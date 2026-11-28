import uuid
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import status

from apps.messaging.models import Conversation, Message, StaffChatProfile
from apps.school.models.school import Section, Staff, Student
from apps.timetable.models import Timetable, TimetableEntry
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger
from shared.utils.s3 import save_to_s3


# =====================================================================
#  CONSTANTS
# =====================================================================

# settings.TIME_ZONE is UTC; available hours are school-local.
SCHOOL_TIME_ZONE = ZoneInfo("Asia/Kolkata")

DEFAULT_MESSAGES_LIMIT = 30
MAX_MESSAGES_LIMIT = 100
TEXT_MAX_LENGTH = 4000
PREVIEW_MAX_LENGTH = 255

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# message_type -> (allowed extensions, max size in bytes)
ATTACHMENT_RULES = {
    Message.MessageType.IMAGE: (("jpg", "jpeg", "png", "webp", "heic", "gif"), 10 * 1024 * 1024),
    Message.MessageType.DOCUMENT: (
        ("pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv"),
        20 * 1024 * 1024,
    ),
    Message.MessageType.AUDIO: (("mp3", "m4a", "aac", "wav", "ogg", "opus", "amr"), 20 * 1024 * 1024),
}

PREVIEW_LABELS = {
    Message.MessageType.IMAGE: "📷 Photo",
    Message.MessageType.DOCUMENT: "📄 Document",
    Message.MessageType.AUDIO: "🎵 Audio",
    Message.MessageType.LOCATION: "📍 Location",
    Message.MessageType.CONTACT: "👤 Contact",
}


# =====================================================================
#  BASIC HELPERS
# =====================================================================
def parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def get_school_now():
    return timezone.now().astimezone(SCHOOL_TIME_ZONE)


def missing_fields_response(missing_fields):
    return CustomResponse.errorResponse(
        description=(
            f"{missing_fields[0]} is required."
            if len(missing_fields) == 1
            else f"{', '.join(missing_fields)} are required."
        ),
        data={
            "missing_fields": missing_fields
        },
    )


def get_request_staff(request):
    return Staff.objects.filter(
        user=request.user,
        school=request.school,
        status=Staff.Status.ACTIVE,
    ).first()


def class_label(student):
    """
    "Grade 3-A"
    """
    grade = student.grade.name if student.grade_id else ""
    section = student.section.name if student.section_id else ""

    return f"{grade}-{section}" if grade and section else grade or section


# =====================================================================
#  PARENT <-> STUDENT
# =====================================================================
def get_parent_student(request, student_id):
    """
    Active student of this school whose father / mother / guardian mobile
    is the logged-in parent's mobile (same match as parent login).
    """
    student_uuid = parse_uuid(student_id)
    mobile = getattr(request.user, "mobile", None)

    if student_uuid is None or not mobile:
        return None

    return Student.objects.filter(
        Q(father_mobile=mobile) | Q(mother_mobile=mobile) | Q(guardian_mobile=mobile),
        id=student_uuid,
        school=request.school,
        status=Student.Status.ACTIVE,
    ).select_related(
        "grade",
        "section",
    ).first()


def get_parent_relation(student, mobile):
    """
    Returns (relation, name from the student record).
    """
    for relation, mobile_field, name_field in (
        ("Father", "father_mobile", "father_name"),
        ("Mother", "mother_mobile", "mother_name"),
        ("Guardian", "guardian_mobile", "guardian_name"),
    ):
        if mobile and getattr(student, mobile_field, None) == mobile:
            return relation, getattr(student, name_field, None)

    return "Parent", None


def get_parent_display_name(user, student):
    full_name = " ".join(
        part for part in [user.first_name, user.last_name] if part
    ).strip()

    if full_name:
        return full_name

    _, record_name = get_parent_relation(student, user.mobile)

    return record_name or user.mobile or user.username


# =====================================================================
#  STUDENT -> TEACHERS (Contact School list)
# =====================================================================
def get_student_teachers(student):
    """
    All ACTIVE teachers of the student's school (and branch, if the
    student has one; school-wide teachers with no branch are included).
    Class teacher and timetable subjects are added when available.
    Returns [{"staff", "subjects", "is_class_teacher"}], class teacher first.
    """

    staff_qs = Staff.objects.filter(
        school_id=student.school_id,
        staff_type=Staff.StaffType.TEACHER,
        status=Staff.Status.ACTIVE,
    ).select_related(
        "chat_profile",
    )

    if student.branch_id:
        staff_qs = staff_qs.filter(
            Q(branch_id=student.branch_id) | Q(branch__isnull=True)
        )

    class_teacher_id = None
    subjects_by_teacher = {}

    if student.section_id:

        class_teacher_id = Section.objects.filter(
            id=student.section_id,
        ).values_list(
            "class_teacher_id",
            flat=True,
        ).first()

        today = get_school_now().date()

        entries = TimetableEntry.objects.filter(
            section_id=student.section_id,
            status=TimetableEntry.Status.ACTIVE,
            timetable__status=Timetable.Status.ACTIVE,
            timetable__is_deleted=False,
            timetable__term__start_date__lte=today,
            timetable__term__end_date__gte=today,
            teacher__isnull=False,
        ).values_list(
            "teacher_id",
            "subject__name",
        )

        for teacher_id, subject_name in entries:
            subjects = subjects_by_teacher.setdefault(teacher_id, [])
            if subject_name and subject_name not in subjects:
                subjects.append(subject_name)

    result = [
        {
            "staff": staff,
            "subjects": subjects_by_teacher.get(staff.id, []),
            "is_class_teacher": staff.id == class_teacher_id,
        }
        for staff in staff_qs
    ]

    result.sort(key=lambda item: (not item["is_class_teacher"], item["staff"].name))

    return result

def teacher_role(item):
    if item["is_class_teacher"]:
        return "Class Teacher"

    if item["subjects"]:
        return f"{item['subjects'][0]} Teacher"

    return "Teacher"


# =====================================================================
#  AVAILABILITY
# =====================================================================
def get_staff_profile(staff):
    try:
        return staff.chat_profile
    except StaffChatProfile.DoesNotExist:
        return None


def get_availability(profile, now=None):
    """
    AVAILABLE / AWAY from the manual switch and available hours.
    """
    if profile is None:
        return "AVAILABLE"

    if not profile.is_available:
        return "AWAY"

    now = now or get_school_now()

    if profile.available_days and now.weekday() not in profile.available_days:
        return "AWAY"

    current_time = now.time().replace(tzinfo=None)

    if profile.available_from and current_time < profile.available_from:
        return "AWAY"

    if profile.available_to and current_time > profile.available_to:
        return "AWAY"

    return "AVAILABLE"


def format_days(days):
    days = sorted(set(day for day in days if isinstance(day, int) and 0 <= day <= 6))

    if not days:
        return ""

    # Consecutive run -> "Mon-Fri"
    if days == list(range(days[0], days[-1] + 1)) and len(days) > 2:
        return f"{DAY_NAMES[days[0]]}-{DAY_NAMES[days[-1]]}"

    return ", ".join(DAY_NAMES[day] for day in days)


def format_available_hours(profile):
    """
    "Mon-Fri, 8:00 AM - 4:00 PM"
    """
    if profile is None or not (profile.available_from and profile.available_to):
        return None

    from_text = profile.available_from.strftime("%I:%M %p").lstrip("0")
    to_text = profile.available_to.strftime("%I:%M %p").lstrip("0")
    days = format_days(profile.available_days or [])

    return f"{days}, {from_text} - {to_text}" if days else f"{from_text} - {to_text}"


def build_profile_data(profile):
    return {
        "about": profile.about if profile else None,
        "classroom_location": profile.classroom_location if profile else None,
        "available_days": profile.available_days if profile else [],
        "available_from": profile.available_from.strftime("%H:%M") if profile and profile.available_from else None,
        "available_to": profile.available_to.strftime("%H:%M") if profile and profile.available_to else None,
        "available_hours": format_available_hours(profile),
        "is_available": profile.is_available if profile else True,
    }


# =====================================================================
#  MESSAGES
# =====================================================================
def build_last_message(conversation, viewer_type):
    if conversation.last_message_at is None:
        return None

    return {
        "text": conversation.last_message_text,
        "message_type": conversation.last_message_type,
        "is_mine": conversation.last_message_sender_type == viewer_type,
        "created_at": conversation.last_message_at,
    }


def build_message_data(message, viewer_type):
    data = {
        "id": str(message.id),
        "sender_type": message.sender_type,
        "is_mine": message.sender_type == viewer_type,
        "message_type": message.message_type,
        "text": message.text,
        "attachment": None,
        "location": None,
        "contact": None,
        "is_read": message.is_read,
        "read_at": message.read_at,
        "client_message_id": message.client_message_id,
        "created_at": message.created_at,
    }

    if message.attachment_url:
        data["attachment"] = {
            "url": message.attachment_url,
            "name": message.attachment_name,
            "size": message.attachment_size,
            "mime_type": message.attachment_mime_type,
        }

    if message.message_type == Message.MessageType.LOCATION:
        data["location"] = {
            "latitude": float(message.latitude) if message.latitude is not None else None,
            "longitude": float(message.longitude) if message.longitude is not None else None,
            "name": message.location_name,
        }

    if message.message_type == Message.MessageType.CONTACT:
        data["contact"] = {
            "name": message.contact_name,
            "phone": message.contact_phone,
        }

    return data


def list_messages(request, conversation, viewer_type):
    """
    GET messages for a conversation.
      ?limit=30           latest messages
      ?before=<msg_id>    older page (scroll up)
      ?after=<msg_id>     only new messages (polling)
    Messages from the other side are marked read.
    """
    try:
        limit = int(request.query_params.get("limit", DEFAULT_MESSAGES_LIMIT))
    except (ValueError, TypeError):
        return CustomResponse.errorResponse(
            description="limit must be a number."
        )

    limit = max(1, min(limit, MAX_MESSAGES_LIMIT))

    messages = Message.objects.filter(
        conversation=conversation,
    )

    before = request.query_params.get("before")
    after = request.query_params.get("after")

    for name, value in (("before", before), ("after", after)):
        if not value:
            continue

        anchor = Message.objects.filter(
            id=parse_uuid(value),
            conversation=conversation,
        ).first() if parse_uuid(value) else None

        if anchor is None:
            return CustomResponse.errorResponse(
                description=f"Invalid {name} message ID."
            )

        if name == "before":
            messages = messages.filter(
                Q(created_at__lt=anchor.created_at)
                | Q(created_at=anchor.created_at, id__lt=anchor.id)
            )
        else:
            messages = messages.filter(
                Q(created_at__gt=anchor.created_at)
                | Q(created_at=anchor.created_at, id__gt=anchor.id)
            )

    if after:
        page = list(messages.order_by("created_at", "id")[:limit + 1])
        has_more = len(page) > limit
        page = page[:limit]
    else:
        page = list(messages.order_by("-created_at", "-id")[:limit + 1])
        has_more = len(page) > limit
        page = list(reversed(page[:limit]))

    # -----------------------------------------
    # Mark the other side's messages as read
    # -----------------------------------------
    other_type = (
        Message.SenderType.STAFF
        if viewer_type == Message.SenderType.PARENT
        else Message.SenderType.PARENT
    )

    now = timezone.now()

    with transaction.atomic():
        marked = Message.objects.filter(
            conversation=conversation,
            sender_type=other_type,
            is_read=False,
        ).update(
            is_read=True,
            read_at=now,
        )

        if viewer_type == Message.SenderType.PARENT:
            Conversation.objects.filter(id=conversation.id).update(parent_unread_count=0)
        else:
            Conversation.objects.filter(id=conversation.id).update(staff_unread_count=0)

    for message in page:
        if message.sender_type == other_type and not message.is_read:
            message.is_read = True
            message.read_at = now

    return CustomResponse.successResponse(
        data={
            "conversation_id": str(conversation.id),
            "messages": [build_message_data(message, viewer_type) for message in page],
            "has_more": has_more,
            "marked_read": marked,
        },
        description="Messages fetched successfully.",
    )


def send_message(request, conversation, sender_type):
    """
    POST a message (JSON or multipart).
      TEXT:      text
      IMAGE / DOCUMENT / AUDIO: file (multipart) or attachment_url, optional text caption
      LOCATION:  latitude, longitude, optional location_name
      CONTACT:   contact_name, contact_phone
      client_message_id (optional): retry-safe, returns the same message
    """
    data = request.data
    message_type = str(data.get("message_type") or Message.MessageType.TEXT).strip().upper()

    if message_type not in Message.MessageType.values:
        return CustomResponse.errorResponse(
            description="message_type must be TEXT, IMAGE, DOCUMENT, AUDIO, LOCATION or CONTACT."
        )

    text = data.get("text")

    if text is not None and not isinstance(text, str):
        return CustomResponse.errorResponse(
            description="text must be a string."
        )

    text = text.strip() if text else None

    if text and len(text) > TEXT_MAX_LENGTH:
        return CustomResponse.errorResponse(
            description=f"Message cannot exceed {TEXT_MAX_LENGTH} characters."
        )

    client_message_id = data.get("client_message_id")
    client_message_id = str(client_message_id).strip()[:64] if client_message_id else None

    if client_message_id:
        existing = Message.objects.filter(
            conversation=conversation,
            client_message_id=client_message_id,
        ).first()

        if existing:
            return CustomResponse.successResponse(
                data=build_message_data(existing, sender_type),
                description="Message already sent.",
            )

    fields = {
        "text": text,
    }

    # -----------------------------------------
    # Per type validation
    # -----------------------------------------
    if message_type == Message.MessageType.TEXT:
        if not text:
            return missing_fields_response(["text"])

    elif message_type in ATTACHMENT_RULES:
        extensions, max_size = ATTACHMENT_RULES[message_type]
        upload = request.FILES.get("file")
        attachment_url = data.get("attachment_url")

        if upload is None and not attachment_url:
            return missing_fields_response(["file"])

        if upload is not None:
            extension = upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""

            if extension not in extensions:
                return CustomResponse.errorResponse(
                    description=f"Allowed {message_type.lower()} files: {', '.join(extensions)}."
                )

            if upload.size > max_size:
                return CustomResponse.errorResponse(
                    description=f"File cannot exceed {max_size // (1024 * 1024)} MB."
                )

            fields["attachment_url"] = save_to_s3(f"messaging/{conversation.id}", upload)
            fields["attachment_name"] = upload.name[:255]
            fields["attachment_size"] = upload.size
            fields["attachment_mime_type"] = (getattr(upload, "content_type", None) or "")[:100] or None
        else:
            if not isinstance(attachment_url, str) or len(attachment_url) > 500:
                return CustomResponse.errorResponse(
                    description="Invalid attachment_url."
                )

            fields["attachment_url"] = attachment_url.strip()
            fields["attachment_name"] = (str(data.get("attachment_name") or "")[:255]) or None

    elif message_type == Message.MessageType.LOCATION:
        missing = [field for field in ("latitude", "longitude") if data.get(field) in (None, "")]

        if missing:
            return missing_fields_response(missing)

        try:
            latitude = Decimal(str(data.get("latitude")))
            longitude = Decimal(str(data.get("longitude")))
        except (InvalidOperation, ValueError, TypeError):
            return CustomResponse.errorResponse(
                description="Invalid latitude or longitude."
            )

        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return CustomResponse.errorResponse(
                description="Invalid latitude or longitude."
            )

        fields["latitude"] = latitude.quantize(Decimal("0.000001"))
        fields["longitude"] = longitude.quantize(Decimal("0.000001"))
        fields["location_name"] = (str(data.get("location_name") or "").strip()[:255]) or None

    elif message_type == Message.MessageType.CONTACT:
        missing = [field for field in ("contact_name", "contact_phone") if not data.get(field)]

        if missing:
            return missing_fields_response(missing)

        fields["contact_name"] = str(data.get("contact_name")).strip()[:150]
        fields["contact_phone"] = str(data.get("contact_phone")).strip()[:20]

    # -----------------------------------------
    # Save + update conversation preview / unread
    # -----------------------------------------
    preview = text or PREVIEW_LABELS.get(message_type, "")

    try:
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                sender_type=sender_type,
                sender_user=request.user,
                message_type=message_type,
                client_message_id=client_message_id,
                **fields,
            )

            updates = {
                "last_message_text": preview[:PREVIEW_MAX_LENGTH],
                "last_message_type": message_type,
                "last_message_sender_type": sender_type,
                "last_message_at": message.created_at,
                "status": Conversation.Status.ACTIVE,
            }

            if sender_type == Message.SenderType.PARENT:
                updates["staff_unread_count"] = F("staff_unread_count") + 1
            else:
                updates["parent_unread_count"] = F("parent_unread_count") + 1

            Conversation.objects.filter(id=conversation.id).update(**updates)

    except IntegrityError:
        # Same client_message_id sent twice at the same time
        existing = Message.objects.filter(
            conversation=conversation,
            client_message_id=client_message_id,
        ).first()

        if existing:
            return CustomResponse.successResponse(
                data=build_message_data(existing, sender_type),
                description="Message already sent.",
            )

        raise

    application_logger.info(
        "messaging_message_sent",
        conversation_id=str(conversation.id),
        message_id=str(message.id),
        sender_type=sender_type,
        message_type=message_type,
        requested_by=str(request.user.id),
    )

    return CustomResponse.successResponse(
        data=build_message_data(message, sender_type),
        description="Message sent successfully.",
    )


def server_error(event, request, **log_fields):
    application_logger.exception(
        event,
        requested_by=str(request.user.id),
        **log_fields,
    )

    return CustomResponse.errorResponse(
        description="Something went wrong. Please try again.",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )

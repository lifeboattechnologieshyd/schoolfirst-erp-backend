from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.messaging.helpers import (
    build_last_message,
    build_profile_data,
    class_label,
    format_available_hours,
    get_availability,
    get_parent_student,
    get_school_now,
    get_staff_profile,
    get_student_teachers,
    list_messages,
    missing_fields_response,
    parse_uuid,
    send_message,
    server_error,
    teacher_role,
)
from apps.messaging.models import Conversation, Message, ParentNote
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


NOTE_MAX_LENGTH = 500


# =====================================================================
#  HELPERS
# =====================================================================
def get_student_or_error(request, student_id):
    """
    Returns (student, error_response).
    """
    if not student_id:
        return None, missing_fields_response(["student_id"])

    student = get_parent_student(request, student_id)

    if student is None:
        return None, CustomResponse.errorResponse(
            description="Invalid student."
        )

    return student, None


def find_teacher(student, staff_id):
    staff_uuid = parse_uuid(staff_id)

    if staff_uuid is None:
        return None

    return next(
        (item for item in get_student_teachers(student) if item["staff"].id == staff_uuid),
        None,
    )


def get_parent_conversation(request, conversation_id):
    conversation_uuid = parse_uuid(conversation_id)

    if conversation_uuid is None:
        return None

    return Conversation.objects.filter(
        id=conversation_uuid,
        parent_user=request.user,
        school=request.school,
    ).select_related(
        "staff",
        "student",
        "student__grade",
        "student__section",
    ).first()


# =====================================================================
#  CONTACT SCHOOL - TEACHERS OF A STUDENT
#  GET contacts?student_id=
# =====================================================================
class MessagingContactLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student, error_response = get_student_or_error(
            request,
            request.query_params.get("student_id"),
        )

        if error_response:
            return error_response

        try:
            now = get_school_now()
            teachers = get_student_teachers(student)

            conversations = {
                conversation.staff_id: conversation
                for conversation in Conversation.objects.filter(
                    parent_user=request.user,
                    student=student,
                )
            }

            office_hours = None
            data = []

            for item in teachers:
                staff = item["staff"]
                profile = get_staff_profile(staff)
                conversation = conversations.get(staff.id)

                if item["is_class_teacher"] and office_hours is None:
                    office_hours = format_available_hours(profile)

                data.append({
                    "staff_id": str(staff.id),
                    "name": staff.name,
                    "profile_image": staff.profile_image,
                    "email": staff.email,
                    "role": teacher_role(item),
                    "subjects": item["subjects"],
                    "is_class_teacher": item["is_class_teacher"],
                    "class": class_label(student),
                    "availability": get_availability(profile, now),
                    "conversation_id": str(conversation.id) if conversation else None,
                    "unread_count": conversation.parent_unread_count if conversation else 0,
                    "last_message": (
                        build_last_message(conversation, Message.SenderType.PARENT)
                        if conversation
                        else None
                    ),
                })

            return CustomResponse.successResponse(
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "class": class_label(student),
                    },
                    "office_hours": office_hours,
                    "contacts": data,
                },
                total=len(data),
                description="Contacts fetched successfully.",
            )

        except Exception:
            return server_error(
                "messaging_contacts_failed",
                request,
                student_id=str(student.id),
            )


# =====================================================================
#  TEACHER PROFILE (parent side) + QUICK NOTES
#  GET teachers/<staff_id>?student_id=
# =====================================================================
class MessagingTeacherDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, staff_id):
        student, error_response = get_student_or_error(
            request,
            request.query_params.get("student_id"),
        )

        if error_response:
            return error_response

        try:
            item = find_teacher(student, staff_id)

            if item is None:
                return CustomResponse.errorResponse(
                    description="Teacher not found for this student.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            staff = item["staff"]
            profile = get_staff_profile(staff)

            conversation = Conversation.objects.filter(
                parent_user=request.user,
                student=student,
                staff=staff,
            ).first()

            notes = ParentNote.objects.filter(
                parent_user=request.user,
                staff=staff,
            ).order_by("-created_at")

            data = {
                "staff_id": str(staff.id),
                "name": staff.name,
                "profile_image": staff.profile_image,
                "email": staff.email,
                "role": teacher_role(item),
                "subjects": item["subjects"],
                "is_class_teacher": item["is_class_teacher"],
                "class": class_label(student),
                "availability": get_availability(profile),
                "conversation_id": str(conversation.id) if conversation else None,
                "notes": [
                    {
                        "id": str(note.id),
                        "note": note.note,
                        "created_at": note.created_at,
                    }
                    for note in notes
                ],
            }

            data.update(build_profile_data(profile))

            return CustomResponse.successResponse(
                data=data,
                description="Teacher details fetched successfully.",
            )

        except Exception:
            return server_error(
                "messaging_teacher_detail_failed",
                request,
                staff_id=str(staff_id),
            )


# =====================================================================
#  QUICK NOTES - ADD / DELETE
# =====================================================================
class ParentNoteCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student_id = request.data.get("student_id")
        staff_id = request.data.get("staff_id")
        note = request.data.get("note")

        missing = [
            field
            for field, value in (("student_id", student_id), ("staff_id", staff_id), ("note", note))
            if value is None or (isinstance(value, str) and not value.strip())
        ]

        if missing:
            return missing_fields_response(missing)

        if not isinstance(note, str) or len(note.strip()) > NOTE_MAX_LENGTH:
            return CustomResponse.errorResponse(
                description=f"Note must be text with at most {NOTE_MAX_LENGTH} characters."
            )

        student, error_response = get_student_or_error(request, student_id)

        if error_response:
            return error_response

        try:
            item = find_teacher(student, staff_id)

            if item is None:
                return CustomResponse.errorResponse(
                    description="Teacher not found for this student.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            parent_note = ParentNote.objects.create(
                school=request.school,
                parent_user=request.user,
                staff=item["staff"],
                student=student,
                note=note.strip(),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(parent_note.id),
                    "note": parent_note.note,
                    "created_at": parent_note.created_at,
                },
                description="Note added successfully.",
            )

        except Exception:
            return server_error("messaging_note_create_failed", request)


class ParentNoteDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, note_id):
        parent_note = ParentNote.objects.filter(
            id=note_id,
            parent_user=request.user,
        ).first()

        if parent_note is None:
            return CustomResponse.errorResponse(
                description="Note not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        parent_note.soft_delete(request.user)

        return CustomResponse.successResponse(
            data={"id": str(parent_note.id)},
            description="Note deleted successfully.",
        )


# =====================================================================
#  START CHAT (returns the existing conversation if there is one)
# =====================================================================
class StartConversationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student_id = request.data.get("student_id")
        staff_id = request.data.get("staff_id")

        missing = [
            field
            for field, value in (("student_id", student_id), ("staff_id", staff_id))
            if not value
        ]

        if missing:
            return missing_fields_response(missing)

        student, error_response = get_student_or_error(request, student_id)

        if error_response:
            return error_response

        try:
            item = find_teacher(student, staff_id)

            if item is None:
                return CustomResponse.errorResponse(
                    description="Teacher not found for this student.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            staff = item["staff"]

            try:
                with transaction.atomic():
                    conversation, created = Conversation.objects.get_or_create(
                        student=student,
                        staff=staff,
                        parent_user=request.user,
                        defaults={
                            "school": request.school,
                        },
                    )
            except IntegrityError:
                conversation = Conversation.objects.get(
                    student=student,
                    staff=staff,
                    parent_user=request.user,
                )
                created = False

            application_logger.info(
                "messaging_conversation_started",
                conversation_id=str(conversation.id),
                created=created,
                requested_by=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "conversation_id": str(conversation.id),
                    "created": created,
                    "staff": {
                        "id": str(staff.id),
                        "name": staff.name,
                        "profile_image": staff.profile_image,
                        "role": teacher_role(item),
                        "availability": get_availability(get_staff_profile(staff)),
                    },
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "class": class_label(student),
                    },
                },
                description="Conversation ready.",
            )

        except Exception:
            return server_error("messaging_conversation_start_failed", request)


# =====================================================================
#  CHAT - LIST / SEND MESSAGES (parent side)
#  GET  conversations/<id>/messages?limit=&before=&after=
#  POST conversations/<id>/messages/send
# =====================================================================
class ParentMessageLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_parent_conversation(request, conversation_id)

        if conversation is None:
            return CustomResponse.errorResponse(
                description="Conversation not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return list_messages(request, conversation, Message.SenderType.PARENT)
        except Exception:
            return server_error(
                "messaging_parent_messages_failed",
                request,
                conversation_id=str(conversation.id),
            )


class ParentMessageSendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        conversation = get_parent_conversation(request, conversation_id)

        if conversation is None:
            return CustomResponse.errorResponse(
                description="Conversation not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return send_message(request, conversation, Message.SenderType.PARENT)
        except Exception:
            return server_error(
                "messaging_parent_send_failed",
                request,
                conversation_id=str(conversation.id),
            )

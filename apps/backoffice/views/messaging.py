from django.db.models import Q, Sum
from django.utils.dateparse import parse_time
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.messaging.helpers import (
    build_last_message,
    build_profile_data,
    class_label,
    get_availability,
    get_parent_display_name,
    get_parent_relation,
    get_request_staff,
    get_staff_profile,
    list_messages,
    parse_uuid,
    send_message,
    server_error,
)
from apps.messaging.models import Conversation, Message, StaffChatProfile
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.utils.logger import application_logger


INBOX_FILTERS = ("ALL", "UNREAD", "HIGH_PRIORITY")


# =====================================================================
#  HELPERS
# =====================================================================
def get_staff_or_error(request):
    """
    Returns (staff, error_response).
    """
    if request.school is None:
        return None, CustomResponse.errorResponse(
            description="School not found."
        )

    staff = get_request_staff(request)

    if staff is None:
        return None, CustomResponse.errorResponse(
            description="Active staff record not found.",
            status=status.HTTP_403_FORBIDDEN,
        )

    return staff, None


def get_staff_conversation(staff, conversation_id):
    conversation_uuid = parse_uuid(conversation_id)

    if conversation_uuid is None:
        return None

    return Conversation.objects.filter(
        id=conversation_uuid,
        staff=staff,
    ).select_related(
        "parent_user",
        "student",
        "student__grade",
        "student__section",
    ).first()


def build_parent_summary(conversation):
    student = conversation.student
    relation, _ = get_parent_relation(student, conversation.parent_user.mobile)

    return {
        "user_id": str(conversation.parent_user_id),
        "name": get_parent_display_name(conversation.parent_user, student),
        "relation": relation,
        "subtitle": f"Parent of {student.name} · {class_label(student)}",
    }


# =====================================================================
#  CONTACT INBOX
#  GET messaging/inbox?filter=ALL|UNREAD|HIGH_PRIORITY&search=
# =====================================================================
class TeacherInboxAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        inbox_filter = (request.query_params.get("filter") or "ALL").strip().upper()

        if inbox_filter not in INBOX_FILTERS:
            return CustomResponse.errorResponse(
                description="filter must be ALL, UNREAD or HIGH_PRIORITY."
            )

        try:
            base = Conversation.objects.filter(
                staff=staff,
                school=request.school,
                last_message_at__isnull=False,
            )

            conversations = base.select_related(
                "parent_user",
                "student",
                "student__grade",
                "student__section",
            ).order_by(
                "-last_message_at",
            )

            if inbox_filter == "UNREAD":
                conversations = conversations.filter(staff_unread_count__gt=0)
            elif inbox_filter == "HIGH_PRIORITY":
                conversations = conversations.filter(is_high_priority=True)

            search = request.query_params.get("search")

            if search and search.strip():
                search = search.strip()
                conversations = conversations.filter(
                    Q(parent_user__first_name__icontains=search)
                    | Q(parent_user__last_name__icontains=search)
                    | Q(parent_user__mobile__icontains=search)
                    | Q(student__name__icontains=search)
                    | Q(student__father_name__icontains=search)
                    | Q(student__mother_name__icontains=search)
                    | Q(student__guardian_name__icontains=search)
                )

            unread_conversations = base.filter(staff_unread_count__gt=0).count()
            unread_messages = base.aggregate(total=Sum("staff_unread_count"))["total"] or 0

            total = conversations.count()

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                conversations,
                request,
                view=self,
            )

            data = [
                {
                    "conversation_id": str(conversation.id),
                    "parent": build_parent_summary(conversation),
                    "student": {
                        "id": str(conversation.student_id),
                        "name": conversation.student.name,
                        "class": class_label(conversation.student),
                    },
                    "last_message": build_last_message(conversation, Message.SenderType.STAFF),
                    "unread_count": conversation.staff_unread_count,
                    "is_high_priority": conversation.is_high_priority,
                }
                for conversation in page
            ]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                unread_conversations=unread_conversations,
                unread_messages=unread_messages,
                description="Inbox fetched successfully.",
            )

        except Exception:
            return server_error("messaging_inbox_failed", request, staff_id=str(staff.id))


# =====================================================================
#  PARENT DETAILS
#  GET messaging/conversations/<id>/parent
# =====================================================================
class TeacherConversationParentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        conversation = get_staff_conversation(staff, conversation_id)

        if conversation is None:
            return CustomResponse.errorResponse(
                description="Conversation not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        student = conversation.student
        parent_user = conversation.parent_user

        data = build_parent_summary(conversation)
        data.update({
            "conversation_id": str(conversation.id),
            "is_high_priority": conversation.is_high_priority,
            "contact": {
                "email": parent_user.email or student.email,
                "mobile": parent_user.mobile,
                "location": student.address,
            },
            "student": {
                "id": str(student.id),
                "name": student.name,
                "class": student.grade.name if student.grade_id else None,
                "section": student.section.name if student.section_id else None,
                "roll_number": student.roll_number,
                "admission_number": student.admission_number,
                "blood_group": student.blood_group,
                "date_of_birth": student.date_of_birth,
                "photo_url": student.photo_url,
            },
        })

        return CustomResponse.successResponse(
            data=data,
            description="Parent details fetched successfully.",
        )


# =====================================================================
#  CHAT - LIST / SEND MESSAGES (teacher side)
# =====================================================================
class TeacherMessageLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        conversation = get_staff_conversation(staff, conversation_id)

        if conversation is None:
            return CustomResponse.errorResponse(
                description="Conversation not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return list_messages(request, conversation, Message.SenderType.STAFF)
        except Exception:
            return server_error(
                "messaging_teacher_messages_failed",
                request,
                conversation_id=str(conversation.id),
            )


class TeacherMessageSendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        conversation = get_staff_conversation(staff, conversation_id)

        if conversation is None:
            return CustomResponse.errorResponse(
                description="Conversation not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return send_message(request, conversation, Message.SenderType.STAFF)
        except Exception:
            return server_error(
                "messaging_teacher_send_failed",
                request,
                conversation_id=str(conversation.id),
            )


# =====================================================================
#  HIGH PRIORITY FLAG
#  PUT messaging/conversations/<id>/priority  {"is_high_priority": true}
# =====================================================================
class TeacherConversationPriorityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, conversation_id):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        is_high_priority = request.data.get("is_high_priority")

        if not isinstance(is_high_priority, bool):
            return CustomResponse.errorResponse(
                description="is_high_priority must be true or false."
            )

        conversation = get_staff_conversation(staff, conversation_id)

        if conversation is None:
            return CustomResponse.errorResponse(
                description="Conversation not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        conversation.is_high_priority = is_high_priority
        conversation.save(update_fields=["is_high_priority", "updated_at", "updated_by"])

        return CustomResponse.successResponse(
            data={
                "conversation_id": str(conversation.id),
                "is_high_priority": conversation.is_high_priority,
            },
            description="Priority updated successfully.",
        )


# =====================================================================
#  MY CHAT PROFILE (shown to parents)
#  GET messaging/profile, PUT messaging/profile/save
# =====================================================================
class MyChatProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        profile = get_staff_profile(staff)

        data = {
            "staff_id": str(staff.id),
            "name": staff.name,
            "email": staff.email,
            "profile_image": staff.profile_image,
            "availability": get_availability(profile),
        }
        data.update(build_profile_data(profile))

        return CustomResponse.successResponse(
            data=data,
            description="Chat profile fetched successfully.",
        )


class SaveMyChatProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        staff, error_response = get_staff_or_error(request)

        if error_response:
            return error_response

        allowed_fields = {
            "about",
            "classroom_location",
            "available_days",
            "available_from",
            "available_to",
            "is_available",
        }

        invalid_fields = set(request.data.keys()) - allowed_fields

        if invalid_fields:
            return CustomResponse.errorResponse(
                description=f"Invalid fields: {', '.join(sorted(invalid_fields))}."
            )

        updates = {}
        data = request.data

        for field, max_length in (("about", 1000), ("classroom_location", 255)):
            if field in data:
                value = data.get(field)

                if value is not None and not isinstance(value, str):
                    return CustomResponse.errorResponse(
                        description=f"{field} must be text."
                    )

                value = value.strip() if value else None

                if value and len(value) > max_length:
                    return CustomResponse.errorResponse(
                        description=f"{field} cannot exceed {max_length} characters."
                    )

                updates[field] = value

        if "available_days" in data:
            days = data.get("available_days")

            if not isinstance(days, list) or any(
                not isinstance(day, int) or isinstance(day, bool) or not 0 <= day <= 6
                for day in days
            ):
                return CustomResponse.errorResponse(
                    description="available_days must be a list of numbers 0 (Mon) to 6 (Sun)."
                )

            updates["available_days"] = sorted(set(days))

        for field in ("available_from", "available_to"):
            if field in data:
                value = data.get(field)

                if value in (None, ""):
                    updates[field] = None
                else:
                    parsed = parse_time(str(value))

                    if parsed is None:
                        return CustomResponse.errorResponse(
                            description=f"{field} must be a time like 08:00."
                        )

                    updates[field] = parsed

        if "is_available" in data:
            if not isinstance(data.get("is_available"), bool):
                return CustomResponse.errorResponse(
                    description="is_available must be true or false."
                )

            updates["is_available"] = data.get("is_available")

        try:
            profile = get_staff_profile(staff) or StaffChatProfile(staff=staff)

            for field, value in updates.items():
                setattr(profile, field, value)

            if profile.available_from and profile.available_to and profile.available_from >= profile.available_to:
                return CustomResponse.errorResponse(
                    description="available_from must be before available_to."
                )

            profile.save()

            application_logger.info(
                "messaging_chat_profile_saved",
                staff_id=str(staff.id),
                requested_by=str(request.user.id),
            )

            data = {
                "staff_id": str(staff.id),
                "availability": get_availability(profile),
            }
            data.update(build_profile_data(profile))

            return CustomResponse.successResponse(
                data=data,
                description="Chat profile saved successfully.",
            )

        except Exception:
            return server_error("messaging_chat_profile_save_failed", request, staff_id=str(staff.id))

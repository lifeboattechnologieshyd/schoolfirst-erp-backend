from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import InvitationCode, UserMaster
from apps.core.serializers.invitations import InvitationCodeSerializer
from shared.helpers.invitation import create_invitation_code, validate_invite_code
from shared.mixins.drf_views import CustomResponse


class InvitationCodeCreateView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        code_type = request.data.get("code_type", "generic")
        target_email = request.data.get("target_email")
        max_uses = request.data.get("max_uses", 1)
        expires_in_days = request.data.get("expires_in_days", 30)

        invite = create_invitation_code(
            created_by_user_id=request.user.id,
            code_type=code_type,
            target_email=target_email,
            max_uses=max_uses,
            expires_in_days=expires_in_days,
        )

        return self.build_response(
            success=True,
            message="Invitation code created successfully",
            data=InvitationCodeSerializer(invite).data,
            status=201,
        )


class InvitationCodeListView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        include_inactive = request.query_params.get("include_inactive", "false").lower() == "true"

        queryset = InvitationCode.objects.filter(created_by_user_id=request.user.id)
        if not include_inactive:
            queryset = queryset.filter(is_active=True)

        return self.build_response(
            success=True, message="Your invitation codes.", data=InvitationCodeSerializer(queryset, many=True).data
        )


class InvitationCodeDeleteView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, code: str) -> Response:
        invite = InvitationCode.objects.filter(code=code, created_by_user_id=request.user.id).first()
        if not invite:
            return self.build_response(
                success=False,
                message="Invitation code not found",
                error={"code": "NOT_FOUND", "message": "Invitation code not found"},
                status=404,
            )

        invite.is_active = False
        invite.save()

        return self.build_response(success=True, message="Invitation code deleted successfully")


class InvitationCodeUsersView(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, code: str) -> Response:
        invite = InvitationCode.objects.filter(code=code, created_by_user_id=request.user.id).first()
        if not invite:
            return self.build_response(
                success=False,
                message="Invitation code not found",
                error={"code": "NOT_FOUND", "message": "Invitation code not found"},
                status=404,
            )

        users = UserMaster.objects.filter(signup_invite_code=code)
        user_list = []
        for user in users:
            user_list.append(
                {
                    "id": str(user.id),
                    "email": user.email,
                    "created_at": user.created_at,  # Assuming AuditModel provides created_at
                }
            )

        return self.build_response(
            success=True,
            message="Users who signed up with this code.",
            data={"invite_code": code, "users": user_list, "total": len(user_list)},
        )


class InvitationCodeValidateView(APIView, CustomResponse):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        invite_code = request.data.get("invite_code")
        email = request.data.get("email")

        if not invite_code:
            return self.build_response(
                success=False,
                message="Invite code is required.",
                error={"code": "REQUIRED", "message": "Invite code is required."},
                status=400,
            )

        is_valid, error_msg, invite = validate_invite_code(invite_code, email)

        if not is_valid:
            return self.build_response(
                success=False, message=error_msg, error={"code": "INVALID", "message": error_msg}, status=400
            )

        return self.build_response(
            success=True,
            message="Invitation code is valid",
            data={"code_type": invite.code_type, "remaining_uses": invite.max_uses - invite.current_uses},
        )

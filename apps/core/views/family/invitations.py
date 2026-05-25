from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.serializers.family import FamilyInvitationSerializer
from apps.core.services.family_service import FamilyService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomCreateAPIView


class FamilyInvitationAcceptView(CustomCreateAPIView):
    """POST: accept a pending family invitation for the current user."""

    permission_classes = [IsAuthenticated]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        family_id = self.kwargs.get("family_id")
        try:
            member = FamilyService.accept_invitation(user_id=request.user.id, family_id=family_id)
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return self.build_response(
            success=True,
            data=FamilyInvitationSerializer(member).data,
            message="Family invitation accepted.",
            status=status.HTTP_200_OK,
        )


class FamilyInvitationDeclineView(CustomCreateAPIView):
    """POST: decline a pending family invitation for the current user."""

    permission_classes = [IsAuthenticated]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        family_id = self.kwargs.get("family_id")
        try:
            member = FamilyService.decline_invitation(user_id=request.user.id, family_id=family_id)
            return self.build_response(
                success=True,
                data=FamilyInvitationSerializer(member).data,
                message="Family invitation declined.",
                status=status.HTTP_200_OK,
            )
        except Http404:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": GlobalAPIMessageCodes.NOT_FOUND.label,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class FamilyExitView(CustomCreateAPIView):
    """POST: exit a family (non-owner members only)."""

    permission_classes = [IsAuthenticated]

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        family_id = self.kwargs.get("family_id")
        FamilyService.exit_family(family_id=family_id, user_id=request.user.id)
        return self.build_response(
            success=True,
            message="You have exited the family.",
            status=status.HTTP_200_OK,
        )

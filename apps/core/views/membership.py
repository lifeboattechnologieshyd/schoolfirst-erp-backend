"""
Membership application views.
Public endpoint for users to apply for membership.
"""

import structlog
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import MembershipApplication
from apps.core.serializers.membership import MembershipApplicationSerializer
from shared.enums import ApplicationStatus, GlobalAPIMessageCodes
from shared.mixins import CustomResponse

logger = structlog.get_logger("default")


class MembershipApplicationCrud(APIView, CustomResponse):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = MembershipApplicationSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
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

        data = serializer.validated_data
        MembershipApplication.objects.create(
            name=data.get("name"),
            email=data["email"],
            mobile=data.get("mobile"),
            source=data.get("source"),
            remarks=data.get("remarks"),
            status=ApplicationStatus.PENDING,
        )
        return self.build_response(
            success=True,
            message="Application submitted successfully",
            status=status.HTTP_201_CREATED,
        )

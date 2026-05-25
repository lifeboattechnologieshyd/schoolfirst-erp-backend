from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.core.serializers.user_lookup import UserLookupRequestSerializer, UserLookupResponseSerializer
from apps.core.services.user_lookup_service import UserLookupService
from shared.enums import GlobalAPIMessageCodes
from shared.mixins.drf_views import CustomCreateAPIView


class UserLookupView(CustomCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method == "POST":
            return UserLookupRequestSerializer
        return UserLookupResponseSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        user_info = UserLookupService.get_by_email(email)

        if not user_info:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.NOT_FOUND,
                    "message": "User not found.",
                },
                status=404,
            )

        return self.build_response(
            success=True,
            message="User found.",
            data=user_info.to_response_data(),
            status=200,
        )

from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.constants import ALLOWED_IMAGE_EXTENSIONS
from apps.core.serializers.user import UserProfileSerializer
from shared.mixins.drf_views import CustomResponse
from shared.utils.files import move_file, validate_image_temp_path


class Profile(APIView, CustomResponse):
    permission_classes = [IsAuthenticated]

    def _apply_profile_image(self, user: Any, profile_image: str) -> str | None:
        """Validate temp path, move file, set user.profile_image."""
        error = validate_image_temp_path(profile_image, user.id, ALLOWED_IMAGE_EXTENSIONS)
        if error:
            return error
        new_path = move_file(profile_image, f"profiles/{user.id}")
        user.profile_image = new_path or profile_image
        return None

    def get(self, request: Request) -> Response:
        return self.build_response(
            success=True,
            message="Profile retrieved successfully.",
            data=UserProfileSerializer(request.user).data,
            status=200,
        )

    def patch(self, request: Request) -> Response:
        user = request.user
        profile_data = request.data.get("profile", request.data)

        first_name = profile_data.get("first_name")
        last_name = profile_data.get("last_name")
        gender = profile_data.get("gender")
        dob = profile_data.get("dob")
        profile_image = profile_data.get("profile_image")
        has_profile_updates = any(value is not None for value in [first_name, last_name, gender, dob, profile_image])

        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if gender is not None:
            user.gender = gender
        if dob is not None:
            user.date_of_birth = dob
        if profile_image is not None:
            error = self._apply_profile_image(user, profile_image)
            if error:
                return self.build_response(
                    success=False,
                    error={"code": "VALIDATION_ERROR", "message": error, "details": None},
                    status=400,
                )

        if has_profile_updates and not user.is_profile_updated:
            user.is_profile_updated = True

        user.save()
        return self.build_response(
            success=True,
            message="Profile updated successfully.",
            data=UserProfileSerializer(request.user).data,
            status=200,
        )

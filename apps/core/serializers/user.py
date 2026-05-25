from rest_framework import serializers

from apps.core.models.user import UserMaster
from shared.utils.files import get_file_url


class UserProfileSerializer(serializers.ModelSerializer):
    dob = serializers.DateField(source="date_of_birth", allow_null=True, read_only=True)
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = UserMaster
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "gender",
            "dob",
            "profile_image",
            "is_profile_updated",
            "is_password_updated",
        ]

    def get_profile_image(self, obj):
        return get_file_url(obj.profile_image) if obj.profile_image else None

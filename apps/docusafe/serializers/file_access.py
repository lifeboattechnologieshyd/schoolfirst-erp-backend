from rest_framework import serializers

from apps.docusafe.models.file_access import DocusafeFileAccess
from shared.enums import DocusafeAccessType


class DocusafeFileAccessSerializer(serializers.ModelSerializer):
    """
    Serializer for DocusafeFileAccess model.
    """

    class Meta:
        model = DocusafeFileAccess
        fields = [
            "id",
            "file_id",
            "access_type",
            "family_id",
            "user_id",
            "owner_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_id",
            "created_at",
            "updated_at",
        ]


class GrantAccessSerializer(serializers.Serializer):
    """
    Serializer for granting file access.
    """

    file_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, required=True)
    access_type = serializers.ChoiceField(choices=DocusafeAccessType.choices, required=True)
    family_id = serializers.UUIDField(required=True)
    user_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)

    def validate(self, attrs):
        if attrs["access_type"] == DocusafeAccessType.USER and not attrs.get("user_ids"):
            raise serializers.ValidationError("user_ids are required when access_type is USER.")
        return attrs


class RevokeAccessSerializer(serializers.Serializer):
    """
    Serializer for revoking file access.
    """

    access_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, required=True)

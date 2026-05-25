import json
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.docusafe.constants import FILE_RETRIEVE_URL_EXPIRY_SECONDS
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.services.file_storage_service import DocusafeFileStorageService


class DocusafeFileSerializer(serializers.ModelSerializer):
    """
    Base serializer for DocusafeFile model (Minimal for listing).
    """

    class Meta:
        model = DocusafeFile
        fields = [
            "id",
            "file_name",
            "file_size",
            "mime_type",
            "is_shared",
            "status",
            "llm_status",
            "created_at",
        ]
        read_only_fields = fields


class DocusafeFileDetailSerializer(DocusafeFileSerializer):
    """
    Detailed serializer for DocusafeFile model.
    """

    file_url = serializers.SerializerMethodField()

    def get_file_url(self, obj) -> str | None:
        try:
            return DocusafeFileStorageService.get_presigned_url(obj.file_path, expiry=FILE_RETRIEVE_URL_EXPIRY_SECONDS)
        except ValidationError:
            return None

    class Meta(DocusafeFileSerializer.Meta):
        fields = [
            *DocusafeFileSerializer.Meta.fields,
            "description",
            "summary",
            "embedding_model",
            "folder_id",
            "file_extension",
            "checksum",
            "file_url",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "folder_id",
            "mime_type",
            "file_size",
            "file_extension",
            "checksum",
            "is_shared",
            "status",
            "llm_status",
            "summary",
            "embedding_model",
            "file_url",
            "created_at",
            "updated_at",
        ]


class DocusafeFileRetrieveSerializer(DocusafeFileDetailSerializer):
    """
    File detail serializer for retrieve responses.
    """

    file_url_expiry = serializers.SerializerMethodField()

    def get_file_url_expiry(self, obj):
        return timezone.now() + timedelta(seconds=FILE_RETRIEVE_URL_EXPIRY_SECONDS - 10)

    class Meta(DocusafeFileDetailSerializer.Meta):
        fields = [
            *DocusafeFileDetailSerializer.Meta.fields,
            "file_url_expiry",
        ]
        read_only_fields = [
            *DocusafeFileDetailSerializer.Meta.read_only_fields,
            "file_url_expiry",
        ]


class BulkUploadDescriptionItemSerializer(serializers.Serializer):
    """
    Validates individual item in the bulk upload 'descriptions' array.
    """

    file_name = serializers.CharField(required=True)
    description = serializers.CharField(required=True, allow_blank=True)


class BulkUploadInputSerializer(serializers.Serializer):
    """
    Validates the multipart form 'descriptions' JSON string list.
    """

    descriptions = serializers.JSONField(required=True)

    def validate_descriptions(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Must be valid JSON.") from None

        if not isinstance(value, list):
            raise serializers.ValidationError("Descriptions must be a JSON list.")

        child_serializer = BulkUploadDescriptionItemSerializer(data=value, many=True)
        child_serializer.is_valid(raise_exception=True)
        return child_serializer.validated_data

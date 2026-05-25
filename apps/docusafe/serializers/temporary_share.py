import json

from django.utils import timezone
from rest_framework import serializers

from apps.docusafe.constants import MAX_SHARE_CLIENT_METADATA_BYTES
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.temporary_share import (
    ShareViewLog,
    TemporaryFileShare,
    TemporaryShareFile,
)


class SharedFileMetadataSerializer(serializers.ModelSerializer):
    file_id = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = DocusafeFile
        fields = ["id", "file_id", "file_name", "file_size", "mime_type"]


class TemporaryFileShareSerializer(serializers.ModelSerializer):
    """
    Overview serializer for listing temporary shares.
    """

    class Meta:
        model = TemporaryFileShare
        fields = [
            "id",
            "title",
            "status",
            "expires_at",
            "view_count",
            "file_count",
            "created_at",
        ]
        read_only_fields = fields


class TemporaryFileShareDetailSerializer(TemporaryFileShareSerializer):
    """
    Detailed serializer for a specific temporary share.
    """

    password = serializers.CharField(write_only=True, required=False, min_length=8)
    files = serializers.JSONField(required=False)
    views = serializers.SerializerMethodField()
    recipient_emails = serializers.ListField(child=serializers.EmailField(), required=False)

    class Meta(TemporaryFileShareSerializer.Meta):
        fields = [
            *TemporaryFileShareSerializer.Meta.fields,
            "max_views",
            "failed_attempts",
            "max_failed_attempts",
            "owner_id",
            "recipient_emails",
            "password",
            "files",
            "views",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "view_count",
            "failed_attempts",
            "file_count",
            "owner_id",
            "files",
            "views",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        if getattr(instance, "_empty_deleted", False):
            return {
                "id": instance.id,
                "status": "DELETED",
                "file_count": 0,
                "message": "Share was deleted because it became empty.",
            }
        ret = super().to_representation(instance)
        # Use prefetched file list if the view attached it to avoid extra queries.
        prefetched_files = getattr(instance, "_prefetched_files", None)
        if prefetched_files is None:
            file_ids = TemporaryShareFile.objects.filter(share_id=instance.id).values_list("file_id", flat=True)
            prefetched_files = list(DocusafeFile.objects.filter(id__in=file_ids))
        ret["files"] = SharedFileMetadataSerializer(prefetched_files, many=True).data
        return ret

    def get_views(self, obj):
        prefetched_logs = getattr(obj, "_prefetched_view_logs", None)
        if prefetched_logs is None:
            prefetched_logs = list(ShareViewLog.objects.filter(share_id=obj.id))
        return ShareViewLogSerializer(prefetched_logs, many=True).data

    def update(self, instance, validated_data):
        from apps.docusafe.services.share_owner_service import (  # noqa: PLC0415
            DocusafeShareOwnerService,
        )

        files_data = validated_data.pop("files", None)
        file_ids = None
        if files_data is not None:
            # Extract IDs from list of objects or list of IDs
            file_ids = []
            for f in files_data:
                if isinstance(f, dict):
                    file_ids.append(f.get("id") or f.get("file_id"))
                else:
                    file_ids.append(f)

        # Call service to handle complex updates
        update_data = validated_data.copy()
        if file_ids is not None:
            update_data["file_ids"] = file_ids

        updated_instance = DocusafeShareOwnerService.update_share(
            user_id=self.context["request"].user.id,
            share_id=instance.id,
            **update_data,
        )
        return updated_instance

    def validate_expires_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Expiration time must be in the future.")
        return value


class CreateTemporaryShareSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    file_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    password = serializers.CharField(write_only=True, min_length=8)
    expires_at = serializers.DateTimeField()
    max_views = serializers.IntegerField(required=False, min_value=1)
    max_failed_attempts = serializers.IntegerField(required=False, min_value=1, default=5)
    recipient_emails = serializers.ListField(child=serializers.EmailField(), required=False)

    def validate_expires_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Expiration time must be in the future.")
        return value


class TemporaryShareAccessSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)
    client_metadata = serializers.JSONField(required=False, default=dict)

    def validate_client_metadata(self, value):
        if value is None:
            return {}

        if not isinstance(value, dict):
            raise serializers.ValidationError("client_metadata must be a JSON object.")

        encoded_value = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(encoded_value) > MAX_SHARE_CLIENT_METADATA_BYTES:
            raise serializers.ValidationError(
                f"client_metadata must be at most {MAX_SHARE_CLIENT_METADATA_BYTES} bytes."
            )

        return value


class ShareViewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareViewLog
        fields = [
            "id",
            "share_id",
            "success",
            "failure_reason",
            "viewed_at",
            "ip_address",
            "user_agent",
            "device_type",
            "device_os",
            "browser",
            "country",
            "city",
            "client_metadata",
        ]

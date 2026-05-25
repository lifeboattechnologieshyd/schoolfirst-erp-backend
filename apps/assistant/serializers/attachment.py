"""
Attachment Serializers

Handles serialization for file attachments.
"""

from rest_framework import serializers

from apps.assistant.models import Attachment
from shared.utils.files import get_public_file_url


class AttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for file attachments with public URL generation.
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id",
            "file_name",
            "file_size",
            "mime_type",
            "width",
            "height",
            "duration",
            "url",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_url(self, obj):
        """
        Generate public URL for the attachment file.
        """
        if obj.file_path:
            return get_public_file_url(obj.file_path)
        return None

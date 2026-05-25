from django.db import models
from rest_framework import serializers

from apps.assistant.models import Attachment, Message
from apps.assistant.serializers.attachment import AttachmentSerializer
from apps.assistant.serializers.content_block import ContentBlockSerializer


class MessageSerializer(serializers.ModelSerializer):
    attachments = serializers.SerializerMethodField()
    content_blocks = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "thread_id",
            "sender_type",
            "content_blocks",
            "schema_version",
            "role_metadata",
            "attachments",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "thread_id",
            "sender_type",
            "content_blocks",
            "schema_version",
            "role_metadata",
            "attachments",
            "created_at",
        ]

    def _build_related_cache(self):
        """
        Builds a cache of attachments for the current result set to avoid N+1 queries.
        Supports both single instance and list/paginated results.
        """
        if self.context.get("_message_related_cache_ready"):
            return

        # Determine the set of message IDs being serialized
        message_ids = []
        if isinstance(self.instance, list):
            message_ids = [obj.id for obj in self.instance]
        elif hasattr(self.instance, "id"):
            message_ids = [self.instance.id]
        elif self.instance is None and hasattr(self.parent, "instance"):
            # This happens when being called as a child of a list serializer
            parent_instance = self.parent.instance
            if isinstance(parent_instance, (list, models.QuerySet)):
                message_ids = [obj.id for obj in parent_instance]

        if not message_ids:
            return

        # Fetch all relevant attachments in one query
        attachment_map = {m_id: [] for m_id in message_ids}
        attachments = Attachment.objects.filter(message_id__in=message_ids).order_by("created_at")

        for attachment in attachments:
            attachment_map[attachment.message_id].append(attachment)

        self.context["_attachment_map"] = attachment_map
        self.context["_message_related_cache_ready"] = True

    def get_attachments(self, obj):
        """
        Fetch attachments for this message from the Attachment table.
        """
        self._build_related_cache()
        attachments = self.context.get("_attachment_map", {}).get(obj.id)
        if attachments is None:
            attachments = Attachment.objects.filter(message_id=obj.id).order_by("created_at")
        return AttachmentSerializer(attachments, many=True, context=self.context).data

    def get_content_blocks(self, obj):
        """Serialize each block through the appropriate typed serializer."""
        blocks = obj.content_blocks
        if not blocks:
            return []
        return ContentBlockSerializer(blocks, many=True).data


class ChatRequestSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    stream = serializers.BooleanField(required=False, default=True)
    attachments = serializers.ListField(child=serializers.CharField(), required=False, default=list)

from typing import Any

from rest_framework import serializers

# ── Leaf serializers ──────────────────────────────────────────────────────────


class TextBlockSerializer(serializers.Serializer):
    type = serializers.CharField()
    index = serializers.IntegerField(required=False)
    text = serializers.CharField(allow_blank=True)


class ToolCallResultSerializer(serializers.Serializer):
    status = serializers.CharField(required=False)
    data = serializers.JSONField(required=False)
    error_message = serializers.CharField(required=False, allow_blank=True)


class ToolCallBlockSerializer(serializers.Serializer):
    type = serializers.CharField()
    index = serializers.IntegerField(required=False)
    id = serializers.CharField()  # noqa: A003
    name = serializers.CharField()
    input = serializers.JSONField(default=dict)  # noqa: A003
    result = ToolCallResultSerializer(required=False, allow_null=True)
    progress_label = serializers.CharField(required=False, allow_blank=True)


# ── Polymorphic dispatcher ────────────────────────────────────────────────────

_BLOCK_SERIALIZER_MAP = {
    "text": TextBlockSerializer,
    "tool_call": ToolCallBlockSerializer,
}


class ContentBlockSerializer(serializers.Serializer):
    """
    Read-only polymorphic serializer for a single content block dict.
    Dispatches to the correct typed serializer based on the ``type`` key.
    Unknown types are passed through as-is.
    """

    def to_representation(self, instance: Any) -> Any:
        block_type: str | None = None
        if isinstance(instance, dict):
            raw_block_type = instance.get("type")
            if isinstance(raw_block_type, str):
                block_type = raw_block_type

        serializer_class = _BLOCK_SERIALIZER_MAP.get(block_type) if block_type else None
        if serializer_class:
            return serializer_class(instance).data
        return instance

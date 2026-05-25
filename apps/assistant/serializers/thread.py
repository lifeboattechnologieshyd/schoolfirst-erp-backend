import uuid
from collections import OrderedDict

from rest_framework import serializers

from apps.assistant.enums import DEFAULT_THREAD_NAME
from apps.assistant.models import Thread
from apps.assistant.serializers.thread_settings import (
    ThreadModuleSettingsSerializer,
    ThreadSettingsSerializer,
    coerce_thread_module_settings,
    serialize_thread_module_settings,
)
from apps.assistant.thread_specializations import validate_module_settings


class ThreadSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, required=False, default=DEFAULT_THREAD_NAME)
    settings = ThreadSettingsSerializer(required=False, allow_null=True)
    module_settings = ThreadModuleSettingsSerializer(required=False, allow_null=True)

    class Meta:
        model = Thread
        fields = [
            "id",
            "user_id",
            "name",
            "status",
            "summary",
            "model",
            "settings",
            "module_settings",
            "is_temporary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user_id", "summary", "model", "created_at", "updated_at"]

    def create(self, validated_data):
        # Always force name to "New Chat" on creation
        validated_data["name"] = DEFAULT_THREAD_NAME
        validated_data = self._ensure_json_serializable(validated_data)
        return super().create(validated_data)

    def validate_module_settings(self, value):
        if not value:
            return value

        request = self.context.get("request")
        user_id = str(request.user.id) if request and request.user else None
        validated_value = validate_module_settings(value, user_id=user_id)
        return serialize_thread_module_settings(validated_value)

    def update(self, instance, validated_data):
        validated_data = self._ensure_json_serializable(validated_data)
        return super().update(instance, validated_data)

    def _ensure_json_serializable(self, data: dict) -> dict:
        """
        Recursively ensure dictionary values are JSON serializable.
        Specifically converts UUIDs to strings.
        """

        def serialize(obj):
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, (dict, OrderedDict)):
                return {k: serialize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [serialize(i) for i in obj]
            return obj

        if data.get("module_settings"):
            data["module_settings"] = serialize_thread_module_settings(
                coerce_thread_module_settings(data["module_settings"])
            )

        if data.get("settings"):
            data["settings"] = serialize(data["settings"])

        return data

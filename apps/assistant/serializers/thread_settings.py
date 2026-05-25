from collections.abc import Mapping
from dataclasses import dataclass

from rest_framework import serializers


@dataclass(frozen=True)
class ThreadModuleSettingsData:
    module_name: str | None = None
    docusafe_file_ids: tuple[str, ...] = ()


def coerce_thread_module_settings(
    value: ThreadModuleSettingsData | Mapping[str, object] | None,
) -> ThreadModuleSettingsData:
    if isinstance(value, ThreadModuleSettingsData):
        return value

    if not value:
        return ThreadModuleSettingsData()

    module_name = value.get("module_name")
    raw_file_ids = value.get("docusafe_file_ids")
    docusafe_file_ids = ()
    if isinstance(raw_file_ids, list):
        docusafe_file_ids = tuple(str(file_id) for file_id in raw_file_ids if file_id)

    return ThreadModuleSettingsData(
        module_name=str(module_name) if module_name else None,
        docusafe_file_ids=docusafe_file_ids,
    )


def serialize_thread_module_settings(value: ThreadModuleSettingsData | None) -> dict[str, object] | None:
    if value is None or (value.module_name is None and not value.docusafe_file_ids):
        return None

    data: dict[str, object] = {}
    if value.module_name is not None:
        data["module_name"] = value.module_name
    if value.module_name == "docusafe" or value.docusafe_file_ids:
        data["docusafe_file_ids"] = list(value.docusafe_file_ids)
    return data


class ThreadSettingsSerializer(serializers.Serializer):
    """
    Typed serializer for the Thread.settings JSONField.
    All flags are optional — omitted keys retain their defaults.
    """

    enabled_web_search = serializers.BooleanField(required=False, default=True)


class ThreadModuleSettingsSerializer(serializers.Serializer):
    module_name = serializers.CharField(max_length=255, required=False, allow_null=True)
    docusafe_file_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_null=True)

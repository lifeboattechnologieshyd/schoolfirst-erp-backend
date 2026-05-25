from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import structlog
from rest_framework.exceptions import ValidationError

from apps.assistant.enums import DEFAULT_INTENT
from apps.assistant.models.thread import Thread
from apps.assistant.query_adapters import build_user_network_context, get_docusafe_file_names
from apps.assistant.serializers.thread_settings import ThreadModuleSettingsData, coerce_thread_module_settings
from apps.docusafe.models.file import DocusafeFile
from shared.enums import DocusafeStatus

logger = structlog.get_logger("default")


@dataclass(frozen=True)
class ThreadSpecialization:
    module_name: str | None
    intent_name: str

    def matches_module_settings(self, module_settings: ThreadModuleSettingsData | None) -> bool:
        if self.module_name is None:
            return module_settings is None or module_settings.module_name is None
        return module_settings is not None and module_settings.module_name == self.module_name

    def build_context(self, thread: Thread | None, user_id: str | None) -> str:
        return ""

    def validate_module_settings(
        self, value: ThreadModuleSettingsData, user_id: str | None
    ) -> ThreadModuleSettingsData:
        return value


class DefaultThreadSpecialization(ThreadSpecialization):
    def build_context(self, thread: Thread | None, user_id: str | None) -> str:
        if not user_id:
            return ""
        return build_user_network_context(user_id)


class DocusafeThreadSpecialization(ThreadSpecialization):
    def build_context(self, thread: Thread | None, user_id: str | None) -> str:
        raw_module_settings = thread.module_settings if thread else None
        module_settings = coerce_thread_module_settings(cast(Mapping[str, object] | None, raw_module_settings))
        file_names = get_docusafe_file_names(list(module_settings.docusafe_file_ids))
        if not file_names:
            return ""

        return (
            "DOCUSAFE CONTEXT: The user has explicitly attached the following documents "
            f"to this chat thread: {', '.join(file_names)}."
        )

    def validate_module_settings(
        self, value: ThreadModuleSettingsData, user_id: str | None
    ) -> ThreadModuleSettingsData:
        file_ids = value.docusafe_file_ids
        if not file_ids or not user_id:
            return value

        valid_ids = DocusafeFile.objects.filter(
            id__in=file_ids,
            owner_id=user_id,
            status=DocusafeStatus.ACTIVE,
        ).values_list("id", flat=True)

        valid_str_ids = {str(file_id) for file_id in valid_ids}
        invalid_ids = [str(file_id) for file_id in file_ids if str(file_id) not in valid_str_ids]
        if invalid_ids:
            raise ValidationError(f"Invalid or inaccessible Docusafe files: {', '.join(invalid_ids)}")

        return value


_SPECIALIZATIONS: tuple[ThreadSpecialization, ...] = (
    DocusafeThreadSpecialization(module_name="docusafe", intent_name="docusafe_qa"),
    DefaultThreadSpecialization(module_name=None, intent_name=DEFAULT_INTENT),
)


def get_thread_specialization(thread: Thread | None) -> ThreadSpecialization:
    raw_module_settings = thread.module_settings if thread else None
    module_settings = coerce_thread_module_settings(cast(Mapping[str, object] | None, raw_module_settings))
    return get_specialization_for_module_settings(module_settings)


def get_specialization_for_module_settings(
    module_settings: ThreadModuleSettingsData | dict | None,
) -> ThreadSpecialization:
    normalized_settings = coerce_thread_module_settings(module_settings)
    for specialization in _SPECIALIZATIONS:
        if specialization.matches_module_settings(normalized_settings):
            return specialization
    return _SPECIALIZATIONS[-1]


def resolve_thread_intent(thread: Thread | None) -> str:
    return get_thread_specialization(thread).intent_name


def get_enriched_system_prompt(base_prompt: str, thread: Thread | None, user_id: str | None = None) -> str:
    specialization = get_thread_specialization(thread)
    try:
        block = specialization.build_context(thread, user_id)
    except Exception:
        logger.exception(
            "Thread specialization context failed",
            specialization=type(specialization).__name__,
            intent=specialization.intent_name,
        )
        return base_prompt

    if not block:
        return base_prompt
    return f"{base_prompt}\n\n{block}"


def validate_module_settings(
    value: ThreadModuleSettingsData | dict | None, user_id: str | None = None
) -> ThreadModuleSettingsData:
    normalized_value = coerce_thread_module_settings(value)
    specialization = get_specialization_for_module_settings(normalized_value)
    return specialization.validate_module_settings(normalized_value, user_id)

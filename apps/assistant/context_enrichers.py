"""Compatibility wrapper for assistant prompt enrichment."""

from apps.assistant.models.thread import Thread
from apps.assistant.thread_specializations import get_enriched_system_prompt as build_specialized_prompt


def get_enriched_system_prompt(
    intent_name: str,
    base_prompt: str,
    thread: Thread | None,
    user_id: str | None = None,
) -> str:
    del intent_name
    return build_specialized_prompt(base_prompt, thread, user_id)

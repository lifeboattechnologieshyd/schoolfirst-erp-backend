from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from apps.assistant.models import Thread
from apps.assistant.tools.catalog import get_tool_map


def resolve_allowed_tool_names(thread: Thread | None, allowed_tool_names: list[str]) -> list[str]:
    resolved_names = list(allowed_tool_names)
    thread_settings = cast(Mapping[str, object] | None, thread.settings if thread else None)

    if thread_settings and thread_settings.get("enabled_web_search", True) is False and "web_search" in resolved_names:
        resolved_names.remove("web_search")

    return resolved_names


def get_tools_for_thread(thread: Thread | None, allowed_tool_names: list[str]) -> list[Any]:
    tool_map = get_tool_map()
    resolved_names = resolve_allowed_tool_names(thread, allowed_tool_names)
    return [tool_map[name] for name in resolved_names if name in tool_map]

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from langchain_core.runnables import RunnableConfig

from .context import ToolContext
from .runtime import ToolTimeoutPolicy, resolve_timeout_seconds, run_with_timeout

ToolResultT = TypeVar("ToolResultT")


class ToolExecution:
    def __init__(
        self,
        name: str,
        tool_call_id: str,
        config: RunnableConfig,
        input_data: dict[str, Any],
        start_progress: str,
        timeout_policy: ToolTimeoutPolicy,
        requested_timeout: int | None,
    ) -> None:
        self.timeout_seconds = resolve_timeout_seconds(requested_timeout, timeout_policy)
        payload = dict(input_data)
        payload.setdefault("timeout", self.timeout_seconds)
        self._context = ToolContext(name, tool_call_id, payload, config, start_progress)

    def __enter__(self) -> ToolExecution:
        self._context.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return self._context.__exit__(exc_type, exc_val, exc_tb)

    @property
    def user_id(self):
        return self._context.user_id

    @property
    def thread_id(self):
        return self._context.thread_id

    def no_user(self) -> str:
        return self._context.no_user()

    def run(self, fn: Callable[..., ToolResultT], *args: Any, **kwargs: Any) -> ToolResultT:
        return cast(ToolResultT, run_with_timeout(self.timeout_seconds, fn, *args, **kwargs))

    def stop(self, result: dict, progress: str, response_text: str) -> str:
        self._context.stop(result, progress)
        return response_text

    def fail(self, error: str, progress: str, response_text: str) -> str:
        self._context.error(error, progress)
        return response_text

    def timeout(self, error: str, response_text: str) -> str:
        self._context.error(error, f"Timed out after {self.timeout_seconds:g}s")
        return response_text

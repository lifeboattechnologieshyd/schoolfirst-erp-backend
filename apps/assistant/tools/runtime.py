"""Shared runtime helpers for assistant tools."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from queue import Queue


@dataclass(frozen=True)
class ToolTimeoutPolicy:
    """Timeout policy declared by a tool definition."""

    default_timeout_seconds: float
    max_timeout_seconds: float | None = None


class ToolTimeoutError(TimeoutError):
    """Raised when a tool exceeds its allowed runtime."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Tool timed out after {timeout_seconds:g}s")


@dataclass(frozen=True)
class _ToolResult:
    value: object | None = None
    error: BaseException | None = None


def resolve_timeout_seconds(requested_timeout: int | float | None, policy: ToolTimeoutPolicy) -> float:
    """Return the effective timeout for a tool invocation."""
    timeout_seconds = policy.default_timeout_seconds

    if requested_timeout is not None and requested_timeout > 0:
        timeout_seconds = float(requested_timeout)

    if policy.max_timeout_seconds is not None:
        timeout_seconds = min(timeout_seconds, policy.max_timeout_seconds)

    return timeout_seconds


def run_with_timeout(timeout_seconds: int | float, fn: Callable[..., object], *args, **kwargs) -> object:
    """Run ``fn`` in a daemon thread and stop waiting after ``timeout_seconds``."""
    result_queue: Queue[_ToolResult] = Queue(maxsize=1)

    def _runner() -> None:
        try:
            result_queue.put(_ToolResult(value=fn(*args, **kwargs)))
        except BaseException as exc:  # noqa: BLE001
            result_queue.put(_ToolResult(error=exc))

    worker = threading.Thread(target=_runner, name="assistant-tool-runtime", daemon=True)
    worker.start()
    worker.join(timeout_seconds)

    if worker.is_alive():
        raise ToolTimeoutError(timeout_seconds)

    result = result_queue.get_nowait()
    if result.error is not None:
        raise result.error

    return result.value

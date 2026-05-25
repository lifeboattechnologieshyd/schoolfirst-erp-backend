"""
Tool execution context.

Provides ``ToolContext`` — a lightweight context manager that owns the three
concerns common to every assistant tool:

  - acquiring the stream writer (with a safe no-op fallback)
  - extracting ``user_id`` from ``RunnableConfig``
  - emitting start, stop, and error events with a consistent shape

Usage::

    with ToolContext(  # noqa: W505
        "my_tool", tool_call_id, {"param": value}, config, "Working…"
    ) as ctx:
        if not ctx.user_id:
            return ctx.no_user()

        # ... business logic ...

        ctx.stop({"result": data}, "Done")
        return "result string"
"""

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer


class ToolContext:
    """Context manager for consistent tool event emission and user context.

    Acquires the stream writer and emits a ``start`` event on ``__enter__``.
    Exposes ``stop`` and ``error`` helpers for explicit event emission.
    Never suppresses exceptions — callers are responsible for catching them.
    """

    def __init__(
        self,
        name: str,
        tool_call_id: str,
        input_data: dict,
        config: RunnableConfig,
        start_progress: str,
    ) -> None:
        self.name = name
        self.tool_call_id = tool_call_id
        self.input_data = input_data
        self.user_id = config.get("configurable", {}).get("user_id")
        self.thread_id = config.get("configurable", {}).get("thread_id")
        self.writer = self._acquire_writer()
        self._start_progress = start_progress

    @staticmethod
    def _acquire_writer():
        try:
            return get_stream_writer()
        except Exception:
            return lambda _: None  # noqa: E731 — safe no-op outside streaming context

    def __enter__(self) -> ToolContext:
        self.writer(
            {
                "type": "tool_call",
                "status": "start",
                "name": self.name,
                "id": self.tool_call_id,
                "input": self.input_data,
                "progress": self._start_progress,
            }
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False  # Never suppress exceptions

    def stop(self, result: dict, progress: str) -> None:
        """Emit a stop event with the given result and progress label."""
        self.writer(
            {
                "type": "tool_call",
                "status": "stop",
                "name": self.name,
                "id": self.tool_call_id,
                "input": self.input_data,
                "result": result,
                "progress": progress,
            }
        )

    def error(self, error: str, progress: str) -> None:
        """Emit an error event."""
        self.writer(
            {
                "type": "tool_call",
                "status": "error",
                "name": self.name,
                "id": self.tool_call_id,
                "input": self.input_data,
                "error": error,
                "progress": progress,
            }
        )

    def no_user(self) -> str:
        """Emit a user-context-missing error and return the standard message."""
        self.error("User context missing", "Failed — no user context")
        return "I'm sorry, I don't have access to your user information right now."

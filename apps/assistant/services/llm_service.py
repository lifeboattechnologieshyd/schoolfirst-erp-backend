"""
LLM Service handles interactions with Large Language Models via LangGraph.
Provides high-level methods for generating full or streaming responses,
as well as auto-titling threads.
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

import structlog
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

from apps.assistant.content_blocks import build_content_blocks_from_messages
from apps.assistant.enums import DEFAULT_INTENT, DEFAULT_THREAD_NAME
from apps.assistant.graph.builder import build_graph
from apps.assistant.models import Thread
from apps.assistant.services.llm_factory import generate_thread_title
from shared.utils import chunk_text, strip_thinking_blocks

logger = structlog.get_logger("default")

_llm_service_instance: LLMService | None = None


@dataclass(frozen=True)
class LLMResponsePayload:
    text: str
    intent_name: str
    content_blocks: tuple[dict[str, Any], ...] = ()


def get_llm_service() -> LLMService:
    """Return a cached LLMService instance (builds the graph once per process)."""
    global _llm_service_instance  # noqa: PLW0603
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance


class LLMService:
    """
    Service layer to handle LLM interactions using LangGraph.
    """

    def __init__(self) -> None:
        logger.info("Initializing LLMService")

    @staticmethod
    def _build_graph() -> Any:
        """Return a fresh compiled graph for each request-scoped invocation."""
        return build_graph()

    def generate_response(
        self, messages: list[BaseMessage], thread_id: str | uuid.UUID, user_id: uuid.UUID | None = None
    ) -> LLMResponsePayload:
        """
        Generates a full (non-streaming) response from the LangGraph.
        """
        logger.debug("Starting direct graph invocation", message_count=len(messages), user_id=user_id)
        state_input = {"messages": messages, "user_id": user_id}
        config = {"configurable": {"thread_id": str(thread_id), "user_id": user_id}}
        graph = self._build_graph()

        try:
            final_state = graph.invoke(state_input, config=config)
            logger.info("Graph invocation completed")

            # The final result is the last message
            output_messages = final_state.get("messages", [])
            if not output_messages:
                logger.error("Graph returned empty message list")
                return LLMResponsePayload(text="Error: No response generated", intent_name="error")

            final_msg = output_messages[-1]
            intent_name = final_state.get("intent_name", DEFAULT_INTENT)
            extracted_text = strip_thinking_blocks(self._extract_text_from_message(final_msg))

            original_len = len(messages)
            new_msgs = output_messages[original_len:] if len(output_messages) > original_len else [final_msg]
            content_blocks = build_content_blocks_from_messages(new_msgs, text_transform=strip_thinking_blocks)

            return LLMResponsePayload(
                text=extracted_text,
                intent_name=intent_name,
                content_blocks=tuple(content_blocks),
            )
        except Exception as e:
            logger.exception("Graph invocation failed", error=str(e))
            raise

    def generate_streaming_response(
        self, messages: list[BaseMessage], thread_id: str | uuid.UUID, user_id: uuid.UUID | None = None
    ) -> Iterator[str | dict]:
        """
        Stream the LLM response using LangGraph's dual-mode streaming.
        """
        logger.debug("Starting streaming graph execution", message_count=len(messages), user_id=user_id)
        state_input = {"messages": messages, "user_id": user_id}
        config = {"configurable": {"thread_id": str(thread_id), "user_id": user_id}}
        graph = self._build_graph()

        # State tracking for the stream
        ctx = {"yield_count": 0, "tool_completed": False, "custom_text_after_tool": False}

        try:
            for mode, event in graph.stream(state_input, config=config, stream_mode=["custom", "values"]):
                if not event:
                    continue

                if mode == "custom":
                    yield from self._handle_custom_stream_event(event, ctx)
                elif mode == "values" and ctx["tool_completed"]:
                    yield from self._handle_values_stream_event(event, ctx)

            logger.info("Streaming graph execution completed", total_yields=ctx["yield_count"])

        except Exception as e:
            logger.exception("Streaming graph execution failed", error=str(e))
            yield {"type": "error", "message": "An error occurred. Please try again."}

    # ------------------------------------------------------------------
    # Stream Event Handlers
    # ------------------------------------------------------------------

    def _handle_custom_stream_event(self, event: dict[str, Any], ctx: dict[str, Any]) -> Iterator[str | dict]:
        """Handles 'custom' mode events (tokens, tool calls, intents)."""
        event_type = event.get("type")

        if event_type == "text":
            content = event.get("content", "")
            if content:
                ctx["yield_count"] += 1
                yield content
                if ctx["tool_completed"]:
                    ctx["custom_text_after_tool"] = True

        elif event_type == "tool_call":
            if event.get("status") == "stop":
                ctx["tool_completed"] = True
                ctx["custom_text_after_tool"] = False
            yield event

        elif event_type in ("intent_selected", "thread_updated", "usage"):
            yield event

    def _handle_values_stream_event(self, event: dict[str, Any], ctx: dict[str, Any]) -> Iterator[str | dict]:
        """Handles 'values' mode events (state snapshots) as fallback."""
        if ctx["custom_text_after_tool"]:
            ctx["tool_completed"] = False
            ctx["custom_text_after_tool"] = False
            return

        state_messages = event.get("messages", [])
        if not state_messages or not isinstance(state_messages[-1], AIMessage):
            return

        content = self._extract_text_from_message(state_messages[-1])
        content = strip_thinking_blocks(content)

        if content:
            logger.info("Emitting post-tool synthesis from values snapshot (fallback)")
            yield from chunk_text(content)

        ctx["tool_completed"] = False
        ctx["custom_text_after_tool"] = False

    # ------------------------------------------------------------------
    # Title Generation
    # ------------------------------------------------------------------

    def auto_title(
        self,
        thread: Thread,
        first_message_content: str,
        config: RunnableConfig | dict[str, object] | None = None,
    ) -> str | None:
        """
        Generate a thread title from the first message content
        if it matches the default name.

        Args:
            thread: The Thread instance to update.
            first_message_content: The content of the first message.
            config: Optional RunnableConfig for LangChain.
        """
        if thread.name == DEFAULT_THREAD_NAME:
            try:
                new_title = self.generate_thread_title(first_message_content, config=config)
                thread.name = cast(Any, new_title)
                thread.save(update_fields=["name", "updated_at"])
                return new_title
            except Exception as e:
                logger.exception("Error generating thread title", error=str(e))
        return None

    def generate_thread_title(
        self, message_content: str, config: RunnableConfig | dict[str, object] | None = None
    ) -> str:
        """Generate a concise thread title. Delegates to the factory function."""
        return generate_thread_title(message_content, config=config)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text_from_message(message: BaseMessage) -> str:
        """Extract plain text from a LangChain message's content field."""
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
            )
        return str(content)

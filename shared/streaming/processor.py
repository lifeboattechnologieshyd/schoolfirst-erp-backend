"""
Stream processor: transforms raw LLM output (text chunks + structured tool events)
into a unified content block SSE event format.

Event sequence emitted (with tool calls):
  message_start
        -> tool_call (status="start", name="web_search", input={"query":"..."})
        -> tool_call (status="stop", input={...}, result={...})
    -> content_block_start (type="text")
      -> content_block_delta (text_delta) x N
    -> content_block_stop
  -> message_delta (stop_reason, usage)
  -> message_stop

Storage: tool_call start+stop collapse into a single block with result inline.
SSE: start and stop events are emitted separately for live UI rendering.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field

import structlog

from .sse import (
    build_content_block_start,
    build_content_block_stop,
    build_intent_selected,
    build_message_delta,
    build_message_start,
    build_message_stop,
    build_text_delta,
    build_thread_updated,
    build_tool_call_error,
    build_tool_call_start,
    build_tool_call_stop,
)

logger = structlog.get_logger("default")


@dataclass
class StreamState:
    """Tracks state during content block stream processing."""

    message_id: str
    model: str
    block_index: int = 0
    accumulated_text: str = ""
    token_count: int = 0  # Fallback rough estimate mapped from len(text)
    usage_metadata: dict | None = None
    text_block_open: bool = False
    # Thinking-block filter state
    in_thinking_block: bool = False
    thinking_tail: str = ""  # buffers up to 10 chars to detect split <thinking> tags
    stop_reason: str = "end_turn"
    # Persistence accumulators
    content_blocks: list = field(default_factory=list)  # ordered typed blocks for DB
    current_text_block: dict | None = None  # open text block awaiting close
    pending_tool_calls: dict = field(default_factory=dict)  # id -> {name, input, progress}


class ContentBlockStreamProcessor:
    """
    Transforms raw LLM output into a unified content block SSE event format.

    Handles tool_call events (start/stop/error) and text content blocks.
    SSE events are emitted with start/stop lifecycle for live UI rendering.
    Persistence uses collapsed single-block format per tool call.
    """

    def __init__(self, message_id: str, model: str):
        self.state = StreamState(message_id=message_id, model=model)
        logger.info("ContentBlockStreamProcessor initialized", message_id=message_id, model=model)

    def process_stream(  # noqa: PLR0912, PLR0915
        self,
        raw_stream: Iterator[str | dict],
        thread_title: str | None = None,
    ) -> Iterator[str]:
        """
        Process raw LLM stream into content block SSE events.
        """
        logger.debug("Starting stream processing")
        yield build_message_start(
            message_id=self.state.message_id,
            model=self.state.model,
        )

        if thread_title:
            logger.info("Emitting thread title update", title=thread_title)
            yield build_thread_updated(name=thread_title)

        try:
            for chunk in raw_stream:
                if not chunk:
                    continue
                if isinstance(chunk, str):
                    yield from self._process_text(chunk)
                elif isinstance(chunk, dict):
                    yield from self._dispatch_dict_chunk(chunk)

            # Flush any text buffered in thinking_tail
            yield from self._flush_thinking_tail()

            # Close any open text block
            if self.state.text_block_open:
                logger.debug("Closing text block on stream end")
                yield build_content_block_stop(index=self.state.block_index)
                self.state.text_block_open = False

            yield build_message_delta(
                stop_reason=self.state.stop_reason,
                usage=self.state.usage_metadata or {"output_tokens": self.state.token_count},
            )
            logger.info(
                "Stream processing completed successfully",
                usage=self.state.usage_metadata,
                fallback_tokens=self.state.token_count,
            )
        except Exception as e:
            logger.exception("Stream processing error", error=str(e))
            if self.state.text_block_open:
                yield build_content_block_stop(index=self.state.block_index)
                self.state.text_block_open = False
            yield build_message_delta(stop_reason="error")
        finally:
            yield build_message_stop()
            logger.debug("Stream processing finalized (message_stop emitted)")

    def _dispatch_dict_chunk(self, chunk: dict) -> Iterator[str]:
        """Route a dict chunk to the correct handler based on its type."""
        chunk_type = chunk.get("type")
        if chunk_type == "tool_call":
            yield from self._dispatch_tool_call_chunk(chunk)
        elif chunk_type == "usage":
            self._merge_usage_metadata(chunk)
        elif chunk_type == "intent_selected":
            intent_name = chunk.get("intent_name")
            logger.info("Intent selected", intent_name=intent_name)
            if isinstance(intent_name, str):
                yield build_intent_selected(intent_name=intent_name)
        elif chunk_type == "thread_updated":
            title = chunk.get("name")
            logger.info("Emitting thread title update", title=title)
            if isinstance(title, str):
                yield build_thread_updated(name=title)
        else:
            logger.warning("Unknown chunk type received", chunk_type=chunk_type)

    def _dispatch_tool_call_chunk(self, chunk: dict) -> Iterator[str]:
        status = chunk.get("status")
        tool_name = chunk.get("name", "unknown")
        tool_id = chunk.get("id", "")
        if status == "start":
            yield from self._handle_tool_start(
                id=tool_id,
                name=tool_name,
                input=chunk.get("input"),
                progress=chunk.get("progress", ""),
            )
            return

        if status == "stop":
            results = chunk.get("results")
            if results is None and isinstance(chunk.get("result"), dict):
                results = chunk["result"].get("data")
            results = results or []

            yield from self._handle_tool_stop(
                id=tool_id,
                name=tool_name,
                input=chunk.get("input"),
                result=chunk.get("result"),
                results=results,
                response_time=chunk.get("response_time"),
                progress=chunk.get("progress", ""),
            )
            return

        if status == "error":
            yield from self._handle_tool_error(
                id=tool_id,
                name=tool_name,
                error=chunk.get("error", "Unknown error"),
                progress=chunk.get("progress", "Error"),
            )
            return

        logger.warning("Unknown tool_call status", status=status, name=tool_name)

    def _merge_usage_metadata(self, chunk: dict) -> None:
        # Combine newly reported usage metadata with any previously
        # accumulated usage.
        reported_usage = chunk.get("usage", {})
        if self.state.usage_metadata is None:
            self.state.usage_metadata = reported_usage
            return

        self.state.usage_metadata["input_tokens"] = self.state.usage_metadata.get(
            "input_tokens", 0
        ) + reported_usage.get("input_tokens", 0)
        self.state.usage_metadata["output_tokens"] = self.state.usage_metadata.get(
            "output_tokens", 0
        ) + reported_usage.get("output_tokens", 0)

    def _handle_tool_start(
        self,
        *,
        id: str,  # noqa: A002
        name: str,
        input: dict | None,  # noqa: A002
        progress: str = "",
    ) -> Iterator[str]:
        """
        Emit a tool_call start event.
        Registers the tool call as pending for later collapse on stop.
        """
        # Flush any text held back by thinking-block filter
        # so it doesn't leak into the next block
        yield from self._flush_thinking_tail()

        # Close any open text block before a tool call
        if self.state.text_block_open:
            yield build_content_block_stop(index=self.state.block_index)
            self.state.text_block_open = False
            # Finalise the in-progress text block so it is stored correctly
            if self.state.current_text_block is not None:
                self.state.current_text_block = None

        input_payload = input or {}  # noqa: A002
        logger.info("Emitting tool_call start", name=name, id=id, input=input_payload)

        # Register as pending — will be collapsed into a single block on stop
        self.state.pending_tool_calls[id] = {
            "name": name,
            "input": input_payload,
            "progress": progress,
        }

        icon_map = {"web_search": "globe", "fetch_user_details": "user"}

        yield build_tool_call_start(
            id=id,
            name=name,
            input=input_payload,
            progress=progress,
            icon=icon_map.get(name, "tool"),
        )

    def _handle_tool_stop(
        self,
        *,
        id: str,  # noqa: A002
        name: str,
        input: dict | None,  # noqa: A002
        result: dict | None,
        results: list[dict],
        response_time: float | None,
        progress: str = "",
    ) -> Iterator[str]:
        """Emit a tool_call stop event and collapse into a single stored block."""
        normalized_data = self._normalize_tool_data(results)
        input_payload = input or self._get_tool_input(id) or {}
        result_payload = (
            result
            if result is not None
            else {
                "response_time": response_time,
                "data": normalized_data,
            }
        )

        # Remove from pending
        self.state.pending_tool_calls.pop(id, None)
        logger.info(
            "Emitting tool_call stop",
            name=name,
            id=id,
            data_count=len(normalized_data),
        )

        # Collapse into a single stored block for DB persistence
        self.state.block_index += 1
        collapsed_block = {
            "type": "tool_call",
            "id": id,
            "name": name,
            "input": input_payload,
            "result": {
                "status": "success",
                **result_payload,
            },
            "progress_label": progress,
            "index": self.state.block_index,
        }
        self.state.content_blocks.append(collapsed_block)

        yield build_tool_call_stop(
            id=id,
            name=name,
            progress=progress,
            input=input_payload,
            result=result_payload,
        )

    @staticmethod
    def _normalize_tool_data(results: list[dict]) -> list[dict]:
        """
        Return raw tool output rows for persistence when provider
        did not send explicit result payload.
        """
        return list(results)

    def _handle_tool_error(
        self,
        *,
        id: str,  # noqa: A002
        name: str,
        error: str,
        progress: str = "",
    ) -> Iterator[str]:
        """Emit a tool_call error event and store collapsed error block."""
        # Remove from pending
        input_payload = self._get_tool_input(id) or {}
        self.state.pending_tool_calls.pop(id, None)
        logger.warning("Emitting tool_call error", name=name, id=id, error=error)

        # Collapse into a single stored block with error result
        collapsed_block = {
            "type": "tool_call",
            "id": id,
            "name": name,
            "input": input_payload,
            "result": {
                "status": "error",
                "error_message": error,
            },
            "progress_label": progress,
        }
        self.state.content_blocks.append(collapsed_block)

        yield build_tool_call_error(
            id=id,
            name=name,
            error=error,
            progress=progress,
        )

    def _get_tool_input(self, id: str) -> dict | None:  # noqa: A002
        """Return the input payload from a pending tool call."""
        pending = self.state.pending_tool_calls.get(id)
        if pending:
            return pending.get("input")
        return None

    def _process_text(self, text: str) -> Iterator[str]:
        """Process a text chunk, filtering out <thinking> blocks before emitting."""
        # Prepend any buffered tail from the previous chunk to handle split tags
        text = self.state.thinking_tail + text
        self.state.thinking_tail = ""

        output_parts: list[str] = []

        while text:
            if self.state.in_thinking_block:
                end = text.find("</thinking>")
                if end == -1:
                    # Closing tag not found in this chunk. Buffer the last N chars in
                    # case the tag is split across chunk boundaries
                    # (e.g. "</think" ends one chunk and "ing>" starts the next).
                    # len("</thinking") == 11 — one char short of the full closing tag.
                    tail_len = len("</thinking>") - 1  # 11
                    self.state.thinking_tail = text[-tail_len:] if len(text) >= tail_len else text
                    text = ""
                else:
                    # Found the closing tag - resume after it
                    text = text[end + len("</thinking>") :]
                    self.state.in_thinking_block = False
            else:
                start = text.find("<thinking>")
                if start == -1:
                    # No thinking tag - check if tail could be a partial tag
                    tail_offset = max(0, len(text) - 9)  # len("<thinking") == 9
                    self.state.thinking_tail = text[tail_offset:]
                    safe = text[:tail_offset]
                    if safe:
                        output_parts.append(safe)
                    text = ""
                else:
                    # Found start of thinking block - emit everything before it
                    if start > 0:
                        output_parts.append(text[:start])
                    text = text[start + len("<thinking>") :]
                    self.state.in_thinking_block = True

        safe_text = "".join(output_parts)
        if not safe_text:
            return

        self.state.accumulated_text += safe_text
        self.state.token_count += max(1, len(safe_text) // 4)  # Rough estimate

        yield from self._ensure_text_block()

        # Append text delta into the current block accumulator for DB persistence
        if self.state.current_text_block is not None:
            self.state.current_text_block["text"] += safe_text

        for chunk in self._split_text_delta_chunks(safe_text):
            yield build_text_delta(index=self.state.block_index, text=chunk)

    @staticmethod
    def _split_text_delta_chunks(text: str, target_chunk_size: int = 48) -> list[str]:
        """Split a text payload into smaller chunks for smoother SSE rendering."""
        if len(text) <= target_chunk_size:
            return [text]

        parts: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= target_chunk_size:
                parts.append(remaining)
                break

            split_at = remaining.rfind(" ", 0, target_chunk_size + 1)
            if split_at <= 0:
                split_at = target_chunk_size

            parts.append(remaining[:split_at])
            remaining = remaining[split_at:]

        return [p for p in parts if p]

    def _flush_thinking_tail(self) -> Iterator[str]:
        """Emit any characters held back by the thinking-block filter."""
        if self.state.thinking_tail and not self.state.in_thinking_block:
            tail = self.state.thinking_tail
            self.state.thinking_tail = ""

            self.state.accumulated_text += tail
            self.state.token_count += max(1, len(tail) // 4)

            yield from self._ensure_text_block()
            if self.state.current_text_block is not None:
                self.state.current_text_block["text"] += tail

            yield build_text_delta(index=self.state.block_index, text=tail)

    def _ensure_text_block(self) -> Iterator[str]:
        """Open a text content block if one isn't already open."""
        if not self.state.text_block_open:
            self.state.block_index += 1
            self.state.text_block_open = True
            # Open a new text block accumulator for DB persistence
            self.state.current_text_block = {
                "type": "text",
                "text": "",
                "index": self.state.block_index,
            }
            self.state.content_blocks.append(self.state.current_text_block)
            logger.debug("Opening new text block", index=self.state.block_index)
            yield build_content_block_start(
                index=self.state.block_index,
                block_type="text",
            )

    def get_accumulated_response(self) -> str:
        """Get the full accumulated response text."""
        return self.state.accumulated_text

    def get_stop_reason(self) -> str:
        """Get the final stop reason."""
        return self.state.stop_reason

    def get_content_blocks(self) -> list:
        """Return the ordered typed content block list for DB persistence."""
        return self.state.content_blocks

    def get_role_metadata(self) -> dict:
        """Return role_metadata dict for DB persistence."""
        return {
            "stop_reason": self.state.stop_reason,
            "model": self.state.model,
            "usage": self.state.usage_metadata or {"output_tokens": self.state.token_count},
        }

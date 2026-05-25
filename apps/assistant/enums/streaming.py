from enum import StrEnum


class StreamEventType(StrEnum):
    """SSE event types — Claude content block streaming model."""

    MESSAGE_START = "message_start"
    CONTENT_BLOCK_START = "content_block_start"
    CONTENT_BLOCK_DELTA = "content_block_delta"
    CONTENT_BLOCK_STOP = "content_block_stop"
    MESSAGE_DELTA = "message_delta"
    MESSAGE_STOP = "message_stop"
    THREAD_UPDATED = "thread_updated"
    INTENT_SELECTED = "intent_selected"
    TOOL_CALL = "tool_call"
    ERROR = "error"


class ContentBlockType(StrEnum):
    """Content block types."""

    TEXT = "text"
    TOOL_USE = "tool_call"
    TOOL_RESULT = "tool_result"


class DeltaType(StrEnum):
    """Delta types within content block deltas."""

    TEXT_DELTA = "text_delta"
    INPUT_JSON_DELTA = "input_json_delta"


class ToolCallStatus(StrEnum):
    """Status values for tool_call SSE events."""

    START = "start"
    UPDATE = "update"
    STOP = "stop"
    ERROR = "error"

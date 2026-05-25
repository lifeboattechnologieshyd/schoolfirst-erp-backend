"""
SSE event builders for a unified content block streaming model.

Produces Server-Sent Events matching a unified content block model:
  message_start
    -> content_block_start (type=text)
      -> content_block_delta (text_delta) x N
    -> content_block_stop
  -> message_delta (stop_reason, usage)
  -> message_stop
"""

import json
from typing import Any

from apps.assistant.enums.streaming import DeltaType, StreamEventType, ToolCallStatus


def _sse(event_type: StreamEventType, payload: dict) -> str:
    """Serialize a structured payload to SSE wire format."""
    return f"event: {event_type.value}\ndata: {json.dumps(payload)}\n\n"


# ------------------------------------------------------------------
# Message-level events
# ------------------------------------------------------------------


def build_message_start(*, message_id: str, model: str) -> str:
    """
    Emit message_start — initializes the message object.

    Format:
        event: message_start
        data: {"type":"message_start","message":{"id":"...","type":"message",
               "role":"assistant","model":"...","content":[],"stop_reason":null}}
    """
    return _sse(
        StreamEventType.MESSAGE_START,
        {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "stop_reason": None,
            },
        },
    )


def build_message_delta(
    *,
    stop_reason: str = "end_turn",
    usage: dict[str, int] | None = None,
) -> str:
    """
    Emit message_delta — final message-level update (stop reason + usage).

    Format:
        event: message_delta
        data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},
               "usage":{"output_tokens":150}}
    """
    payload: dict[str, Any] = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason},
    }
    if usage:
        payload["usage"] = usage
    return _sse(StreamEventType.MESSAGE_DELTA, payload)


def build_message_stop() -> str:
    """
    Emit message_stop — stream terminator.

    Format:
        event: message_stop
        data: {"type":"message_stop"}
    """
    return _sse(StreamEventType.MESSAGE_STOP, {"type": "message_stop"})


# ------------------------------------------------------------------
# Content block events
# ------------------------------------------------------------------


def build_content_block_start(*, index: int, block_type: str, **kwargs: Any) -> str:
    """
    Emit content_block_start — opens a new content block.

    Format:
        event: content_block_start
        data: {"type":"content_block_start","index":0,
               "content_block":{"type":"text","text":""}}
    """
    content_block: dict[str, Any] = {"type": block_type, **kwargs}
    if block_type == "text":
        content_block.setdefault("text", "")
    return _sse(
        StreamEventType.CONTENT_BLOCK_START,
        {
            "type": "content_block_start",
            "index": index,
            "content_block": content_block,
        },
    )


def build_content_block_stop(*, index: int) -> str:
    """
    Emit content_block_stop — closes a content block.

    Format:
        event: content_block_stop
        data: {"type":"content_block_stop","index":0}
    """
    return _sse(
        StreamEventType.CONTENT_BLOCK_STOP,
        {
            "type": "content_block_stop",
            "index": index,
        },
    )


# ------------------------------------------------------------------
# Content block delta events
# ------------------------------------------------------------------


def build_text_delta(*, index: int, text: str) -> str:
    """
    Emit text_delta — append text to the current content block.

    Format:
        event: content_block_delta
        data: {"type":"content_block_delta","index":0,
               "delta":{"type":"text_delta","text":"Hello"}}
    """
    return _sse(
        StreamEventType.CONTENT_BLOCK_DELTA,
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {
                "type": DeltaType.TEXT_DELTA.value,
                "text": text,
            },
        },
    )


def build_input_json_delta(*, index: int, partial_json: str) -> str:
    """
    Emit input_json_delta — append JSON fragment to a tool_call or tool_result block.

    Used to stream tool input (e.g. web search query) or tool output
    (e.g. knowledge items) incrementally.

    Format:
        event: content_block_delta
        data: {"type":"content_block_delta","index":0,
               "delta":{"type":"input_json_delta","partial_json":"{...}"}}
    """
    return _sse(
        StreamEventType.CONTENT_BLOCK_DELTA,
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {
                "type": DeltaType.INPUT_JSON_DELTA.value,
                "partial_json": partial_json,
            },
        },
    )


# ------------------------------------------------------------------
# Error event
# ------------------------------------------------------------------


def build_thread_updated(*, name: str) -> str:
    """
    Emit thread_updated — notifies frontend of a title update.

    Format:
        event: thread_updated
        data: {"type":"thread_updated","name":"..."}
    """
    return _sse(StreamEventType.THREAD_UPDATED, {"type": "thread_updated", "name": name})


def build_intent_selected(*, intent_name: str) -> str:
    """
    Emit intent_selected — notifies frontend of the classified intent.

    Format:
        event: intent_selected
        data: {"type":"intent_selected","intent_name":"..."}
    """
    return _sse(StreamEventType.INTENT_SELECTED, {"type": "intent_selected", "intent_name": intent_name})


def build_error(*, error_type: str = "server_error", message: str) -> str:
    """
    Emit error event.

    Format:
        event: error
        data: {"type":"error","error":{"type":"server_error","message":"..."}}
    """
    return _sse(
        StreamEventType.ERROR,
        {
            "type": "error",
            "error": {"type": error_type, "message": message},
        },
    )


# ------------------------------------------------------------------
# Tool call events
# ------------------------------------------------------------------


def build_tool_call_start(
    *,
    id: str,  # noqa: A002
    name: str,
    input: dict,  # noqa: A002
    progress: str = "",
    icon: str = "tool",
) -> str:
    """
    Emit tool_call start — signals that a tool is beginning execution.

    Format:
        event: tool_call
        data: {"type":"tool_call","status":"start","id":"tc_xxx",
               "name":"web_search","input":{"query":"..."},
               "progress":"Searching the Web","icon":"globe"}
    """
    return _sse(
        StreamEventType.TOOL_CALL,
        {
            "type": "tool_call",
            "status": ToolCallStatus.START.value,
            "id": id,
            "name": name,
            "input": input,
            "progress": progress,
            "icon": icon,
        },
    )


def build_tool_call_update(
    *,
    id: str,  # noqa: A002
    name: str,
    progress: str,
    **extra,
) -> str:
    """
    Emit tool_call update — an intermediate status update during tool execution.

    Format:
        event: tool_call
        data: {"type":"tool_call","status":"update","id":"tc_xxx",
               "name":"web_search","progress":"..."}
    """
    payload = {
        "type": "tool_call",
        "status": ToolCallStatus.UPDATE.value,
        "id": id,
        "name": name,
        "progress": progress,
        **extra,
    }
    return _sse(StreamEventType.TOOL_CALL, payload)


def build_tool_call_stop(
    *,
    id: str,  # noqa: A002
    name: str,
    progress: str = "",
    input: dict | None = None,  # noqa: A002
    result: dict | None = None,
    **extra,
) -> str:
    """
    Emit tool_call stop — signals that a tool has finished execution.

    Format:
        event: tool_call
        data: {"type":"tool_call","status":"stop","id":"tc_xxx",
               "name":"web_search","progress":"Searched the Web",
               "input":{"query":"..."},"result":{"data":[...]}}
    """
    payload: dict[str, Any] = {
        "type": "tool_call",
        "status": ToolCallStatus.STOP.value,
        "id": id,
        "name": name,
        "progress": progress,
        **extra,
    }
    if input is not None:
        payload["input"] = input
    if result is not None:
        payload["result"] = result
    return _sse(StreamEventType.TOOL_CALL, payload)


def build_tool_call_error(
    *,
    id: str,  # noqa: A002
    name: str,
    error: str,
    **extra,
) -> str:
    """
    Emit tool_call error — signals that a tool failed.

    Format:
        event: tool_call
        data: {"type":"tool_call","status":"error","id":"tc_xxx",
               "name":"web_search","error":"..."}
    """
    payload = {
        "type": "tool_call",
        "status": ToolCallStatus.ERROR.value,
        "id": id,
        "name": name,
        "error": error,
        **extra,
    }
    return _sse(StreamEventType.TOOL_CALL, payload)

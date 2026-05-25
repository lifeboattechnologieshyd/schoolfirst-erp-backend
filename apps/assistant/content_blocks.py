from __future__ import annotations

import json
from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


def build_content_blocks_from_messages(
    messages: list[BaseMessage],
    text_transform: Callable[[str], str] | None = None,
) -> list[dict[str, object]]:
    transform = text_transform or (lambda text: text)
    content_blocks: list[dict[str, object]] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls:
                content_blocks.append(
                    {
                        "type": "tool_call",
                        "id": tool_call.get("id"),
                        "name": tool_call.get("name"),
                        "input": tool_call.get("args"),
                        "result": {"status": "success", "data": []},
                        "progress_label": "",
                    }
                )

            text_part = transform(_extract_text_from_message(message))
            if text_part.strip():
                content_blocks.append({"type": "text", "text": text_part})
            continue

        if getattr(message, "type", "") != "tool":
            continue

        for block in content_blocks:
            if block.get("type") == "tool_call" and block.get("id") == getattr(message, "tool_call_id", ""):
                block["result"] = {"status": "success", "data": [{"content": getattr(message, "content", "")}]}

    return content_blocks


def build_langchain_messages_from_assistant_blocks(content_blocks: list[dict], text_content: str) -> list[BaseMessage]:
    tool_call_blocks = [
        block for block in content_blocks if isinstance(block, dict) and block.get("type") == "tool_call"
    ]
    if not tool_call_blocks:
        return [AIMessage(content=text_content)] if text_content else []

    lc_tool_calls = []
    for block in tool_call_blocks:
        tool_call_id = block.get("id") or ""
        if not tool_call_id:
            continue
        lc_tool_calls.append(
            {
                "id": tool_call_id,
                "name": block.get("name", ""),
                "args": block.get("input") or {},
                "type": "tool_call",
            }
        )

    messages: list[BaseMessage] = [AIMessage(content=text_content or "", tool_calls=lc_tool_calls)]
    for block in tool_call_blocks:
        tool_call_id = block.get("id") or ""
        if not tool_call_id:
            continue
        result = block.get("result") or {}
        result_data = result.get("data") or []
        result_text = json.dumps(result_data) if result_data else "No data returned"
        messages.append(ToolMessage(content=result_text, tool_call_id=tool_call_id))

    return messages


def _extract_text_from_message(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)

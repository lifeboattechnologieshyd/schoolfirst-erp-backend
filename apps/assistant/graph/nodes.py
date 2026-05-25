"""
Nodes for the Assistant LangGraph.
Each function represents a computational step (node) in the graph.
"""

from typing import Any, cast

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.config import get_stream_writer

from apps.assistant.context_enrichers import get_enriched_system_prompt
from apps.assistant.enums import DEFAULT_INTENT, DEFAULT_THREAD_NAME
from apps.assistant.graph.state import AssistantState
from apps.assistant.intents.registry import (
    get_intent_by_name,
)
from apps.assistant.models import Thread
from apps.assistant.services.llm_factory import build_chat_llm, generate_thread_title
from apps.assistant.thread_specializations import resolve_thread_intent
from apps.assistant.tools import get_tools_for_thread

logger = structlog.get_logger("default")


def intent_router_node(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
    """
    Route the conversation to the correct intent handler.

    Two intents are currently active:
      - "docusafe_qa": for threads with module_name="docusafe" in module_settings
      - DEFAULT_INTENT ("schoolfirst_assistant"): for all other threads

    LLM-based multi-intent classification is not active. All non-docusafe threads
    are routed directly to the default intent.
    """
    logger.debug("Entering intent_router_node")

    thread_id = config.get("configurable", {}).get("thread_id")
    if thread_id:
        thread = Thread.objects.filter(id=thread_id).first()
        resolved_intent = resolve_thread_intent(thread)
        if resolved_intent != DEFAULT_INTENT:
            logger.info("Routing to specialized intent", intent=resolved_intent)
            return {"intent_name": resolved_intent, "confidence": 1.0}

    logger.info("Routing to default intent", intent=DEFAULT_INTENT)
    return {"intent_name": DEFAULT_INTENT, "confidence": 1.0}


def intent_handler_node(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
    """
    Generate a response for the classified intent.
    """
    intent_name = str(state.get("intent_name") or DEFAULT_INTENT)
    logger.debug("Entering intent_handler_node", intent=intent_name)

    intent_config = get_intent_by_name(intent_name) or get_intent_by_name(DEFAULT_INTENT)
    if not intent_config:
        logger.error("No intent config found (not even default)", intent=intent_name)
        return {"messages": [AIMessage(content="")]}

    llm = build_chat_llm(
        llm_config=intent_config.llm_config,
        temperature=intent_config.temperature,
        max_tokens=intent_config.max_output_tokens,
    )

    allowed_tool_names = list(intent_config.allowed_tools)

    thread_id = config.get("configurable", {}).get("thread_id")
    user_id = config.get("configurable", {}).get("user_id")
    thread = None
    if thread_id:
        thread = Thread.objects.filter(id=thread_id).first()

    allowed_tools = get_tools_for_thread(thread, allowed_tool_names)
    llm_with_tools = llm.bind_tools(allowed_tools) if allowed_tools else llm

    system_prompt = get_enriched_system_prompt(intent_name, intent_config.system_prompt, thread, user_id)

    messages_to_pass = [SystemMessage(content=system_prompt)] + state["messages"]

    writer = get_stream_writer()
    accumulated_chunks = []

    logger.info("Starting generation stream", intent=intent_name)

    # Only emit the intent event if this is the start of the interaction
    # (i.e. before any tools have been executed in this turn)
    if messages_to_pass and isinstance(messages_to_pass[-1], HumanMessage):
        writer({"type": "intent_selected", "intent_name": intent_name})

    for chunk in llm_with_tools.stream(messages_to_pass, config):
        accumulated_chunks.append(chunk)

        # Emit text content as structured custom stream events
        if content := chunk.content:
            if isinstance(content, str):
                writer({"type": "text", "content": content})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and (text := block.get("text")):
                        writer({"type": "text", "content": text})

        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            writer({"type": "usage", "usage": chunk.usage_metadata})

    if not accumulated_chunks:
        logger.warning("Node yielded no chunks", intent=intent_name)
        return {"messages": [AIMessage(content="")]}

    # Merge streamed chunks into a single message
    full_msg = _merge_chunks(accumulated_chunks)

    logger.info("Generation stream complete", intent=intent_name, total_chunks=len(accumulated_chunks))
    return {"messages": [full_msg], "intent_name": intent_name}


def _merge_chunks(chunks: list[Any]) -> AIMessage:
    """Merge message chunks while preserving metadata and tool calls."""
    if not chunks:
        return AIMessage(content="")

    full_msg = chunks[0]
    for chunk in chunks[1:]:
        full_msg = full_msg + chunk
    return full_msg


def generate_title_node(state: AssistantState, config: RunnableConfig) -> dict[str, Any]:
    """
    Generate a title for the thread if new. Runs in parallel with main router/handler.
    """
    logger.debug("Entering generate_title_node")

    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id:
        return {}

    thread = Thread.objects.filter(id=thread_id).first()
    if not thread or thread.name != DEFAULT_THREAD_NAME:
        return {}

    # Find the latest human message
    last_user_msg = next((m for m in reversed(state["messages"]) if getattr(m, "type", "") == "human"), None)
    if not last_user_msg:
        return {}

    content = last_user_msg.content
    if isinstance(content, list):
        text_parts = [
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        ]
        content = "".join(text_parts)

    new_title = generate_thread_title(content, config=config)

    if new_title:
        thread.name = cast(Any, new_title)
        thread.save(update_fields=["name", "updated_at"])
        writer = get_stream_writer()
        writer({"type": "thread_updated", "name": new_title})
        logger.info("Title generation complete, emitted to stream", title=new_title)

    return {}

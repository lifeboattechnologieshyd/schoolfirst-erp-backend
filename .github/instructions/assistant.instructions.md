---
description: "Use when working in the assistant app: chat threads, messages, LangGraph graph, intent routing, LLM tools, SSE streaming, or AWS Bedrock integration."
applyTo: "apps/assistant/**"
---

# Assistant App Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## Models

- `Thread` and `Message` use `TimeAuditModel` (timestamps only — no `created_by`/`updated_by` user audit fields).
- `Message.content_blocks` is a JSON list in **v2 format**:
  - Text: `{"type": "text", "text": "..."}`
  - Tool call: `{"type": "tool_call", "id": "...", "name": "...", "input": {...}, "result": {...}, "progress_label": ""}`
- Validate `Message.content_blocks` as: a JSON array of objects, each object must include a string `type`, and each block must match one supported v2 shape. If payload is malformed JSON or a block shape is invalid, return a validation error instead of coercing values.
- `Thread.settings` JSON is validated through `ThreadSettingsSerializer`.
- `Thread.module_settings` holds per-module context (e.g. `docusafe_file_ids` list).
- Cross-app ownership uses `UUIDField` (not `ForeignKey`) — e.g. `thread_id` on `Message`.

## Tools

Registration pattern for every new tool:

```python
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from typing import Annotated
from langgraph.prebuilt import InjectedToolCallId
from apps.assistant.graph.streaming import get_stream_writer

@tool
def my_tool(
    query: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    writer = get_stream_writer()
    writer({"status": "start", "tool_call_id": tool_call_id, "label": "..."})
    # ... do work ...
    writer({"status": "stop", "tool_call_id": tool_call_id})
    return "string result shown to LLM"
```

After creating a tool:
1. Add it to `get_all_tools()` in `apps/assistant/tools/__init__.py`.
2. Add the tool name to `allowed_tools` in the relevant `IntentConfig` in `apps/assistant/intents/registry.py`.

## Intent Registry

- Static registry in `apps/assistant/intents/registry.py`.
- Each intent has: `name`, `description`, `system_prompt`, `allowed_tools`, temperature/token config, and `llm_config` (provider, model, region).
- Current intents: `general_qa` (default), `docusafe_qa` (document QA; bypasses LLM classifier).
- Intent helpers: `get_intent_by_name()`, `get_all_intent_summaries()`.

## LangGraph Flow

```
START → router → [generate_title → END | handler] → [tools conditional] → tools → handler → END
```

- `router` node: classifies intent; docusafe threads bypass classifier.
- `handler` node: streams tokens/tool_calls via `get_stream_writer()`, binds allowed tools to LLM.
- `generate_title` node: auto-titles "New Chat" threads, emits `thread_updated` event.
- State: `AssistantState` with `messages` (BaseMessage list), `intent_name`, `confidence`, `user_id`.

## SSE Streaming

Custom SSE event types emitted via `get_stream_writer()`:
- `text` — streamed token chunk
- `tool_call` — tool progress updates (start/update/stop/error)
- `intent_selected` — intent routing decision
- `usage` — token usage stats
- `error` — error details

`ChatView` returns an `EventSourceResponse` for streaming. Non-streaming returns JSON with `message` + `intent_name`.

## LLM Provider (AWS Bedrock)

Settings variables (in `settings/llm.py`):
- `AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID` — primary chat model
- `AWS_BEDROCK_TITLE_INFERENCE_PROFILE_ID` — title generation model
- `AWS_BEDROCK_INTENT_CLASSIFIER_INFERENCE_PROFILE_ID` — intent classification model
- `AWS_BEDROCK_REGION` — defaults to `us-east-1`

Use cross-region inference profile format: `us.amazon.nova-pro-v1:0` or full ARN.

`llm_factory.build_chat_llm(llm_config, temperature, max_tokens)` returns `ChatBedrockConverse`.

## Key Pitfalls

1. Highest priority: Do **not** use `AuditModel` for `Thread`/`Message` — use `TimeAuditModel`.
2. High priority: Do **not** add cross-app `ForeignKey` — use `UUIDField` references.
3. High priority: Always register new tools in both `get_all_tools()` **and** the relevant `IntentConfig.allowed_tools`.
4. Medium priority: `Thread.settings.enabled_web_search` can disable `web_search` per thread — respect it in intent configs.
5. Medium priority: For LangSmith cost tracking, set `ls_model_name` to a stable provider/model identifier (for example, `amazon.nova-pro-v1`) instead of a deployment-specific inference profile ID. If cost is blank, add a model price row in LangSmith workspace settings with the same `ls_model_name` value used in traces.

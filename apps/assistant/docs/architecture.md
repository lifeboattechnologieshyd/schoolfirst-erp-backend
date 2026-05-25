# Assistant App — Architecture Reference

## Overview

The Assistant app provides a conversational AI interface backed by AWS Bedrock. Users create **threads** (conversations), send **messages**, and receive LLM-generated responses. Responses can be delivered as standard JSON or as Server-Sent Events (SSE) for real-time streaming.

```
┌──────────┐     ┌───────────┐     ┌────────────┐     ┌──────────────┐
│  Client   │────▶│  ChatView  │────▶│ LLMService  │────▶│ LLM Provider │
│ (Frontend)│◀────│  (DRF)     │◀────│ (LangGraph) │◀────│ (Bedrock)    │
└──────────┘     └───────────┘     └────────────┘     └──────────────┘
      │                │                                       │
      │          ┌─────▼─────┐                          ┌──────▼──────┐
      │          │  Message   │                          │ Nova Web    │
      │          │  Model     │                          │ Grounding   │
      │          └───────────┘                          └─────────────┘
      │
      ▼
 SSE Stream (text deltas)
 or JSON response
```

---

## Data Models

All models inherit from `TimeAuditModel` (provides `created_at`, `updated_at`).

### Thread

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUIDField (PK) | `default=uuid.uuid4` |
| `user_id` | UUIDField | Owner, indexed |
| `name` | CharField(255) | Default `"New Chat"`, auto-titled on first message |
| `status` | CharField(20) | Default `"ACTIVE"` |

**Indexes:** `(user_id, status)`, `(created_at)`

### Message

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUIDField (PK) | `default=uuid.uuid4` |
| `thread_id` | UUIDField | FK to Thread |
| `sender_type` | CharField | `"user"` or `"assistant"` (MessageSenderType enum) |
| `content_blocks` | JSONField | Structured array of text/tool_call blocks |
| `schema_version` | CharField(10) | Default `"2.0"` |
| `role_metadata` | JSONField | Assistant-only metadata (stop_reason, model, usage) |
| `intent_name` | CharField(100) | Nullable. Classified intent (e.g. `"general_qa"`) |

**Indexes:** `(thread_id)`, `(sender_type)`, `(created_at)`

### Attachment

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUIDField (PK) | `default=uuid.uuid4` |
| `thread_id` | UUIDField | FK to Thread |
| `message_id` | UUIDField | FK to Message |
| `file_path` | CharField(500) | Storage location |
| `file_name` | CharField(255) | Original filename |
| `file_size` | BigIntegerField | Bytes |
| `mime_type` | CharField(100) | MIME type |
| `width` | IntegerField | Nullable, for images/videos |
| `height` | IntegerField | Nullable, for images/videos |
| `duration` | IntegerField | Nullable, for audio/video (seconds) |

**Indexes:** `(thread_id, message_id)`

---

## API Endpoints

All endpoints require authentication (`IsAuthenticated`).

### `POST /v1/assistant/threads/`

Create a new thread.

**Request:** `{}` (empty body, or `{"name": "optional"}`)

**Response (200):**

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "name": "New Chat",
    "status": "ACTIVE",
    "created_at": "iso-datetime",
    "updated_at": "iso-datetime"
  }
}
```

### `GET /v1/assistant/threads/`

List all threads for the authenticated user.

### `GET /v1/assistant/threads/{id}/`

Retrieve a single thread.

### `PATCH /v1/assistant/threads/{id}/`

Update thread (e.g. rename).

### `DELETE /v1/assistant/threads/{id}/`

Delete a thread.

### `POST /v1/assistant/threads/{id}/chat/`

Send a message and receive an LLM response. See [Frontend Integration Guide](frontend-integration-guide.md) for full details.

**Request:**

```json
{
  "content": "string (required)",
  "stream": true,
  "attachments": ["temp_path_1", "temp_path_2"]
}
```

**Response (direct, `stream=false`):**

```json
{
  "success": true,
  "data": {
    "message": "LLM response text (markdown)"
  }
}
```

**Response (streaming, `stream=true`):**
`Content-Type: text/event-stream` — see [Frontend Integration Guide](frontend-integration-guide.md).

### `GET /v1/assistant/threads/{id}/messages/`

List messages for a thread, ordered by `created_at` ascending.

**Response (200):**

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "thread_id": "uuid",
      "sender_type": "user",
      "content_blocks": [{"type": "text", "text": "What is Python?"}],
      "role_metadata": null,
      "schema_version": "2.0",
      "created_at": "iso-datetime"
    },
    {
      "id": "uuid",
      "thread_id": "uuid",
      "sender_type": "assistant",
      "content_blocks": [{"type": "text", "text": "Python is a programming language..."}],
      "role_metadata": {"stop_reason": "end_turn", "model": "claude-haiku", "usage": {}},
      "schema_version": "2.0",
      "created_at": "iso-datetime"
    }
  ]
}
```

---

## Enums

### MessageSenderType (`apps/assistant/enums/message.py`)

| Value | Label |
| --- | --- |
| `USER` | User |
| `LLM` | LLM Assistant |

### StreamEventType (`apps/assistant/enums/streaming.py`)

| Value | Purpose |
| --- | --- |
| `message_start` | Response initialization |
| `content_block_start` | Content block initialization |
| `content_block_delta` | Content block incremental update |
| `content_block_stop` | Content block completion |
| `message_delta` | Message-level metadata update |
| `message_stop` | Response completion |
| `error` | Error event |

### ContentBlockType (`apps/assistant/enums/streaming.py`)

| Value | Purpose |
| --- | --- |
| `text` | Text content block |
| `tool_call` | Tool invocation block |
| `tool_result` | Tool result block |

### DeltaType (`apps/assistant/enums/streaming.py`)

| Value | Purpose |
| --- | --- |
| `text_delta` | Incremental text content |
| `input_json_delta` | Incremental JSON input |

---

## LLM Provider System

### AbstractLLMProvider (`apps/assistant/services/providers/base.py`)

| Method | Returns | Purpose |
| --- | --- | --- |
| `classify_intent(query, intents)` | `dict` | Intent classification with confidence |
| `generate_response(query, context)` | `LLMResponse` | Non-streaming response |
| `generate_streaming_response(query, context)` | `Iterator[str \| dict]` | Streaming: `str`=text, `dict`=citation |
| `generate_title(message)` | `str` | Thread title generation |

### AWSBedrockNativeLLMProvider

Uses boto3 `converse()` / `converse_stream()` APIs.

### FakeLLMProvider

Returns static responses for testing/development. Always classifies as `general_qa` with confidence `1.0`.

---

## Intent System

See [Intent System Walkthrough](intent-system.md) for full details.

**Summary:** User messages are classified by the LLM into intents (e.g. `general_qa`) using a LangGraph-based routing system. If confidence exceeds the threshold, the graph routes the request to a specific node or handler. Otherwise, it falls back to a general response node.

Key files:

- `apps/assistant/graph/builder.py` — LangGraph structure and node definitions
- `apps/assistant/graph/nodes.py` — Individual node implementations (router, handlers)
- `apps/assistant/services/llm_service.py` — Graph orchestration

---

## Streaming Architecture

See [Frontend Integration Guide](frontend-integration-guide.md) for the full event reference and rendering guide.

**Summary:** The `ContentBlockStreamProcessor` converts raw LLM output (text chunks) into a unified content block SSE event format. The event sequence is:

```
message_start → content_block_start(text) → content_block_delta(text_delta)* → content_block_stop → message_delta → message_stop
```

Key files:

- `shared/streaming/processor.py` — Content block stream processor
- `shared/streaming/sse.py` — Content block SSE event builders
- `apps/assistant/enums/streaming.py` — StreamEventType, ContentBlockType, DeltaType enums

---

## Configuration

| Setting | Type | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `str` | `"AWS_BEDROCK"` or `"FAKE"` |
| `AWS_BEDROCK_MODEL_ID` | `str` | Bedrock model ID (e.g. `"us.amazon.nova-pro-v1:0"`) |
| `AWS_BEDROCK_REGION` | `str` | AWS region (default `"us-east-1"`) |
| `LLM_MODEL` | `str` | Model name for metadata/logging |

---

## File Structure

```
apps/assistant/
├── docs/
│   ├── architecture.md                 # This file
│   ├── frontend-integration-guide.md   # Frontend rendering & event reference
│   └── intent-system.md               # Intent system walkthrough
├── enums/
│   ├── __init__.py
│   ├── message.py                      # MessageSenderType
│   └── streaming.py                    # StreamEventType, ContentBlockType, DeltaType
├── intents/
│   ├── __init__.py
│   ├── registry.py                     # Static intent definitions
│   └── handlers/
│       ├── __init__.py
│       └── general_qa.py              # General QA handler
├── models/
│   ├── __init__.py
│   ├── thread.py                       # Thread model
│   ├── message.py                      # Message model
│   └── attachment.py                   # Attachment model
├── serializers/
│   ├── __init__.py
│   ├── thread.py
│   ├── message.py
│   └── attachment.py
├── services/
│   ├── __init__.py
│   ├── llm_service.py                  # LLM orchestration service
│   ├── intent_dispatcher.py            # Dynamic intent handler dispatch
│   └── providers/
│       ├── base.py                     # AbstractLLMProvider, LLMResponse
│       ├── aws_bedrock_native.py       # AWS Bedrock Converse API provider
│       ├── async_wrapper.py            # Async facade over sync providers
│       └── fake.py                     # Mock provider for testing
├── views/
│   ├── __init__.py
│   ├── chat.py                         # ChatView, MessageListView
│   └── thread.py                       # Thread CRUD views
├── urls.py
├── apps.py
└── migrations/

shared/streaming/
├── __init__.py                         # Public exports
├── sse.py                              # Content block SSE event builders
└── processor.py                        # Content block stream processor
```

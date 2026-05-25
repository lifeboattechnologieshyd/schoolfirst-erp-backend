# Frontend Integration Guide — Chat Endpoint

This document is the contract between the backend and frontend for the assistant chat endpoint. It covers the request/response format, content block streaming model, SSE event structure, citation handling, and rendering conventions.

---

## Table of Contents

1. [Chat Endpoint Overview](#1-chat-endpoint-overview)
10. [Event Reference](#10-event-reference)
11. [Rendering Guide](#11-rendering-guide)
7. [Client Code Examples](#7-client-code-examples)
8. [Error Handling](#8-error-handling)
9. [Conventions & Standards](#9-conventions--standards)

---

## 1. Chat Endpoint Overview

```
POST /api/v1/assistant/threads/{thread_id}/chat/
Authorization: Bearer <token>
Content-Type: application/json
```

### Request Body

```json
{
  "content": "What are the latest Python releases?",
  "stream": true,
  "attachments": []
}
```

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `content` | string | Yes | — | User's message text |
| `stream` | boolean | No | `true` | `true` = SSE stream, `false` = JSON response |
| `attachments` | string[] | No | `[]` | Temp file paths from upload endpoint |

### Response Modes

| Mode | Content-Type | When |
| --- | --- | --- |
| Streaming | `text/event-stream` | `stream=true` |
| Direct | `application/json` | `stream=false` |

---

## 2. Non-Streaming Response

When `stream=false`, the endpoint returns a standard JSON response after the full LLM generation completes.

```json
{
  "success": true,
  "data": {
    "message": "Python 3.13 was released on October 7, 2024...",
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `data.message` | string | Full LLM response text (markdown). |

---

## 2.5 Messages API Format (Stored Format)

While the SSE stream is ephemeral (sending separate start/stop tool events and text deltas), the **stored format** returned by the `GET /api/v1/assistant/threads/{thread_id}/messages/` API uses a clean, collapsed record structure.

Tool call starts and stops are collapsed into a single `tool_call` block with the result inline.

```json
[
  {
    "type": "text",
    "text": "I'll search your files now."
  },
  {
    "type": "tool_call",
    "id": "tc_01",
    "name": "search_docusafe",
    "input": {"query": "esops"},
    "result": {
      "status": "success",
      "data": [
        { "file_id": "7c14b9a0", "file_name": "Grant Letter.pdf" }
      ]
    },
    "progress_label": "Found relevant matches in 1 file"
  }
]
```

Note: Stored text blocks do **not** have an `index` or `block_index`. The array position dictates the render order.

---

## 3. Streaming Response (SSE)

When streaming, the response follows a **unified content block streaming model**. The client receives a series of SSE events representing the incremental construction of the assistant's message.

### Connection

```
POST /api/v1/assistant/threads/{thread_id}/chat/
Content-Type: application/json
Accept: text/event-stream
```

**Headers returned:**

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

```
message_start
  -> content_block_start (type="text")
    -> content_block_delta (type="text_delta", text="...") x N
  -> content_block_stop
-> message_delta (stop_reason, usage)
-> message_stop
```

### SSE Wire Format

Each event follows the standard SSE format:

```
event: <event_type>
data: <json_payload>

```

Events are separated by a blank line (`\n\n`).

---

## 4. Event Reference

### 4.1 `message_start`

Initializes the message structure. Emitted once at the start of every stream.

```json
{
  "type": "message_start",
  "message": {
    "id": "341d9542-ed5f-4945-9d26-45dfefa0c3ae",
    "type": "message",
    "role": "assistant",
    "model": "assistant-model",
    "content": [],
    "stop_reason": null
  }
}
```

The `model` field reflects the server's configured `LLM_MODEL` setting (e.g., `"nova-2-lite-v1"`).

**Client action:** Initialize local message state. The `message.id` is stable for the entire stream.

### 4.2 `content_block_start`

Marks the beginning of a content block. For text responses, there's typically one text content block.

```json
{
  "type": "content_block_start",
  "index": 0,
  "content_block": {
    "type": "text",
    "text": "",
| Field | Type | Description |
| --- | --- | --- |
| `index` | integer | Content block index (0-based) |
| `content_block.type` | string | Block type (always `"text"` for current implementation) |
| `content_block.text` | string | Initial text (empty string) |

**Client action:** Initialize content accumulator for this block.

### 4.3 `content_block_delta` (text)

Appends text to the current content block. This is the most frequent event.

```json
{
  "type": "content_block_delta",
  "index": 0,
  "delta": {
    "type": "text_delta",
    "text": "Python 3.13 was released on "
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `index` | integer | Content block index this delta applies to |
| `delta.type` | string | Delta type (`"text_delta"`) |
| `delta.text` | string | Text chunk to append |

**Client action:** Append `delta.text` to accumulated text. Re-render markdown progressively.

**Client action:** Finalize the content block. No more deltas will arrive for this block.

### 4.7 `tool_call`

Emitted for tool execution lifecycles. Separated into `start`, `update`, `stop`, and `error` statuses.

```json
{
  "type": "tool_call",
  "status": "start",
  "id": "tc_01",
  "name": "search_docusafe",
  "input": {"query": "..."},
  "progress": "Searching...",
  "icon": "globe"
}
```

```json
{
  "type": "tool_call",
  "status": "stop",
  "id": "tc_01",
  "name": "search_docusafe",
  "input": {"query": "..."},
  "result": {"data": [...]},
  "progress": "Search complete"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `status` | string | `"start"`, `"update"`, `"stop"`, or `"error"` |
| `id` | string | Unique tool call ID |
| `name` | string | Tool name (e.g., `"search_docusafe"`) |
| `input` | object | Tool request arguments (present on start/stop) |
| `result` | object | Tool complete result (present on stop) |
| `progress` | string | User-facing progress label |

**Client action:** Display a loading indicator/pill when `start` is received, update the label on `update`, and resolve it on `stop` or `error`.

### 4.8 `message_delta`

Provides final message metadata (stop reason and token usage).

```json
{
  "type": "message_delta",
  "delta": {
    "stop_reason": "end_turn"
  },
  "usage": {
    "output_tokens": 150
  }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `delta.stop_reason` | string | Reason for completion (`"end_turn"`, `"max_tokens"`, `"error"`) |
| `usage.output_tokens` | integer | Approximate token count (estimated as `len(text) / 4`, not a precise model count) |

**Client action:** Update UI with final status. Display token count if needed (note: this is an estimate).

### 4.9 `message_stop`

Stream terminator. Always the last event.

```json
{
  "type": "message_stop"
}
```

**Client action:** Close the connection. The stream is complete.

### 4.10 `thread_updated`

Notifies the frontend when a thread-level attribute (specifically the auto-generated title) has been updated. This typically occurs on the very first message of a "New Chat" thread.

```json
{
  "type": "thread_updated",
  "name": "The Generated Title"
}
```

**Client action:** Update the thread title in the sidebar or header immediately without waiting for the stream to finish or polling the API.

### 4.11 `error`

Emitted when a stream error occurs.

```json
{
  "type": "error",
  "error": {
    "type": "server_error",
    "message": "Connection timeout"
  }
}
```

**Client action:** Display error to user. The stream may still send `message_delta` with `stop_reason: "error"` and `message_stop`.

---

## 6. Rendering Guide

### Text Content

- Response text is **markdown**. Use a markdown renderer (e.g., `marked`, `react-markdown`, `markdown-it`).
- Content includes tables, code blocks, lists, headers, bold, italic, links.
- **All content is chunked** — tables, code blocks, etc. do NOT arrive as single units. They arrive as arbitrary chunks split across multiple `content_block_delta` events. Accumulate text and re-render progressively.
- **URLs in text arrive intact** — the backend buffers partial URLs so they are never split across events.

### Streaming UI States

```
+-------------+    message_start     +--------------+
|   Idle      |-------------------->  |  Loading     |
+-------------+                      +------+-------+
                                            |
                                   content_block_start
                                            |
                                     +------v-------+
                                     |  Streaming   |
                                     |  (show text) |
                                     +------+-------+
                                            |
                                      message_stop
                                            |
                                     +------v-------+
                                     |  Complete    |
                                     +--------------+
```

1. **Idle** -> User sends message
2. **Loading** -> Show typing indicator / skeleton. `message_start` received.
3. **Streaming** -> Show text as it arrives. Triggered by first `content_block_delta`.
4. **Complete** -> Message fully rendered. `message_stop` received.

### Display Conventions

- Response text is **markdown**. Use a markdown renderer (e.g., `marked`, `react-markdown`, `markdown-it`).
- Content includes tables, code blocks, lists, headers, bold, italic, links.
- **All content is chunked** — tables, code blocks, etc. do NOT arrive as single units. They arrive as arbitrary chunks split across multiple `content_block_delta` events. Accumulate text and re-render progressively.
- **URLs in text arrive intact** — the backend buffers partial URLs so they are never split across events.

- Use `favicon_url` from metadata to show site icon
- Display `site_domain` as the attribution
- Show `title` as the citation heading
- Use `content_body` from sources as the excerpt/snippet
- Make citations clickable to open the source URL
- Show citations as superscript numbers (e.g., `[1]`, `[2]`)

---

## 7. Client Code Examples

### TypeScript: Complete Streaming Client

```typescript
interface StreamState {
  messageId: string | null;
  text: string;
  status: "idle" | "loading" | "streaming" | "complete" | "error";
  stopReason: string | null;
  outputTokens: number;
}

async function sendMessage(threadId: string, content: string, token: string) {
  const state: StreamState = {
    messageId: null,
    text: "",
    status: "idle",
    stopReason: null,
    outputTokens: 0,
  };

  const response = await fetch(
    `/api/v1/assistant/threads/${threadId}/chat/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ content, stream: true }),
    }
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  state.status = "loading";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || ""; // Keep incomplete line in buffer

    let eventType = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        const data = JSON.parse(line.slice(6));
        handleEvent(eventType, data, state);
        renderMessage(state); // Re-render after each event
      }
    }
  }

  return state;
}

function handleEvent(eventType: string, data: any, state: StreamState) {
  switch (eventType) {
    case "message_start":
      state.messageId = data.message.id;
      state.status = "loading";
      break;

    case "content_block_start":
      state.status = "streaming";
      break;

    case "content_block_delta":
      handleContentBlockDelta(data, state);
      break;

    case "content_block_stop":
      // Block finalized — no action needed
      break;

    case "message_delta":
      state.stopReason = data.delta.stop_reason;
      state.outputTokens = data.usage?.output_tokens || 0;
      break;

    case "message_stop":
      state.status = state.stopReason === "error" ? "error" : "complete";
      break;

    case "error":
      state.status = "error";
      console.error("Stream error:", data.error);
      break;
  }
}

function handleContentBlockDelta(data: any, state: StreamState) {
  const { delta } = data;

  if (delta.type === "text_delta") {
    state.text += delta.text;
  }
}

function renderMessage(state: StreamState) {
  const container = document.getElementById("message-container");
  if (!container) return;

  // Convert markdown to HTML
  container.innerHTML = marked.parse(state.text);

  // Show token count (approximate)
  const tokenDisplay = document.getElementById("token-count");
  if (tokenDisplay && state.outputTokens > 0) {
    tokenDisplay.textContent = `~${state.outputTokens} tokens`;
  }
}
```

### React Example: Hook for Streaming

```typescript
import { useState, useCallback } from 'react';

export function useChatStream(threadId: string, token: string) {
  const [state, setState] = useState<StreamState>({
    messageId: null,
    text: "",
    status: "idle",
    stopReason: null,
    outputTokens: 0,
  });

  const sendMessage = useCallback(async (content: string) => {
    setState(prev => ({ ...prev, status: "loading" }));

    const response = await fetch(
      `/api/v1/assistant/threads/${threadId}/chat/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content, stream: true }),
      }
    );

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let eventType = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const data = JSON.parse(line.slice(6));

          setState(prev => {
            const newState = { ...prev };
            handleEvent(eventType, data, newState);
            return newState;
          });
        }
      }
    }
  }, [threadId, token]);

  return { state, sendMessage };
}
```

### Simple Fetch Example (Non-Streaming)

```typescript
async function sendMessageSync(threadId: string, content: string, token: string) {
  const response = await fetch(
    `/api/v1/assistant/threads/${threadId}/chat/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ content, stream: false }),
    }
  );

  const result = await response.json();

  if (!result.success) {
    throw new Error("Message failed");
  }

  return {
    message: result.data.message,
  };
}
```

---

## 8. Error Handling

### Stream Errors

| Scenario | What Happens |
| --- | --- |
| LLM provider error | `message_delta` with `stop_reason: "error"`, then `message_stop` |
| Connection drop | No `message_stop` event received — client should detect and retry |
| Timeout | Backend closes connection — client sees stream end without `message_stop` |
| Parse error | `error` event with error details |

### Recommended Client Behavior

```typescript
// Detect incomplete streams
if (state.status === "streaming" && !receivedMessageStop) {
  // Stream ended unexpectedly
  showError("Connection lost. Please retry.");
}

// Handle error stop reason
if (state.stopReason === "error") {
  showError("An error occurred while generating the response.");
}

// Handle max_tokens
if (state.stopReason === "max_tokens") {
  showWarning("Response was truncated due to length limit.");
}

// Connection timeout
const TIMEOUT_MS = 60000; // 60 seconds
const timeoutId = setTimeout(() => {
  if (state.status === "loading" || state.status === "streaming") {
    reader.cancel();
    showError("Request timed out.");
  }
}, TIMEOUT_MS);
```

### Non-Streaming Errors

| HTTP Status | Meaning | Action |
| --- | --- | --- |
| `400` | Missing or empty `content` | Show validation error |
| `404` | Thread not found or doesn't belong to user | Redirect to thread list |
| `401` | Invalid or missing authentication token | Redirect to login |
| `503` | LLM provider temporarily unavailable | Show retry button |
| `500` | Unexpected server error | Show error message, log to monitoring |

### Retry Strategy

```typescript
async function sendMessageWithRetry(
  threadId: string,
  content: string,
  token: string,
  maxRetries = 3
) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await sendMessage(threadId, content, token);
    } catch (error) {
      if (attempt === maxRetries) throw error;

      const backoffMs = Math.min(1000 * Math.pow(2, attempt), 10000);
      await new Promise(resolve => setTimeout(resolve, backoffMs));
    }
  }
}
```

---

## 9. Conventions & Standards

### Event Structure

All events follow this structure:

```json
{
  "type": "event_type",
  ...event-specific fields
}
```

The `type` field identifies the event. No additional metadata like `event_id` or `sequence` is included.

### Content

- **Content type** is always `"text"`. The text is markdown, rendered by the client.
- **Token count** in `usage.output_tokens` is an **approximate** estimate (roughly `text_length / 4`), not a precise model-reported count.
- **Text is chunked arbitrarily.** Tables, code blocks, etc. are split across multiple `content_block_delta` events. The client must accumulate and re-render progressively.
- **URLs in text are never split.** The backend buffers partial URLs so they always arrive as complete strings in a single `text_delta`.

### Content Block Index

- The `index` field in `content_block_start`, `content_block_delta`, and `content_block_stop` identifies which content block a delta belongs to.
- Currently, only one content block (index 0) is used per message.
- Future implementations may support multiple content blocks (e.g., text + image).

### Stop Reasons

| Stop Reason | Meaning |
| --- | --- |
| `end_turn` | Normal completion — LLM finished generating |
| `max_tokens` | Token limit reached — response truncated |
| `error` | Error occurred during generation |

### Markdown Rendering

- Use a secure markdown renderer (e.g., `marked` with sanitization, `react-markdown`).
- Support all standard markdown features: headers, lists, tables, code blocks, links, bold, italic.
- Code blocks: Use syntax highlighting (e.g., `highlight.js`, `prism`).
- Tables: Render with proper CSS styling.
- Links: Open in new tab with `rel="noopener noreferrer"`.

### Security Considerations

- **Sanitize markdown output** to prevent XSS attacks.
- **Validate citation URLs** before rendering as links.
- **Use HTTPS** for all API requests.
- **Handle authentication token securely** — never log or expose in client-side code.
- **Rate limiting**: Implement client-side throttling to prevent excessive requests.

### Performance Optimization

- **Debounce rendering**: Don't re-render on every single `text_delta`. Batch updates (e.g., every 50ms).
- **Virtual scrolling**: For long conversations, use virtual scrolling to improve performance.
- **Lazy load citations**: Load citation source details on-demand (hover/click).
- **Connection pooling**: Reuse HTTP connections for multiple requests.

---

## Summary

This guide documents the Claude content block streaming model for the SamsR assistant chat endpoint. Key points:

1. **Two modes**: Streaming (SSE) and non-streaming (JSON)
2. **Content blocks**: Messages are composed of content blocks that stream incrementally
3. **Approximate tokens**: `output_tokens` is an estimate, not a precise count.
4. **Markdown content**: All text is markdown and should be rendered accordingly.
5. **Progressive rendering**: UI updates as chunks arrive for responsive user experience.

For questions or issues, refer to the backend implementation in `/apps/assistant/` or contact the backend team.

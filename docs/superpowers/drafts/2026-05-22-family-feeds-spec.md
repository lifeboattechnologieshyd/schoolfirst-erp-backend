# Family Feeds — Module Specification v1.0
**SamsR App** · Status: In Design

---

## Table of Contents
1. [Overview](#overview)
2. [DB Schema](#db-schema)
3. [APIs](#apis)
4. [Payloads & Responses](#payloads--responses)
5. [AI Tool Calling](#ai-tool-calling)

---

## Overview

A private social timeline exclusively for family members. Users can post rich media — text, images, videos, YouTube links, and web links — and control visibility at a granular level. Think of it as a walled-garden Instagram where the walls are family trees and close groups.

### Access Model

Each feed record carries four access fields:

```
access_type           : "only_me" | "all" | "mixed"
access_family_ids     : UUID[]
access_close_group_ids: UUID[]
access_user_ids       : UUID[]
```

| Access Type | Behaviour | Arrays |
|-------------|-----------|--------|
| `only_me` | Only the creator can see the post. Used for drafts or private memories. | All three arrays are empty. Creator is implicit via `creator_id`. |
| `all` | All family members across all groups see the post. | Frontend sends the user's family ID + every close-group ID they belong to. |
| `mixed` | User hand-picks a combination of families, groups, and/or individuals. | Only the selected entity IDs are sent in the respective arrays. |

> **Rule:** Creator always has access regardless of access_type. No need to add creator to any access array.

---

### Feed Types

| # | Type | `feed_type` value | Required fields |
|---|------|-------------------|-----------------|
| 1 | Plain text | `text` | `body_text` (required). No `media_url`. |
| 2 | Image | `image` | `media_url` (image URL). `body_text` optional caption. |
| 3 | Video | `video` | `media_url` (video URL). `body_text` optional caption. |
| 4 | YouTube | `youtube` | `media_url` (YouTube URL for native embed). `body_text` optional caption. |
| 5 | Link | `link` | `media_url` (external URL, opens in browser). `body_text` optional caption. |

---

### Business Rules

| Rule | Detail |
|------|--------|
| Post deletion | Creator can delete their own post. **No editing allowed.** |
| Comment deletion | Post creator can delete any comment on their post. Commenter can delete their own comment. |
| No nested replies | Comments are flat — no `parent_comment_id` concept. |
| Feed ordering | Always chronological (newest first) for now. |
| Soft deletes | Both posts and comments use `is_deleted` flag. Records are never hard-deleted. |
| Access enforcement | Backend validates access arrays on every read. Creator is always granted access. |

---

## DB Schema

### Table: `family_feeds`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Primary key |
| `creator_id` | `UUID` | NOT NULL, FK → `users.id` | Who posted |
| `feed_type` | `ENUM` | NOT NULL | `text`, `image`, `video`, `youtube`, `link` |
| `body_text` | `TEXT` | NULLABLE | Caption or full text. Required when `feed_type = text`. |
| `media_url` | `TEXT` | NULLABLE | Image / video / YouTube / link URL. Required for all non-text types. |
| `access_type` | `ENUM` | NOT NULL | `only_me`, `all`, `mixed` |
| `access_family_ids` | `UUID[]` | DEFAULT `'{}'` | Family IDs with access |
| `access_close_group_ids` | `UUID[]` | DEFAULT `'{}'` | Close group IDs with access |
| `access_user_ids` | `UUID[]` | DEFAULT `'{}'` | Individual user IDs with access |
| `posted_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Post timestamp |
| `is_deleted` | `BOOLEAN` | DEFAULT `false` | Soft delete flag |
| `deleted_at` | `TIMESTAMPTZ` | NULLABLE | Timestamp of deletion |

> All fetches filter `is_deleted = false` unless an admin audit endpoint is used.

---

### Table: `feed_comments`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `UUID` | PK | Primary key |
| `feed_id` | `UUID` | NOT NULL, FK → `family_feeds.id` | Parent feed post |
| `commenter_id` | `UUID` | NOT NULL, FK → `users.id` | Who commented |
| `commenter_name` | `VARCHAR(150)` | NOT NULL | Denormalized for display speed |
| `commenter_pic_url` | `TEXT` | NULLABLE | Profile pic URL at time of comment |
| `comment_text` | `TEXT` | NOT NULL | The comment body |
| `commented_at` | `TIMESTAMPTZ` | NOT NULL, default `now()` | Timestamp |
| `is_deleted` | `BOOLEAN` | DEFAULT `false` | Soft delete |
| `deleted_at` | `TIMESTAMPTZ` | NULLABLE | Timestamp of deletion |

> No `parent_comment_id` — flat comment structure. No threading or nesting.

---

### Indexes

| Table | Index | Purpose |
|-------|-------|---------|
| `family_feeds` | `idx_feeds_creator_posted` on `(creator_id, posted_at DESC)` | Fast fetch by creator, chronological |
| `family_feeds` | `idx_feeds_posted_at` on `(posted_at DESC)` | Global timeline fetch |
| `family_feeds` | GIN on `access_family_ids`, `access_close_group_ids`, `access_user_ids` | Array containment queries for access checks |
| `feed_comments` | `idx_comments_feed_id` on `(feed_id, commented_at ASC)` | Fetch comments per post in order |

---

## APIs

### Feeds Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/family-feeds/` | Create a new feed post |
| `GET` | `/api/v1/family-feeds/` | Fetch feed list (chronological, newest first) |
| `GET` | `/api/v1/family-feeds/{feed_id}/` | Fetch a single feed post by ID |
| `DELETE` | `/api/v1/family-feeds/{feed_id}/` | Soft-delete a post (creator only) |

#### GET /api/v1/family-feeds/ — Query Parameters

| Param | Type | Description |
|-------|------|-------------|
| `creator_id` | UUID | Filter to posts by a specific user (for "My Posts" view) |
| `feed_type` | string | Comma-separated: `?feed_type=image,video` |
| `access_type` | string | Filter by `only_me`, `all`, or `mixed` |
| `search` | string | Case-insensitive ILIKE on `body_text` |
| `from_date` | ISO 8601 | Filter posts on or after this date (`posted_at`) |
| `to_date` | ISO 8601 | Filter posts on or before this date (`posted_at`) |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Results per page (default: 20) |

---

### Comments Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/family-feeds/{feed_id}/comments/` | Add a comment to a feed post |
| `GET` | `/api/v1/family-feeds/{feed_id}/comments/` | Fetch all comments (oldest first). Supports `?page` and `?page_size` |
| `DELETE` | `/api/v1/family-feeds/{feed_id}/comments/{comment_id}/` | Delete a comment. Allowed if: requester = commenter OR requester = feed creator |

---

### Error Responses

| Status | Code | When |
|--------|------|------|
| `400` | `INVALID_FEED_TYPE` | `feed_type` not in allowed enum |
| `400` | `MEDIA_URL_REQUIRED` | `media_url` is null for image / video / youtube / link types |
| `400` | `TEXT_REQUIRED` | `body_text` is null when `feed_type = text` |
| `400` | `INVALID_ACCESS_TYPE` | `access_type` not in `only_me` / `all` / `mixed` |
| `403` | `NOT_OWNER` | Attempting delete on a post/comment you don't own |
| `404` | `FEED_NOT_FOUND` | `feed_id` does not exist or is deleted |
| `404` | `COMMENT_NOT_FOUND` | `comment_id` not found on that feed |

---

## Payloads & Responses

### POST /api/v1/family-feeds/ — Request

#### feed_type: `text`
```json
{
  "feed_type": "text",
  "body_text": "Happy anniversary to us! 25 years and counting",
  "media_url": null,
  "access_type": "all",
  "access_family_ids": ["fam-uuid-001"],
  "access_close_group_ids": ["grp-uuid-a", "grp-uuid-b"],
  "access_user_ids": []
}
```

#### feed_type: `image`
```json
{
  "feed_type": "image",
  "body_text": "Sunset at the beach house last evening",
  "media_url": "https://cdn.samsR.app/feeds/img_abc123.jpg",
  "access_type": "mixed",
  "access_family_ids": ["fam-uuid-001"],
  "access_close_group_ids": [],
  "access_user_ids": ["usr-uuid-granny"]
}
```

#### feed_type: `video`
```json
{
  "feed_type": "video",
  "body_text": "Baby's first steps!",
  "media_url": "https://cdn.samsR.app/feeds/vid_xyz789.mp4",
  "access_type": "all",
  "access_family_ids": ["fam-uuid-001"],
  "access_close_group_ids": ["grp-uuid-a"],
  "access_user_ids": []
}
```

#### feed_type: `youtube`
```json
{
  "feed_type": "youtube",
  "body_text": "Dad's favourite song — sharing for memories!",
  "media_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "access_type": "only_me",
  "access_family_ids": [],
  "access_close_group_ids": [],
  "access_user_ids": []
}
```

#### feed_type: `link`
```json
{
  "feed_type": "link",
  "body_text": "This recipe is exactly how Mom used to make it",
  "media_url": "https://www.somerecipe.com/moms-biryani",
  "access_type": "mixed",
  "access_family_ids": [],
  "access_close_group_ids": ["grp-uuid-b"],
  "access_user_ids": ["usr-uuid-aunt", "usr-uuid-cousin"]
}
```

---

### POST /api/v1/family-feeds/ — Success Response `201`

```json
{
  "id": "feed-uuid-001",
  "creator_id": "usr-uuid-abc",
  "feed_type": "image",
  "body_text": "Sunset at the beach house last evening",
  "media_url": "https://cdn.samsR.app/feeds/img_abc123.jpg",
  "access_type": "mixed",
  "access_family_ids": ["fam-uuid-001"],
  "access_close_group_ids": [],
  "access_user_ids": ["usr-uuid-granny"],
  "posted_at": "2025-11-20T18:42:00Z",
  "is_deleted": false,
  "comment_count": 0
}
```

---

### GET /api/v1/family-feeds/ — List Response `200`

```json
{
  "count": 142,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": "feed-uuid-001",
      "creator_id": "usr-uuid-abc",
      "creator_name": "Priya Sharma",
      "creator_pic_url": "https://cdn.samsR.app/pics/priya.jpg",
      "feed_type": "image",
      "body_text": "Sunset at the beach house last evening",
      "media_url": "https://cdn.samsR.app/feeds/img_abc123.jpg",
      "access_type": "mixed",
      "access_family_ids": ["fam-uuid-001"],
      "access_close_group_ids": [],
      "access_user_ids": ["usr-uuid-granny"],
      "posted_at": "2025-11-20T18:42:00Z",
      "comment_count": 4
    }
  ]
}
```

> Note: List response includes denormalized `creator_name` and `creator_pic_url` for fast rendering without joins on the frontend.

---

### POST /api/v1/family-feeds/{feed_id}/comments/ — Request

```json
{
  "comment_text": "This is so beautiful! Miss you all"
}
```

> `commenter_id`, `commenter_name`, and `commenter_pic_url` are derived from the auth token on the backend. Frontend does not send them.

---

### GET /api/v1/family-feeds/{feed_id}/comments/ — Response `200`

```json
{
  "count": 4,
  "results": [
    {
      "id": "cmt-uuid-001",
      "feed_id": "feed-uuid-001",
      "commenter_id": "usr-uuid-granny",
      "commenter_name": "Kamala Sharma",
      "commenter_pic_url": "https://cdn.samsR.app/pics/kamala.jpg",
      "comment_text": "Beautiful sunset beta!",
      "commented_at": "2025-11-20T19:05:00Z"
    }
  ]
}
```

---

## AI Tool Calling

These tool definitions allow the in-app chatbot to post feeds and comments on behalf of the user through natural language. The AI never crafts raw API calls — it calls structured tools and the app layer handles auth and submission.

---

### Tool: `create_feed_post`

```json
{
  "name": "create_feed_post",
  "description": "Create a family feed post on behalf of the user. Use this when the user wants to share text, an image, video, YouTube link, or web link with family members. Always confirm access_type with the user if not specified.",
  "input_schema": {
    "type": "object",
    "properties": {
      "feed_type": {
        "type": "string",
        "enum": ["text", "image", "video", "youtube", "link"],
        "description": "Type of feed post to create"
      },
      "body_text": {
        "type": "string",
        "description": "Caption or full text of the post. Required for feed_type=text."
      },
      "media_url": {
        "type": "string",
        "description": "URL of image, video, YouTube video, or web link. Required for all non-text feed types."
      },
      "access_type": {
        "type": "string",
        "enum": ["only_me", "all", "mixed"],
        "description": "Who can see this post. 'all' shares with all family and groups. 'mixed' allows specific selection."
      },
      "access_family_ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Family IDs to include. Empty for only_me."
      },
      "access_close_group_ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Close group IDs to include."
      },
      "access_user_ids": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Individual user IDs to include in mixed access."
      }
    },
    "required": ["feed_type", "access_type"]
  }
}
```

---

### Tool: `add_feed_comment`

```json
{
  "name": "add_feed_comment",
  "description": "Post a comment on a specific family feed post. Use when the user wants to comment on a visible feed item.",
  "input_schema": {
    "type": "object",
    "properties": {
      "feed_id": {
        "type": "string",
        "description": "UUID of the feed post to comment on"
      },
      "comment_text": {
        "type": "string",
        "description": "The comment content to post"
      }
    },
    "required": ["feed_id", "comment_text"]
  }
}
```

---

### Tool: `delete_feed_post`

```json
{
  "name": "delete_feed_post",
  "description": "Delete a feed post. Only works if the user is the creator. Always confirm with the user before calling this.",
  "input_schema": {
    "type": "object",
    "properties": {
      "feed_id": {
        "type": "string",
        "description": "UUID of the feed to delete"
      }
    },
    "required": ["feed_id"]
  }
}
```

---

### Example AI Conversation Flow

**User prompt:**
> "Post a message for the whole family saying happy Diwali from us!"

**AI resolves:**
- `feed_type` = `text`
- `access_type` = `all`
- Populates `access_family_ids` + `access_close_group_ids` from user context
- `body_text` = `"Happy Diwali from us!"`

**Calls:** `create_feed_post` → confirms with user → Done

---

> **Security note:** AI never receives raw auth tokens. The app layer appends `creator_id` and auth headers server-side. AI only sends content and access intent.

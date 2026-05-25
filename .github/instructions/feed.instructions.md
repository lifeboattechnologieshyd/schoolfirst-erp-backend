---
description: "Use when working in the feed app: posts, comments, reactions, shares, or feed visibility."
applyTo: "apps/feed/**"
---

# Feed App Conventions

## Session Close-Out

After Python code changes, follow the repo-level close-out validation in [AGENTS.md](../../AGENTS.md). Run `source ~/.zshrc && source .venv/bin/activate && ruff check . --output-format concise && ty check` from the repo root, and fix any failures before handoff.

## URL Structure

```
v1/feed/                              # list (newest first) / create
                                      #   ?creator_id=<uuid> optional filter
v1/feed/saved/                        # list current user's saved posts (newest save first)
v1/feed/{feed_id}/                      # get / put / patch / delete
v1/feed/{feed_id}/comments/             # list/create comments (nested)
v1/feed/{feed_id}/comments/{comment_id}/    # update/delete comment (nested)
v1/feed/{feed_id}/react/                # add/update/remove reaction
v1/feed/{feed_id}/save/                 # save post (POST) / unsave (DELETE)
v1/feed/{feed_id}/share/                # log share event
```

Effective paths are prefixed with `/api/` from [settings/urls.py](../../settings/urls.py).

## Models

| Model | Key Fields |
|-------|-----------|
| `Feed` | `creator` FK, `text`, `media_urls`, `youtube_url`, `external_urls` (nullable JSON list), JSON access arrays, denormalized counters, soft delete |
| `FeedComment` | `feed`, `user`, `comment_text`, soft delete |
| `FeedReaction` | one reaction per user per post (`UniqueConstraint`) |
| `FeedSave` | one save per user per post (`UniqueConstraint`) |
| `FeedShare` | share audit log with validated `platform` enum |

`Feed.creator` is the post author FK. `AuditModel.created_by` remains the request audit CharField — do not rename the author FK back to `created_by`.

## Access Control

Visibility uses the same JSON-array pattern as calendar:

- `access_type`: `only_me`, `all`, or `mixed`
- `access_family_ids`, `access_close_group_ids`, `access_user_ids`

Feed-specific `all` semantics (stricter than calendar):

- Requires at least one family or close-group ID
- `access_user_ids` must be empty

Validation lives in [apps/feed/services/access_policy.py](../apps/feed/services/access_policy.py). Filtering uses `FeedAccessPolicy.build_filter()` with `SocialGraphService`.

## Services

- Mutations go through [apps/feed/services/feed_service.py](../apps/feed/services/feed_service.py)
- Use `FeedService.get_visible_feed()` from views — do not call private helpers
- Media paths must be `temp/{user_id}/...` on create or existing `feeds/{feed_id}/...` on update
- List endpoint always orders by `-created_at` (newest first)
- `body_text` is required only when `media_urls`, `youtube_url`, and `external_urls` are all empty

## Serializers

- Read: `FeedListSerializer` (includes `my_reaction`, `is_saved`, `reactions`), `FeedCommentSerializer`
- Write: `FeedCreateSerializer`, `FeedUpdateSerializer`, `FeedCommentWriteSerializer`, `FeedReactionWriteSerializer`, `FeedShareWriteSerializer`
- API exposes author UUID as `created_by` (sourced from `creator_id`)
- `profile_image` and `media_urls` in responses are full public S3 URLs (no signed query params)

## Tests

Playwright API tests only: [tests/playwright/tests/feed/feed.spec.ts](../../tests/playwright/tests/feed/feed.spec.ts)

Bruno collection: [bruno/Feed/](../../bruno/Feed/)

## Legacy Tables

`core.0009_move_feed_to_feed_app` removed old `FamilyFeed*` models from Django state only. Legacy `family_feed*` tables may still exist in long-lived databases; new data uses `feeds`, `feed_comments`, `feed_reactions`, `feed_saves`, and `feed_shares`. No automatic data migration is shipped — treat as greenfield unless ops confirms legacy data.

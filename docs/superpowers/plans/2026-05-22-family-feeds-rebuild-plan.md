# Rebuild Feeds Module Implementation Plan

Rebuild the feeds module to adapt the Project Manager's specifications into the existing Django backend architecture, allowing generic posting (across families, close groups, and individuals) with key security validations, reaction features, share tracking, and optimized database structures.

## User Review Required

We have aligned on the following design choices:
1. **URL Scheme:** Use `/api/v1/feed` for feed list and creation, `/api/v1/feed/<uuid:feed_id>` for feed detail operations, `/api/v1/feed/<uuid:feed_id>/comments` for comments, and `/api/v1/feed/comments/<uuid:comment_id>` for comment deletion.
2. **Comment Management:** Consolidate list/create onto nested resources (`v1/feed/<uuid:feed_id>/comments`) and delete onto comment path parameters.
3. **Access Control Modeling:** Use plain `models.JSONField(default=list, null=True, blank=True)` fields for `access_family_ids`, `access_close_group_ids`, and `access_user_ids` on the feed model. This matches the visibility pattern in `apps/calendar` (storing arrays of UUIDs directly) rather than using relational child tables, ensuring complete schema and querying consistency. No single `family` ForeignKey field is stored on the feed model itself.
4. **Media Storage:** Store media URLs as a JSON list (`media_urls` array field) directly in the parent `Feed` table. Completely discard the separate child `FamilyFeedMedia` model.
5. **Feed Reactions:** Add reaction support using a Django CharField with choices/enum mapping to the 7 fixed emojis (`like`, `love`, `laugh`, `wow`, `sad`, `angry`, `celebrate`).
6. **Feed Shares:** Track share events (user, post, sharing platform) in a `FeedShare` table.
7. **Soft Deletion:** Implement soft-deletion (`is_deleted` and `deleted_at`) for both feed posts and comments.
8. **Creator & Commenter Details:** Query name and profile picture dynamically at serialization time instead of denormalizing them on the tables (eliminating N+1 queries using `select_related`).
9. **Error Codes:** Use standard `GlobalAPIMessageCodes` (e.g., `VALIDATION_ERROR`, `FORBIDDEN`, `NOT_FOUND`).
10. **Cross-Module Foreign Keys:** Use direct Django relationship foreign keys between the `feed` module and the `core` module (`Feed.created_by`, `FeedComment.user`, `FeedReaction.user`, and `FeedShare.user` pointing to `UserMaster`), overriding the strict module-isolation rule as requested.
11. **Text Formatting:** The feed description field (`text`) is defined as a `models.TextField` to natively store and render line breaks (`\n`, `\r\n`) sent by the frontend.
12. **YouTube Integration:** Support native YouTube sharing by introducing a `youtube_url` field on the `Feed` parent model. When `youtube_url` is provided, `media_urls` must be empty, and the user can optionally supply text (or leave it blank).

---

## N+1 Query Optimization

To prevent N+1 queries when loading feeds and their associated comments/reactions:
1. **Feed List Endpoint (`GET /api/v1/feed`)**:
   * Use `.select_related("created_by")` on the `Feed` queryset in `FeedService.get_feed_queryset(user)`.
   * For checking the current user's reaction on each feed post, use `prefetch_related(Prefetch("reactions", queryset=FeedReaction.objects.filter(user=user), to_attr="user_reaction"))`.
2. **Feed Comments Endpoint (`GET /api/v1/feed/comments`)**:
   * Use `.select_related("user")` on the `FeedComment` queryset in `FeedService.get_feed_comments` to fetch commenter user records in the same query.

---

## Proposed Changes

### 1. Database & Models (`apps/feed/models/`)

#### [MODIFY] [feed.py](file:///Users/karthiknarayan/veto/samsr-backend/apps/feed/models/feed.py)
Redesign and replace all existing model classes with generic feed entities:

```python
from django.db import models
from shared.mixins.base_model import AuditModel
from apps.core.models import UserMaster

class Feed(AuditModel):
    class AccessType(models.TextChoices):
        ONLY_ME = "only_me", "Only Me"
        ALL = "all", "All Family"
        MIXED = "mixed", "Selected Entities"

    created_by = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="created_feeds")
    
    text = models.TextField(null=True, blank=True)  # Handles line breaks & text body
    media_urls = models.JSONField(default=list, blank=True)  # Array of URLs (stored in parent table)
    youtube_url = models.CharField(max_length=500, null=True, blank=True)  # Stores YouTube video link

    
    access_type = models.CharField(max_length=20, choices=AccessType.choices, default=AccessType.ONLY_ME)
    access_family_ids = models.JSONField(default=list, null=True, blank=True)
    access_close_group_ids = models.JSONField(default=list, null=True, blank=True)
    access_user_ids = models.JSONField(default=list, null=True, blank=True)
    
    reaction_count = models.IntegerField(default=0)  # Denormalized field
    comment_count = models.IntegerField(default=0)   # Denormalized field
    share_count = models.IntegerField(default=0)     # Denormalized field
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "feeds"
        ordering = ["-created_at"]


class FeedComment(AuditModel):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_comments")
    comment_text = models.TextField()
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "feed_comments"
        ordering = ["created_at"]


class FeedReaction(AuditModel):
    class ReactionType(models.TextChoices):
        LIKE = "like", "👍"
        LOVE = "love", "❤️"
        LAUGH = "laugh", "😂"
        WOW = "wow", "😮"
        SAD = "sad", "😢"
        ANGRY = "angry", "😡"
        CELEBRATE = "celebrate", "🎉"

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_reactions")
    reaction = models.CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        db_table = "feed_reactions"
        unique_together = ("feed", "user")


class FeedShare(AuditModel):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_shares")
    platform = models.CharField(max_length=50)  # e.g., "whatsapp", "facebook", "native"

    class Meta:
        db_table = "feed_shares"
```

---

### 2. Services (`apps/feed/services/`)

#### [MODIFY] [feed_service.py](file:///Users/karthiknarayan/veto/samsr-backend/apps/feed/services/feed_service.py)
* Re-implement `FeedService` logic:
  - **Security Access Check (`_get_visible_feed`)**:
    Checks if a post is visible to a user before performing reading, commenting, reacting, or sharing. Visibility checks build filters dynamically (using family lists and close group lists) matching the scopes of `SocialGraphService` (similar to Calendar logic).
  - **`create_feed(user, text, media_urls, access_type, access_family_ids, access_close_group_ids, access_user_ids)`**:
    Validates creator network constraints for access arrays and saves the post.
  - **`comment_on_feed(user, feed_id, comment_text)`**:
    1. Validates user has access to `feed_id` post.
    2. Creates a `FeedComment`.
    3. Atomically updates parent: `Feed.objects.filter(id=feed_id).update(comment_count=F("comment_count") + 1)`.
  - **`react_to_feed(user, feed_id, reaction_string)`**:
    1. Validates user has access to `feed_id` post.
    2. If `reaction_string` is `null`/empty, removes any existing reaction from this user and decrements `reaction_count`.
    3. If reaction exists with a different emoji, updates it (keeping reaction count same).
    4. If no reaction exists, creates `FeedReaction` and increments `reaction_count`.
    5. Perform updates atomically using `F("reaction_count")`.
  - **`share_feed(user, feed_id, platform)`**:
    1. Validates user has access to `feed_id` post.
    2. Creates `FeedShare` log entry.
    3. Atomically increments parent: `Feed.objects.filter(id=feed_id).update(share_count=F("share_count") + 1)`.
  - **`delete_feed_comment(user, comment_id)`**:
    Validates user ownership/permissions, soft-deletes the comment, and atomically decrements `comment_count` on the parent.

---

### 3. Serializers (`apps/feed/serializers/`)

#### [MODIFY] [feed.py](file:///Users/karthiknarayan/veto/samsr-backend/apps/feed/serializers/feed.py)
* Update serializers:
  - `FeedListSerializer`:
    * Map `text` -> `body_text`.
    * Expose `media_urls` (JSON list).
    * Dynamic nested dictionary serialization for `created_by` (ID, first_name, last_name, profile_image).
    * Dynamic resolution of `my_reaction` string.
    * Expose counters: `reaction_count`, `comment_count`, `share_count`.
  - `FeedCommentSerializer`:
    * Map `id` -> `comment_id`, `comment_text` -> `comment_text`.
    * Dynamic nested dictionary serialization for commenter details (`user`).

---

### 4. Views & Routing (`apps/feed/views/`, `apps/feed/urls.py`)

#### [MODIFY] [feed.py](file:///Users/karthiknarayan/veto/samsr-backend/apps/feed/views/feed.py)
* Re-implement View classes:
  - `FeedListCreateView` (GET `/api/v1/feed`, POST `/api/v1/feed`)
  - `FeedDetailView` — GET, PUT, PATCH, DELETE `/api/v1/feed/{feed_id}`
  - `FeedCommentListCreateView` (GET `/api/v1/feed/<uuid:feed_id>/comments`, POST `/api/v1/feed/<uuid:feed_id>/comments`)
  - `FeedCommentDestroyView` (DELETE `/api/v1/feed/comments/<uuid:comment_id>`)
  - `FeedReactionView` (POST `/api/v1/feed/<uuid:feed_id>/react`)
  - `FeedShareView` (POST `/api/v1/feed/<uuid:feed_id>/share`)

#### [MODIFY] [urls.py](file:///Users/karthiknarayan/veto/samsr-backend/apps/feed/urls.py)
* Map urls:
  - `path("v1/feed", FeedListCreateView.as_view())`
  - `path("v1/feed/<uuid:feed_id>", FeedDetailView.as_view())`
  - `path("v1/feed/<uuid:feed_id>/comments", FeedCommentListCreateView.as_view())`
  - `path("v1/feed/comments/<uuid:comment_id>", FeedCommentDestroyView.as_view())`
  - `path("v1/feed/<uuid:feed_id>/react", FeedReactionView.as_view())`
  - `path("v1/feed/<uuid:feed_id>/share", FeedShareView.as_view())`

---

### 5. Bruno Collection (`bruno/Feed/`)

#### [NEW]
* `bruno/Feed/React To Feed.yml`
* `bruno/Feed/Share Feed.yml`

#### [MODIFY]
* Update list/create/comment requests and payloads to match.

---

### 6. Playwright Tests (`tests/playwright/tests/feed/`)

#### [MODIFY] [feed.spec.ts](file:///Users/karthiknarayan/veto/samsr-backend/tests/playwright/tests/feed/feed.spec.ts)
* Update tests to validate:
  - Access validation for reacting/commenting/sharing posts.
  - Verification of incremented reaction/comment/share counters.
  - Multi-media posts (`media_urls`).
  - Text posts containing line breaks (`\n`).

---

## Verification Plan

### Automated Tests
* Run migrations:
  `python manage.py makemigrations feed && python manage.py migrate --settings=settings.development`
* Run playwright tests:
  `npx playwright test tests/playwright/tests/feed/` (from `tests/playwright` directory)
* Lint and type checking:
  `ruff check . --output-format concise && ty check`

### Manual Verification
* Execute Bruno calls locally to verify feed, reaction, share count updates, and access validation blocks.

---

## Handoff (2026-05-24 convention alignment)

Completed alignment with repository conventions:

- Renamed author FK to `Feed.creator`; restored audit `created_by` CharField
- Extracted `apps/feed/enums/` and `apps/feed/services/access_policy.py`
- Added write serializers and `GlobalAPIMessageCodes` in views
- Standardized comment list pagination `meta`; added GET `/api/v1/feed/{feed_id}`
- Added btree indexes, counter floor guards, and migration `0004_feed_convention_alignment`
- Added `.github/instructions/feed.instructions.md` and Playwright/Bruno updates

Decisions applied: keep feed-specific `all` access rules; keep one-comment-per-user; no legacy data migration (greenfield); module split limited to enums + access policy.

from __future__ import annotations

import uuid
from typing import Any, cast

from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from apps.core.models import UserMaster
from apps.feed.enums import AccessType, ReactionType, SharePlatform
from shared.mixins.base_model import AuditModel


class Feed(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    creator = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="created_feeds")

    text = models.TextField(null=True)
    media_urls = models.JSONField(default=list)
    youtube_url = models.CharField(max_length=500, null=True)
    external_urls = models.JSONField(null=True)

    access_type = models.CharField(max_length=20, choices=AccessType.choices, default=AccessType.ONLY_ME)
    access_family_ids = models.JSONField(default=list, null=True)
    access_close_group_ids = models.JSONField(default=list, null=True)
    access_user_ids = models.JSONField(default=list, null=True)

    reaction_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    share_count = models.IntegerField(default=0)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "feeds"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["creator", "-created_at"], name="feeds_creator_a63108_idx"),
            models.Index(fields=["is_deleted"], name="feeds_is_dele_fd454d_idx"),
            models.Index(fields=["access_type"], name="feeds_access__6ff40b_idx"),
            models.Index(fields=["is_deleted", "-created_at"], name="feeds_active_created_idx"),
            GinIndex(fields=["access_family_ids"], name="feeds_access_family_gin_idx"),
            GinIndex(fields=["access_close_group_ids"], name="feeds_access_cg_gin_idx"),
            GinIndex(fields=["access_user_ids"], name="feeds_access_user_gin_idx"),
        ]

    def __str__(self) -> str:
        return f"Feed {self.id} by {self.creator}"

    objects: models.Manager[Feed] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]
    reactions: models.Manager[FeedReaction]
    saves: models.Manager[FeedSave]


class FeedComment(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_comments")
    comment_text = models.TextField()

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "feed_comments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["feed", "created_at"], name="feed_commen_feed_id_afc08c_idx"),
            models.Index(fields=["is_deleted"], name="feed_commen_is_dele_bcb026_idx"),
            models.Index(
                fields=["feed", "is_deleted", "created_at"],
                name="feed_commen_feed_active_idx",
            ),
            models.Index(
                fields=["feed", "user", "is_deleted"],
                name="feed_commen_feed_user_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Comment {self.id} on Feed {cast(Any, self.feed).id} by {self.user}"

    objects: models.Manager[FeedComment] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class FeedReaction(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_reactions")
    reaction = models.CharField(max_length=20, choices=ReactionType.choices)

    class Meta:
        db_table = "feed_reactions"
        constraints = [
            models.UniqueConstraint(fields=["feed", "user"], name="feed_reactions_feed_user_unique"),
        ]
        indexes = [
            models.Index(fields=["feed"], name="feed_reactions_feed_idx"),
        ]

    def __str__(self) -> str:
        return f"Reaction {self.reaction} on Feed {cast(Any, self.feed).id} by {self.user}"

    objects: models.Manager[FeedReaction] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class FeedSave(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="saves")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_saves")

    class Meta:
        db_table = "feed_saves"
        constraints = [
            models.UniqueConstraint(fields=["feed", "user"], name="feed_saves_feed_user_unique"),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="feed_saves_user_created_idx"),
            models.Index(fields=["feed"], name="feed_saves_feed_idx"),
        ]

    def __str__(self) -> str:
        return f"Save on Feed {cast(Any, self.feed).id} by {self.user}"

    objects: models.Manager[FeedSave] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class FeedShare(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="feed_shares")
    platform = models.CharField(max_length=50, choices=SharePlatform.choices)

    class Meta:
        db_table = "feed_shares"
        indexes = [
            models.Index(fields=["feed"], name="feed_shares_feed_id_c029ef_idx"),
            models.Index(fields=["user"], name="feed_shares_user_idx"),
        ]

    def __str__(self) -> str:
        return f"Share of Feed {cast(Any, self.feed).id} by {self.user} on {self.platform}"

    objects: models.Manager[FeedShare] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

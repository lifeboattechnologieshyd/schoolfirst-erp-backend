from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from apps.calendar.enums import CommentParentType
from shared.mixins.base_model import AuditModel


class Comment(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_type = models.CharField(max_length=20, choices=CommentParentType.choices)
    parent_id = models.UUIDField()
    user_id = models.UUIDField(db_index=True)
    body = models.TextField()
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "calendar_comment"
        indexes = [
            models.Index(fields=["parent_type", "parent_id"]),
        ]

    def __str__(self):
        return f"Comment by {self.user_id} on {self.parent_type}:{self.parent_id}"

    # Type declarations for static analysis
    objects: models.Manager[Comment] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

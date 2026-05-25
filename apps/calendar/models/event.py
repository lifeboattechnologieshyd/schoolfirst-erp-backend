from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from apps.calendar.mixins import AccessControlMixin, RecurringMixin
from shared.mixins.base_model import AuditModel


class Event(AuditModel, AccessControlMixin, RecurringMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True)
    event_type = models.CharField(max_length=100, null=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True)
    all_day = models.BooleanField(default=False)
    reminder_datetime = models.DateTimeField(null=True)
    reminder_types = models.JSONField(null=True)
    location = models.JSONField(null=True)
    attachments = models.JSONField(null=True)
    comment_count = models.PositiveIntegerField(default=0)
    parent_event = models.ForeignKey(
        "self",
        null=True,
        on_delete=models.CASCADE,
        related_name="overrides",
    )

    class Meta:
        db_table = "calendar_event"
        indexes = [
            models.Index(fields=["start_at"]),
            models.Index(fields=["end_at"]),
            models.Index(fields=["creator_id"]),
            models.Index(fields=["access_type"]),
        ]

    def __str__(self):
        return self.title

    # Type declarations for static analysis
    objects: models.Manager[Event] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

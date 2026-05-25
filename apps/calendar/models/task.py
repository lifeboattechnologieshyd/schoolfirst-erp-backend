from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from apps.calendar.enums import TaskPriority, TaskStatus
from apps.calendar.mixins import AccessControlMixin, RecurringMixin
from shared.mixins.base_model import AuditModel


class Task(AuditModel, AccessControlMixin, RecurringMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True)
    task_type = models.CharField(max_length=100, null=True)
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
    )
    done_by = models.UUIDField(null=True)
    completed_at = models.DateTimeField(null=True)
    acknowledged_at = models.DateTimeField(null=True)
    is_visible = models.BooleanField(default=True)
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.ROUTINE,
    )
    agent_assist = models.BooleanField(default=False)
    deadline_datetime = models.DateTimeField(null=True)
    reminder_datetime = models.DateTimeField(null=True)
    reminder_types = models.JSONField(null=True)
    location = models.JSONField(null=True)
    attachments = models.JSONField(null=True)
    comment_count = models.PositiveIntegerField(default=0)
    parent_task = models.ForeignKey(
        "self",
        null=True,
        on_delete=models.CASCADE,
        related_name="overrides",
    )

    class Meta:
        db_table = "calendar_task"
        indexes = [
            models.Index(fields=["deadline_datetime"]),
            models.Index(fields=["creator_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_visible"]),
            models.Index(fields=["access_type"]),
        ]

    def __str__(self):
        return self.title

    # Type declarations for static analysis
    objects: models.Manager[Task] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

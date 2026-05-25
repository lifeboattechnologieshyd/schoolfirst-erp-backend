from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from shared.mixins.base_model import TimeAuditModel


class GeneralEvent(TimeAuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True)
    event_at = models.DateTimeField()

    class Meta:
        db_table = "calendar_general_event"
        indexes = [
            models.Index(fields=["event_at"]),
        ]

    # Type declarations for static analysis
    objects: models.Manager[GeneralEvent] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

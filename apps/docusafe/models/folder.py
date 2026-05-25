from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from shared.enums import DocusafeStatus
from shared.mixins.base_model import AuditModel


class DocusafeFolder(AuditModel):
    """
    Root-level document folder. No sub-directories.
    Scoped to one family and owned by one user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True)
    # Cross-model references via UUIDs (no ForeignKeys per design decision #1)
    owner_id = models.UUIDField()
    # Denormalized counters — updated by the service layer
    file_count = models.PositiveIntegerField(default=0)
    total_size = models.BigIntegerField(default=0)
    # True when any file in this folder is in an active temporary share
    is_shared = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=DocusafeStatus.choices, default=DocusafeStatus.ACTIVE)

    class Meta:
        db_table = "docusafe_folder"
        verbose_name = "DocusafeFolder"
        verbose_name_plural = "DocusafeFolders"
        ordering = ["-created_at"]
        # Each (owner, folder name) must be unique
        unique_together = [("owner_id", "name")]
        indexes = [
            models.Index(fields=["owner_id"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["is_shared"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} (owner={self.owner_id})"

    # Type declarations for static analysis
    objects: models.Manager[DocusafeFolder] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

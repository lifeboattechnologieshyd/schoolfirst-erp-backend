from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from shared.enums import DocusafeAccessType
from shared.mixins.base_model import AuditModel


class DocusafeFileAccess(AuditModel):
    """
    Grants read-only access to a file.
    Access is either family-wide or per-user (must be APPROVED family member).
    Only the folder owner can create / revoke grants.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(
        "docusafe.DocusafeFile",
        on_delete=models.CASCADE,
        db_column="file_id",
        related_name="access_grants",
    )
    access_type = models.CharField(
        max_length=10,
        choices=DocusafeAccessType.choices,
        default=DocusafeAccessType.FAMILY,
    )
    # The family context for this grant
    family_id = models.UUIDField()
    # Only populated when access_type = USER
    user_id = models.UUIDField(null=True)
    # The folder owner who created this grant
    owner_id = models.UUIDField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "docusafe_file_access"
        verbose_name = "DocusafeFileAccess"
        verbose_name_plural = "DocusafeFileAccesses"
        ordering = ["-created_at"]
        unique_together = [("file", "access_type", "family_id", "user_id")]
        indexes = [
            models.Index(fields=["file"], name="docusafe_fi_file_id_c5bb17_idx"),
            models.Index(fields=["access_type"]),
            models.Index(fields=["family_id"]),
            models.Index(fields=["user_id"]),
            models.Index(fields=["owner_id"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        file_id = getattr(self, "file_id", None)
        return f"Access({self.access_type}) file={file_id} family={self.family_id}"

    # Type declarations for static analysis
    objects: models.Manager[DocusafeFileAccess] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

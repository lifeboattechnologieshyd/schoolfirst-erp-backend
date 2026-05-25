from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from shared.enums import DocusafeLLMStatus, DocusafeStatus
from shared.mixins.base_model import AuditModel


class DocusafeFile(AuditModel):
    """
    A file stored in a DocusafeFolder.

    file_path stores the S3 object key — pre-signed URLs are generated
    on-the-fly at download time (never stored).

    S3 key pattern:
        docusafe/<owner_id>/<folder_id>/<file_id>_<sanitized_filename>
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    folder = models.ForeignKey(
        "docusafe.DocusafeFolder",
        on_delete=models.PROTECT,
        db_column="folder_id",
        related_name="files",
    )
    owner_id = models.UUIDField()
    file_name = models.CharField(max_length=255)
    description = models.TextField(null=True)
    # The S3 object key (the only reference to the file in S3)
    file_path = models.CharField(max_length=1024)
    mime_type = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    file_extension = models.CharField(max_length=50)
    checksum = models.CharField(max_length=128, null=True)
    # True when included in at least one active temporary share
    is_shared = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=DocusafeStatus.choices, default=DocusafeStatus.ACTIVE)
    llm_status = models.CharField(max_length=50, choices=DocusafeLLMStatus.choices, default=DocusafeLLMStatus.PENDING)
    summary = models.TextField(null=True)
    embedding_model = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "docusafe_file"
        verbose_name = "DocusafeFile"
        verbose_name_plural = "DocusafeFiles"
        ordering = ["-created_at"]
        unique_together = [("folder", "file_name")]
        indexes = [
            models.Index(fields=["folder"], name="docusafe_fi_folder__ed32d1_idx"),
            models.Index(fields=["mime_type"]),
            models.Index(fields=["is_shared"]),
        ]

    def __str__(self) -> str:
        folder_id = getattr(self, "folder_id", None)
        return f"{self.file_name} (folder={folder_id})"

    # Type declarations for static analysis
    objects: models.Manager[DocusafeFile] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

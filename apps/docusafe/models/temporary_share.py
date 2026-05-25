from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from shared.enums import TemporaryShareStatus
from shared.mixins.base_model import AuditModel, TimeAuditModel


class TemporaryFileShare(AuditModel):
    """
    A password-protected, time-limited share link that can contain
    multiple files from across different folders.

    The share's UUID (id) is used directly in all URLs — no separate token.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Hashed via make_password — no strength constraints
    password_hash = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=TemporaryShareStatus.choices,
        default=TemporaryShareStatus.ACTIVE,
    )
    expires_at = models.DateTimeField()
    max_views = models.PositiveIntegerField(null=True)
    view_count = models.PositiveIntegerField(default=0)
    # Brute-force protection
    failed_attempts = models.PositiveIntegerField(default=0)
    max_failed_attempts = models.PositiveIntegerField(default=5)
    # Optional title for the share
    title = models.CharField(max_length=255, null=True)
    # The number of files in this share (read-only)
    file_count = models.PositiveIntegerField(default=0)
    # Owner of the share (references UserMaster.id)
    owner_id = models.UUIDField()
    # Optional — recipients will be notified if set
    recipient_emails = models.JSONField(default=list, null=True)

    class Meta:
        db_table = "docusafe_temporary_share"
        verbose_name = "TemporaryFileShare"
        verbose_name_plural = "TemporaryFileShares"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["owner_id"]),
        ]

    def __str__(self) -> str:
        return f"Share {self.id} ({self.status}) by {self.owner_id}"

    # Type declarations for static analysis
    objects: models.Manager[TemporaryFileShare] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class TemporaryShareFile(TimeAuditModel):
    """
    Junction table: associates files with a TemporaryFileShare.
    One share can include files from multiple folders.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    share = models.ForeignKey(
        "docusafe.TemporaryFileShare",
        on_delete=models.CASCADE,
        db_column="share_id",
        related_name="share_files",
    )
    file = models.ForeignKey(
        "docusafe.DocusafeFile",
        on_delete=models.CASCADE,
        db_column="file_id",
        related_name="temporary_share_files",
    )

    class Meta:
        db_table = "docusafe_temporary_share_file"
        verbose_name = "TemporaryShareFile"
        verbose_name_plural = "TemporaryShareFiles"
        unique_together = [("share", "file")]
        indexes = [
            models.Index(fields=["share"], name="docusafe_te_share_i_e6bec1_idx"),
            models.Index(fields=["file"], name="docusafe_te_file_id_793cee_idx"),
        ]

    def __str__(self) -> str:
        share_id = getattr(self, "share_id", None)
        file_id = getattr(self, "file_id", None)
        return f"ShareFile share={share_id} file={file_id}"

    # Type declarations for static analysis
    objects: models.Manager[TemporaryShareFile] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class ShareViewLog(TimeAuditModel):
    """
    Immutable audit log of every access attempt against a TemporaryFileShare.
    Captures both successful and failed attempts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    share = models.ForeignKey(
        "docusafe.TemporaryFileShare",
        on_delete=models.CASCADE,
        db_column="share_id",
        related_name="view_logs",
    )
    success = models.BooleanField()
    # Failure reason: INVALID_PASSWORD | EXPIRED | BLOCKED
    # | MAX_VIEWS_REACHED | DISABLED
    failure_reason = models.CharField(max_length=100, null=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(max_length=50, null=True)
    device_os = models.CharField(max_length=100, null=True)
    browser = models.CharField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=100, null=True)
    # Extensible bag for additional client context (screen resolution, timezone, etc.)
    client_metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "docusafe_share_view_log"
        verbose_name = "ShareViewLog"
        verbose_name_plural = "ShareViewLogs"
        indexes = [
            models.Index(fields=["share"], name="docusafe_sh_share_i_56d9cd_idx"),
            models.Index(fields=["viewed_at"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["success"]),
        ]

    def __str__(self) -> str:
        outcome = "OK" if self.success else f"FAIL({self.failure_reason})"
        share_id = getattr(self, "share_id", None)
        return f"ViewLog share={share_id} {outcome}"

    # Type declarations for static analysis
    objects: models.Manager[ShareViewLog] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

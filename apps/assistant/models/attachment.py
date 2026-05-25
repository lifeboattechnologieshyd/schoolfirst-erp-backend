"""
Attachment Model and related logic for the Assistant application.
Handles file associations with threads and messages.
"""
from __future__ import annotations

import posixpath
import uuid

import structlog
from django.db import models

from shared.mixins.base_model import TimeAuditModel
from shared.utils.files import get_file_info, move_file

logger = structlog.get_logger("default")


class Attachment(TimeAuditModel):
    """
    Represents a file attachment associated with a thread
    and optionally a specific message.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects: models.Manager[Attachment] = models.Manager()
    thread_id = models.UUIDField(db_index=True, help_text="ID of the thread")
    message_id = models.UUIDField(db_index=True, help_text="ID of the message this attachment belongs to")
    file_path = models.CharField(max_length=500, help_text="Storage path of the file")
    file_name = models.CharField(max_length=255, help_text="Original file name")
    file_size = models.BigIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, help_text="MIME type of the file")
    width = models.IntegerField(null=True, help_text="Image/video width in pixels")
    height = models.IntegerField(null=True, help_text="Image/video height in pixels")
    duration = models.IntegerField(null=True, help_text="Audio/video duration in seconds")

    class Meta:
        db_table = "attachment"
        verbose_name = "Attachment"
        verbose_name_plural = "Attachments"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["thread_id", "message_id"]),
        ]

    def __str__(self) -> str:
        return f"Attachment {self.file_name} for Message {self.message_id}"

    # Allowed prefix for user-uploaded temp files. Must match the upload view's folder.
    _TEMP_FILE_PREFIX = "temp/"

    @classmethod
    def _validate_temp_path(cls, temp_path: str) -> bool:
        """Return True only if the path is safely within the temp upload folder."""
        if not isinstance(temp_path, str):
            return False
        candidate = temp_path.strip()
        if not candidate or "\\" in candidate or "\x00" in candidate:
            return False

        normalised = posixpath.normpath(candidate)
        if normalised.startswith("/"):
            return False

        if not normalised.startswith(cls._TEMP_FILE_PREFIX):
            return False

        relative_path = normalised[len(cls._TEMP_FILE_PREFIX) :]
        return bool(relative_path and relative_path not in {".", ".."})

    @classmethod
    def process_for_message(cls, thread_id: uuid.UUID, message_id: uuid.UUID, raw_attachments: list[str]) -> None:
        """Move temp files and create Attachment records."""
        if not raw_attachments:
            return

        dest_folder = f"assistant/{thread_id}"
        logger.info("Processing attachments", count=len(raw_attachments), thread_id=thread_id)

        attachments_to_create = []
        for temp_path in raw_attachments:
            if not cls._validate_temp_path(temp_path):
                logger.warning("Rejected attachment path outside temp folder", temp_path=temp_path)
                continue

            moved_path = move_file(temp_path, dest_folder)
            if not moved_path:
                logger.warning("Could not move file", temp_path=temp_path)
                continue

            file_info = get_file_info(moved_path)
            if file_info:
                attachments_to_create.append(
                    cls(
                        message_id=message_id,
                        thread_id=thread_id,
                        file_path=file_info["file_path"],
                        file_name=file_info["file_name"],
                        file_size=file_info["file_size"],
                        mime_type=file_info["mime_type"],
                    )
                )

        if attachments_to_create:
            cls.objects.bulk_create(attachments_to_create)

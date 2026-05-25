"""
Message Model for the Assistant application.
Represents individual turns in a thread conversation.
"""
from __future__ import annotations

import uuid
from typing import cast

from django.db import models

from apps.assistant.enums import MessageSenderType
from shared.mixins.base_model import TimeAuditModel


class Message(TimeAuditModel):
    """
    Represents a single message in a conversation thread.
    Can be from a user or the LLM assistant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects: models.Manager[Message] = models.Manager()  # type: ignore[assignment, misc]
    thread_id = models.UUIDField(help_text="ID of the thread this message belongs to")
    sender_type = models.CharField(
        max_length=10, choices=MessageSenderType.choices, default=MessageSenderType.USER, help_text="Sender type"
    )
    content_blocks = models.JSONField(null=True, help_text="Typed content block array (tool_call, text)")
    schema_version = models.CharField(max_length=10, default="2.0", help_text="Content block schema version")
    role_metadata = models.JSONField(
        null=True,
        help_text="Assistant-only metadata: stop_reason, model, usage",
    )

    class Meta:
        db_table = "message"
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["thread_id"]),
            models.Index(fields=["sender_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["thread_id", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Message {self.id} ({self.sender_type}) in Thread {self.thread_id}"

    @property
    def text(self) -> str:
        """Extract plain text from content_blocks."""
        if not isinstance(self.content_blocks, list):
            return ""

        text_parts: list[str] = []
        for raw_block in self.content_blocks:
            if not isinstance(raw_block, dict):
                continue

            block = cast(dict[str, object], raw_block)
            if block.get("type") == "text":
                val = block.get("text")
                if isinstance(val, str) and val:
                    text_parts.append(val)

        return "".join(text_parts).strip()

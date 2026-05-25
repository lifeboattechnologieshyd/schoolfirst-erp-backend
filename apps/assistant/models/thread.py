"""
Thread Model and related logic for the Assistant application.
Each thread represents a separate conversation between a user and the AI.
"""
from __future__ import annotations

import uuid

from django.db import models
from langchain_core.messages import BaseMessage, HumanMessage

from apps.assistant.content_blocks import build_langchain_messages_from_assistant_blocks
from apps.assistant.enums import DEFAULT_THREAD_NAME, MessageSenderType, ThreadStatus
from apps.assistant.models.message import Message
from shared.mixins.base_model import TimeAuditModel


class Thread(TimeAuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, help_text="Thread ID")
    objects: models.Manager[Thread] = models.Manager()
    user_id = models.UUIDField(db_index=True, help_text="ID of the user who owns this thread")
    name = models.CharField(max_length=255, default=DEFAULT_THREAD_NAME, help_text="Thread name")
    status = models.CharField(
        max_length=20,
        choices=ThreadStatus.choices,
        default=ThreadStatus.ACTIVE,
        help_text="Thread status",
    )
    summary = models.TextField(null=True, help_text="Auto-generated thread summary")
    model = models.CharField(max_length=200, null=True, help_text="LLM model ID used in this thread")
    settings = models.JSONField(null=True, help_text='Per-thread feature flags e.g. {"enabled_web_search": true}')
    module_settings = models.JSONField(null=True, help_text='Module specific settings e.g. {"module_name": "docusafe"}')
    is_temporary = models.BooleanField(
        default=False, help_text="Temporary chats excluded from history (e.g., for one-off tasks)"
    )

    class Meta:
        db_table = "thread"
        verbose_name = "Thread"
        verbose_name_plural = "Threads"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user_id", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["user_id", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Thread {self.id} - {self.name} (User: {self.user_id})"

    def get_recent_history(self, limit: int = 20, exclude_message_id: uuid.UUID | None = None) -> list[BaseMessage]:
        """
        Retrieves the most recent messages for this thread,
        formatted as LangChain message objects.

        LLM messages that contain tool_call blocks are reconstructed as an
        AIMessage (with tool_calls) followed by ToolMessage results so the
        model receives complete multi-turn tool context.
        """

        messages = Message.objects.filter(thread_id=self.id)
        if exclude_message_id:
            messages = messages.exclude(id=exclude_message_id)

        history_msgs = messages.order_by("-created_at")[:limit]

        results: list[BaseMessage] = []
        for msg in reversed(history_msgs):
            if msg.sender_type == MessageSenderType.USER:
                history_text = msg.text
                if history_text:
                    results.append(HumanMessage(content=history_text))
                continue

            # Assistant message — reconstruct with tool calls if present
            blocks = msg.content_blocks if isinstance(msg.content_blocks, list) else []
            text_content = msg.text
            assistant_messages = build_langchain_messages_from_assistant_blocks(blocks, text_content)
            results.extend(assistant_messages)

        return results

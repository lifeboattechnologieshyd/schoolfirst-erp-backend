"""
Conversation Service for orchestrating chat lifecycles.
Handles message persistence, thread resolution, and failure logging.
"""

import uuid

import structlog
from django.shortcuts import get_object_or_404
from langchain_core.messages import BaseMessage, HumanMessage

from apps.assistant.enums import DEFAULT_MODEL_NAME, MessageSenderType, StopReason
from apps.assistant.models import Attachment, Message, Thread
from apps.assistant.services.llm_factory import get_active_chat_model_display_name

logger = structlog.get_logger("default")


class ConversationService:
    """
    Orchestrates the lifecycle of a chat interaction.
    Handles thread resolution, message persistence, and state cleanup.
    """

    @staticmethod
    def prepare_chat_context(
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        attachments: list[str] | None = None,
    ) -> tuple[Thread, Message, list[BaseMessage]]:
        """
        1. Resolve thread ownership.
        2. Persist user message.
        3. Process attachments.
        4. Return (thread, user_message, combined_history).
        """
        thread = get_object_or_404(Thread, id=thread_id, user_id=user_id)

        # Save User Message
        user_message = Message.objects.create(
            thread_id=thread.id,
            sender_type=MessageSenderType.USER,
            content_blocks=[{"type": "text", "block_index": 0, "text": content}],
        )

        # Process file attachments
        if attachments:
            Attachment.process_for_message(thread.id, user_message.id, attachments)

        # Get history (returns LangChain message objects)
        messages = thread.get_recent_history(limit=20, exclude_message_id=user_message.id)
        messages.append(HumanMessage(content=content))

        return thread, user_message, messages

    @staticmethod
    def finalize_assistant_message(
        thread_id: uuid.UUID,
        content_blocks: list[dict],
        role_metadata: dict | None = None,
        message_id: uuid.UUID | None = None,
    ) -> None:
        """
        Persist the assistant response to the database.

        Args:
            thread_id: ID of the thread.
            content_blocks: List of structured content blocks (v2 collapsed format).
            role_metadata: Assistant metadata dict with stop_reason, model, usage.
            message_id: Optional pre-generated UUID so the stored record matches
                        the ID already emitted to the client (e.g. in SSE streams).
        """
        model_name = get_active_chat_model_display_name() or DEFAULT_MODEL_NAME

        # Ensure role_metadata has model set
        if role_metadata is None:
            role_metadata = {"stop_reason": StopReason.END_TURN, "model": model_name}
        elif "model" not in role_metadata:
            role_metadata["model"] = model_name

        create_kwargs: dict = {
            "thread_id": thread_id,
            "sender_type": MessageSenderType.ASSISTANT,
            "content_blocks": content_blocks,
            "schema_version": "2.0",
            "role_metadata": role_metadata,
        }
        if message_id is not None:
            create_kwargs["id"] = message_id

        # Save assistant message
        Message.objects.create(**create_kwargs)

        # Stamp the model used on the thread if not already set
        Thread.objects.filter(id=thread_id, model__isnull=True).update(model=model_name)

    @staticmethod
    def handle_message_failure(user_message: Message) -> None:
        """Log failure for a user message instead of deleting it."""
        logger.warning("Generation failed for user message", message_id=user_message.id)
        # We no longer delete the message or attachments to preserve user input
        # and audit trail.

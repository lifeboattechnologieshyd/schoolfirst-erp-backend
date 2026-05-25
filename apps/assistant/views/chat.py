"""
Chat Views for the Assistant application.
Handles message submission and streaming/direct responses from the LLM.
"""

import uuid
from typing import Any

import structlog
from botocore.exceptions import BotoCoreError, ClientError
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from langchain_core.messages import BaseMessage
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.assistant.enums import DEFAULT_INTENT, DEFAULT_MODEL_NAME, StopReason
from apps.assistant.models import Message, Thread
from apps.assistant.serializers import ChatRequestSerializer, MessageSerializer
from apps.assistant.services.conversation_service import ConversationService
from apps.assistant.services.llm_factory import get_active_chat_model_display_name, get_llm_service
from shared.mixins.drf_views import CustomListAPIView, CustomResponse
from shared.streaming import ContentBlockStreamProcessor, build_message_delta, build_message_stop

logger = structlog.get_logger("default")


class ChatView(APIView, CustomResponse):
    """
    API View to handle sending messages to a thread and getting LLM response.

    POST /api/assistant/threads/{id}/chat/
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "chat_message"

    def post(self, request: Request, thread_id: Any) -> Response | StreamingHttpResponse:
        user_id = request.user.id
        logger.info("Chat request received", user_id=user_id, thread_id=thread_id)

        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            error_details = serializer.errors
            error_msg = "Validation failed"
            if "attachments" in error_details:
                error_msg = "attachments must be a list"
            elif "content" in error_details:
                error_msg = "Content is required"

            return self.build_response(
                success=False,
                error={"message": error_msg, "code": "VALIDATION_ERROR", "details": error_details},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_data = serializer.validated_data
        content = validated_data["content"]
        use_streaming = validated_data["stream"]
        attachments = validated_data.get("attachments", [])

        llm_service = get_llm_service()

        # Prepare chat context (thread, user message, history)
        thread, user_message, messages = ConversationService.prepare_chat_context(
            thread_id=thread_id,
            user_id=user_id,
            content=content,
            attachments=attachments,
        )

        if use_streaming:
            return self._handle_streaming(llm_service, messages, thread, user_message, user_id=user_id)

        return self._handle_direct(llm_service, messages, thread, user_message, user_id=user_id)

    def _handle_direct(
        self,
        llm_service: Any,
        messages: list[BaseMessage],
        thread: Thread,
        user_message: Message,
        user_id: uuid.UUID | None = None,
    ) -> Response:
        """Returns a standard JSON response with the LLM reply."""
        try:
            result = llm_service.generate_response(messages, thread_id=thread.id, user_id=user_id)
            response_text = result.text
            content_blocks = list(result.content_blocks) or [{"type": "text", "text": response_text}]

            role_metadata = {
                "stop_reason": StopReason.END_TURN,
                "model": get_active_chat_model_display_name() or DEFAULT_MODEL_NAME,
            }
            ConversationService.finalize_assistant_message(
                uuid.UUID(str(thread.id)),
                content_blocks,
                role_metadata=role_metadata,
            )

            return self.build_response(
                success=True,
                message="Here's your response.",
                data={
                    "message": response_text,
                    "intent_name": result.intent_name or DEFAULT_INTENT,
                },
                status=status.HTTP_200_OK,
            )

        except (BotoCoreError, ClientError) as e:
            logger.exception(
                "LLM provider API error",
                error=str(e),
                thread_id=str(thread.id),
                user_id=str(user_id) if user_id else None,
                user_message_id=str(user_message.id),
            )
            ConversationService.handle_message_failure(user_message)
            return self.build_response(
                success=False,
                error={"message": "LLM service is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception(
                "Unexpected error during chat",
                error=str(e),
                thread_id=str(thread.id),
                user_id=str(user_id) if user_id else None,
                user_message_id=str(user_message.id),
            )
            ConversationService.handle_message_failure(user_message)
            return self.build_response(
                success=False,
                error={"message": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_streaming(
        self,
        llm_service: Any,
        messages: list[BaseMessage],
        thread: Thread,
        user_message: Message,
        user_id: uuid.UUID | None = None,
    ) -> StreamingHttpResponse:
        """Returns a StreamingHttpResponse (Server-Sent Events)."""
        pre_generated_id = uuid.uuid4()
        message_id = str(pre_generated_id)
        model_name = get_active_chat_model_display_name() or DEFAULT_MODEL_NAME

        def event_stream():
            try:
                response_stream = llm_service.generate_streaming_response(
                    messages, thread_id=thread.id, user_id=user_id
                )
                processor = ContentBlockStreamProcessor(message_id=message_id, model=model_name)

                yield from processor.process_stream(response_stream)

                # Persist the full response using the same UUID emitted in the stream
                if (full_text := processor.get_accumulated_response()) and full_text.strip():
                    ConversationService.finalize_assistant_message(
                        uuid.UUID(str(thread.id)),
                        processor.get_content_blocks(),
                        role_metadata=processor.get_role_metadata(),
                        message_id=pre_generated_id,
                    )

            except Exception as e:
                logger.exception(
                    "Streaming LLM response failed",
                    error=str(e),
                    thread_id=str(thread.id),
                    user_id=str(user_id) if user_id else None,
                    user_message_id=str(user_message.id),
                    assistant_message_id=message_id,
                )
                ConversationService.handle_message_failure(user_message)
                yield build_message_delta(stop_reason=StopReason.ERROR)
                yield build_message_stop()

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class MessageListView(CustomListAPIView):
    """
    List messages for a thread.
    GET /api/assistant/threads/{id}/messages/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self) -> QuerySet[Message]:
        user_id = self.request.user.id
        thread_id = self.kwargs["thread_id"]
        thread = get_object_or_404(Thread, id=thread_id, user_id=user_id)
        return Message.objects.filter(thread_id=thread.id).order_by("created_at")

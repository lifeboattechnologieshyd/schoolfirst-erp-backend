from django.db import models


class MessageSenderType(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class StopReason(models.TextChoices):
    END_TURN = "end_turn", "End Turn"
    MAX_TOKENS = "max_tokens", "Max Tokens"
    ERROR = "error", "Error"
    TOOL_USE = "tool_use", "Tool Use"

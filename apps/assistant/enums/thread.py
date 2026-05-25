from django.db import models

DEFAULT_THREAD_NAME = "New Chat"
DEFAULT_MODEL_NAME = "assistant-model"
DEFAULT_INTENT = "schoolfirst_assistant"


class ThreadStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"
    DELETED = "DELETED", "Deleted"

from django.db import models


class CommentParentType(models.TextChoices):
    EVENT = "event", "Event"
    TASK = "task", "Task"

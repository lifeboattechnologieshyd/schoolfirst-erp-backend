from django.db import models


class TaskStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    DONE = "done", "Done"


class TaskPriority(models.TextChoices):
    ROUTINE = "routine", "Routine"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"

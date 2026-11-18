import uuid

from django.db import models

from shared.mixins import AuditModel


class Activities(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    date = models.DateField(
        unique=True,
    )

    title = models.CharField(
        max_length=255,
    )

    theme = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    prompt = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    benefit = models.TextField(
        null=True,
        blank=True,
    )

    youtube_video_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    image = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "calendar"
        ordering = ["date"]

        indexes = [
            models.Index(
                fields=["date"],
                name="calendar_date_idx",
            ),
            models.Index(
                fields=["theme"],
                name="calendar_theme_idx",
            ),
        ]

    def __str__(self):
        return self.title


class ActivitySteps(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    activities = models.ForeignKey(
        Activities,
        on_delete=models.CASCADE,
        related_name="activity_steps",
    )

    step_number = models.PositiveIntegerField()

    title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    description = models.TextField()

    image = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "calendar_activity_steps"
        ordering = ["step_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["activities", "step_number"],
                name="unique_calendar_activity_step",
            ),
        ]

        indexes = [
            models.Index(
                fields=["activities", "step_number"],
                name="activity_step_order_idx",
            ),
        ]

    def __str__(self):
        return f"{self.activities.title} - Step {self.step_number}"
import uuid

from django.db import models

from apps.core.models import UserMaster
from apps.school.models import School
from apps.school.models.school import Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class FeedbackCategory(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="feedback_categories",
    )

    name = models.CharField(max_length=100)

    description = models.TextField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "feedback_categories"

        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_feedback_category_per_school",
            )
        ]

        indexes = [
            models.Index(fields=["school", "is_active"]),
        ]

    def __str__(self):
        return self.name

class Feedback(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        IN_REVIEW = "IN_REVIEW", "In Review"
        RESOLVED = "RESOLVED", "Resolved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="parent_feedbacks",
    )

    parent = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="submitted_feedbacks",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="parent_feedbacks",
    )

    category = models.ForeignKey(
        FeedbackCategory,
        on_delete=models.PROTECT,
        related_name="feedbacks",
    )

    subject = models.CharField(max_length=255)

    message = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )

    class Meta:
        db_table = "feedbacks"

        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["parent", "created_at"]),
            models.Index(fields=["student"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.subject


class FeedbackResponse(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    feedback = models.ForeignKey(
        Feedback,
        on_delete=models.CASCADE,
        related_name="responses",
    )

    responded_by = models.ForeignKey(
        UserMaster,
        on_delete=models.PROTECT,
        related_name="feedback_responses",
    )

    message = models.TextField()

    class Meta:
        db_table = "feedback_responses"

        indexes = [
            models.Index(fields=["feedback", "created_at"]),
            models.Index(fields=["responded_by"]),
        ]

    def __str__(self):
        return f"Response to {self.feedback.subject}"
import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear, Grade
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class ExaminationType(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="examination_types",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="examination_types",
    )

    name = models.CharField(
        max_length=100,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    weightage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Weightage percentage",
    )

    max_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=100,
        help_text="Maximum marks",
    )

    frequency = models.PositiveIntegerField(
        default=1,
        help_text="Number of times this examination type occurs in an academic year",
    )

    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration in minutes",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        db_table = "examination_types"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "name",
                ],
                name="unique_examination_type_name_per_school",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["status"]),
            models.Index(
                fields=[
                    "school",
                    "status",
                ]
            ),
        ]

    def __str__(self):
        return self.name


class Examination(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="examinations",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="examinations",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="examinations",
    )

    examination_type = models.ForeignKey(
        ExaminationType,
        on_delete=models.PROTECT,
        related_name="examinations",
    )

    name = models.CharField(
        max_length=255,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "examinations"

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["academic_year"]),
            models.Index(fields=["examination_type"]),
            models.Index(fields=["status"]),
            models.Index(
                fields=[
                    "school",
                    "academic_year",
                ]
            ),
        ]

    def __str__(self):
        return self.name

class ExaminationGrade(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    examination = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name="examination_grades",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="examination_grades",
    )

    class Meta:
        db_table = "examination_grades"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "examination",
                    "grade",
                ],
                name="unique_examination_grade",
            ),
        ]

        indexes = [
            models.Index(fields=["examination"]),
            models.Index(fields=["grade"]),
        ]

    def __str__(self):
        return f"{self.examination.name} - {self.grade.name}"
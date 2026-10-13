import uuid

from django.db import models
from django.utils import timezone

from apps.core.models import UserMaster
from apps.school.models import School
from apps.school.models.school import Student, Subject, Section, Grade, Staff
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel




class RemarkCategory(AuditModel):
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
        related_name="remark_categories",
    )

    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "remark_categories"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_remark_category_per_school",
            )
        ]
        indexes = [
            models.Index(fields=["school", "is_active"]),
        ]

    def __str__(self):
        return self.name


class Remark(AuditModel):
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
        related_name="student_remarks",
    )
    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name="student_remarks",
    )
    category = models.ForeignKey(
        RemarkCategory,
        on_delete=models.PROTECT,
        related_name="student_remarks",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="remarks",
    )

    teacher = models.ForeignKey(
        Staff,
        on_delete=models.PROTECT,
        related_name="created_student_remarks",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="student_remarks",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        related_name="student_remarks",
        null=True,
        blank=True,
    )

    date = models.DateField(
        default=timezone.localdate,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    context = models.CharField(
        max_length=100,
        null=True,
        blank=True,

    )
    is_visible_to_staff = models.BooleanField(
        default=True,
    )

    is_visible_to_parent = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "remarks"

        indexes = [
            models.Index(
                fields=["school", "student", "date"],
            ),

            models.Index(
                fields=["school", "is_visible_to_parent"],
            ),
        ]

    def __str__(self):
        return f"{self.student} - {self.title}"
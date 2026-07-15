import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear, Grade, Subject, Staff, Section, Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class Assignment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        CLOSED = "CLOSED", "Closed"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    school = models.ForeignKey(School,on_delete=models.CASCADE,)
    branch = models.ForeignKey(Branch,on_delete=models.SET_NULL,null=True,blank=True,)
    academic_year = models.ForeignKey(AcademicYear,on_delete=models.CASCADE,)
    grade = models.ForeignKey(Grade,on_delete=models.CASCADE,)
    subject = models.ForeignKey(Subject,on_delete=models.CASCADE,)
    teacher = models.ForeignKey( Staff,on_delete=models.PROTECT,)
    title = models.CharField(max_length=255)
    description = models.TextField()
    assigned_date = models.DateField()
    due_date = models.DateField()
    total_marks = models.PositiveIntegerField(default=100)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    class Meta:
        db_table = "assignments"

        ordering = [
            "-assigned_date",
            "-created_at",
        ]

        indexes = [
                   models.Index(fields=["status",]),
                   models.Index(fields=[ "assigned_date",]),
                   models.Index(fields=["due_date",]),
                   models.Index(fields=["school","academic_year",]),
                   models.Index(fields=["grade","subject",]),
        ]


class AssignmentSection(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    assignment = models.ForeignKey(Assignment,on_delete=models.CASCADE,related_name="assignment_sections",)
    section = models.ForeignKey(Section,on_delete=models.CASCADE,)

    class Meta:
        db_table = "assignment_sections"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "assignment",
                    "section",
                ],
                name="unique_assignment_section",
            )
        ]

        indexes = [models.Index(fields=["assignment",]),
                   models.Index(fields=[ "section",]),]

class AssignmentAttachment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    assignment = models.ForeignKey(Assignment,on_delete=models.CASCADE,related_name="attachments",)
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()

    class Meta:
        db_table = "assignment_attachments"

        indexes = [models.Index(fields=["assignment",]),]

class AssignmentSubmission(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()


    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUBMITTED = "SUBMITTED", "Submitted"
        LATE = "LATE", "Late"
        EVALUATED = "EVALUATED", "Evaluated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assignment = models.ForeignKey(Assignment,on_delete=models.CASCADE,related_name="submissions",)
    student = models.ForeignKey(Student,on_delete=models.CASCADE,related_name="assignment_submissions",)
    submitted_at = models.DateTimeField(null=True,blank=True,)
    marks = models.DecimalField(max_digits=5,decimal_places=2,null=True,blank=True,)
    feedback = models.TextField(null=True,blank=True,)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,)

    class Meta:

        db_table = "assignment_submissions"

        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="unique_assignment_submission",
            )
        ]

        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assignment", "student"]),
        ]

class AssignmentSubmissionAttachment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    assignment_submission = models.ForeignKey(AssignmentSubmission,on_delete=models.CASCADE,related_name="attachments",)
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()

    class Meta:

        db_table = "assignment_submission_attachments"

        indexes = [
            models.Index(fields=["assignment_submission"]),
        ]
import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear, Grade, Staff, Section, Subject, Student
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class Homework(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    school = models.ForeignKey(School,on_delete=models.CASCADE,related_name="homeworks",)
    branch = models.ForeignKey(Branch,on_delete=models.SET_NULL,null=True,blank=True,related_name="homeworks",)
    academic_year = models.ForeignKey(AcademicYear,on_delete=models.CASCADE,related_name="homeworks",)
    grade = models.ForeignKey(Grade,on_delete=models.CASCADE,related_name="homeworks",)
    subject = models.ForeignKey(Subject,on_delete=models.CASCADE,related_name="homeworks",)
    teacher = models.ForeignKey(Staff,on_delete=models.PROTECT,related_name="created_homeworks",)
    title = models.CharField(max_length=255)
    description = models.TextField()
    assigned_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT,)

    class Meta:
        db_table = "homeworks"

        ordering = [
            "-assigned_date",
            "-created_at",
        ]

        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assigned_date"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["school", "academic_year"]),
            models.Index(fields=["grade", "subject"]),
        ]



class HomeworkSection(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    homework = models.ForeignKey(Homework,on_delete=models.CASCADE,related_name="homework_sections",)
    section = models.ForeignKey(Section,on_delete=models.CASCADE,related_name="homework_sections")

    class Meta:
        db_table = "homework_sections"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "homework",
                    "section",
                ],
                name="unique_homework_section",
            )
        ]

        indexes = [models.Index(fields=["homework",]),
                   models.Index(fields=["section",]),]

class HomeworkAttachment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    homework = models.ForeignKey(Homework,on_delete=models.CASCADE,related_name="attachments",)
    file_name = models.CharField(max_length=255)

    file_url = models.URLField()

    class Meta:
        db_table = "homework_attachments"

class HomeworkSubmission(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUBMITTED = "SUBMITTED", "Submitted"
        CHECKED = "CHECKED", "Checked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    homework = models.ForeignKey(Homework,on_delete=models.CASCADE, related_name="submissions",)
    student = models.ForeignKey(Student,on_delete=models.CASCADE,related_name="homework_submissions",)
    submitted_at = models.DateTimeField(null=True,blank=True,)
    remarks = models.TextField(null=True,blank=True,)
    teacher_remarks = models.TextField(null=True,blank=True,)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,)

    class Meta:

        db_table = "homework_submissions"

        constraints = [
            models.UniqueConstraint(
                fields=["homework", "student"],
                name="unique_homework_submission",
            )
        ]

        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["homework", "student"]),
        ]

class HomeworkSubmissionAttachment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    homework_submission = models.ForeignKey(HomeworkSubmission, on_delete=models.CASCADE,related_name="attachments",)
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()

    class Meta:

        db_table = "homework_submission_attachments"

        indexes = [
            models.Index(fields=["homework_submission"]),
        ]
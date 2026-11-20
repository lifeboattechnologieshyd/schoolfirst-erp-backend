
import uuid
from django.db import models

from shared.mixins import AuditModel


class Curriculum(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    title = models.CharField(max_length=200)

    description = models.TextField(
        null=True,
        blank=True
    )
    grade = models.ForeignKey(
        "vocabbee.Grades",
        on_delete=models.PROTECT,
        related_name="curriculums"
    )

    thumbnail_image = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    serial_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum"
        ordering = ["serial_number"]


class CurriculumLevel(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="levels"
    )

    name = models.CharField(max_length=100)

    serial_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum_levels"
        ordering = ["serial_number"]


class CurriculumCategory(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    name = models.CharField(max_length=150)

    description = models.TextField(
        null=True,
        blank=True
    )

    thumbnail_image = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    serial_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum_categories"
        ordering = ["serial_number"]


class CurriculumSubject(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    category = models.ForeignKey(
        CurriculumCategory,
        on_delete=models.CASCADE,
        related_name="subjects"
    )

    name = models.CharField(max_length=150)

    description = models.TextField(
        null=True,
        blank=True
    )

    thumbnail_image = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    total_lessons = models.PositiveIntegerField(default=0)

    serial_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum_subjects"
        ordering = ["serial_number"]





class CurriculumLesson(AuditModel):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    subject = models.ForeignKey(
        CurriculumSubject,
        on_delete=models.CASCADE,
        related_name="lessons"
    )

    title = models.CharField(max_length=200)

    description = models.TextField(
        null=True,
        blank=True
    )

    thumbnail_image = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    estimated_duration = models.PositiveIntegerField(
        default=0,
        help_text="Estimated duration in minutes"
    )

    total_pages = models.PositiveIntegerField(default=0)

    serial_number = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum_lessons"
        ordering = ["serial_number"]

    def __str__(self):
        return self.title


class CurriculumLessonPage(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    lesson = models.ForeignKey(
        CurriculumLesson,
        on_delete=models.CASCADE,
        related_name="pages"
    )

    title = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    serial_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum_lesson_pages"
        ordering = ["serial_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "serial_number"],
                name="unique_curriculum_lesson_page_number"
            )
        ]

    def __str__(self):
        return f"{self.lesson.title} - Page {self.serial_number}"

class CurriculumPageContent(AuditModel):

    class ContentType(models.TextChoices):
        HEADING = "HEADING", "Heading"
        TEXT = "TEXT", "Text"
        IMAGE = "IMAGE", "Image"
        VIDEO = "VIDEO", "Video"
        PDF = "PDF", "PDF"
        AUDIO = "AUDIO", "Audio"
        QUESTION = "QUESTION", "Question"
        ACTIVITY = "ACTIVITY", "Activity"
        INFO_BOX = "INFO_BOX", "Info Box"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    page = models.ForeignKey(
        CurriculumLessonPage,
        on_delete=models.CASCADE,
        related_name="contents"
    )

    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices
    )

    title = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    content = models.TextField(
        null=True,
        blank=True
    )

    media_url = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    serial_number = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "curriculum_page_contents"
        ordering = ["serial_number"]

    def __str__(self):
        return f"{self.content_type} - {self.page}"
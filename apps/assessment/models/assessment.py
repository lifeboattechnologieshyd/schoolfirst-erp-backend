import uuid

from django.db import models

from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class Assessment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    curriculum = models.ForeignKey(
        "curriculum.Curriculum",
        on_delete=models.PROTECT,
        related_name="assessments",
    )

    grade = models.ForeignKey(
        "vocabbee.Grades",
        on_delete=models.PROTECT,
        related_name="assessments",
    )

    subject = models.ForeignKey(
        "curriculum.CurriculumSubject",
        on_delete=models.PROTECT,
        related_name="assessments",
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    cover_image = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    time_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time limit in minutes. Null means no limit.",
    )

    total_questions = models.PositiveIntegerField(
        default=0,
    )

    total_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "assessments"

        ordering = [
            "-created_at",
        ]

        constraints = [
            # "A test with this title already exists for Grade 2 Science"
            models.UniqueConstraint(
                fields=[
                    "grade",
                    "subject",
                    "title",
                ],
                condition=models.Q(is_deleted=False),
                name="unique_assessment_title_per_grade_subject",
            ),
        ]

        indexes = [
            models.Index(fields=["curriculum"]),
            models.Index(fields=["status"]),
            models.Index(
                fields=[
                    "grade",
                    "subject",
                ]
            ),
        ]

    def __str__(self):
        return self.title


# =====================================================================
#  ASSESSMENT LESSONS
#  Step 2 (Lessons) - lessons selected for the assessment
# =====================================================================
class AssessmentLesson(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="assessment_lessons",
    )

    lesson = models.ForeignKey(
        "curriculum.CurriculumLesson",
        on_delete=models.PROTECT,
        related_name="assessment_lessons",
    )

    class Meta:
        db_table = "assessment_lessons"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "assessment",
                    "lesson",
                ],
                condition=models.Q(is_deleted=False),
                name="unique_assessment_lesson",
            ),
        ]

        indexes = [
            models.Index(fields=["assessment"]),
            models.Index(fields=["lesson"]),
        ]

    def __str__(self):
        return f"{self.assessment.title} - {self.lesson.title}"


# =====================================================================
#  ASSESSMENT QUESTION (QUESTION BANK)
#  Question bank, Question editor, Bulk upload
#  Lesson is optional ("All lessons" in bulk upload)
# =====================================================================
class AssessmentQuestion(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Level(models.TextChoices):
        BASIC = "BASIC", "Basic"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        ADVANCED = "ADVANCED", "Advanced"

    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "SINGLE_CHOICE", "Single Choice"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    grade = models.ForeignKey(
        "vocabbee.Grades",
        on_delete=models.PROTECT,
        related_name="assessment_questions",
    )

    subject = models.ForeignKey(
        "curriculum.CurriculumSubject",
        on_delete=models.PROTECT,
        related_name="assessment_questions",
    )

    lesson = models.ForeignKey(
        "curriculum.CurriculumLesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_questions",
    )

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE_CHOICE,
    )

    question = models.TextField()

    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.BASIC,
    )

    marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1,
    )

    hint = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    explanation = models.TextField(
        null=True,
        blank=True,
    )

    image = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "assessment_questions"

        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(fields=["level"]),
            models.Index(fields=["is_active"]),
            models.Index(
                fields=[
                    "grade",
                    "subject",
                ]
            ),
            models.Index(fields=["lesson"]),
        ]

    def __str__(self):
        return self.question[:50]


# =====================================================================
#  ASSESSMENT QUESTION OPTIONS
#  option_a..option_d, correct = A/B/C/D
# =====================================================================
class AssessmentQuestionOption(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Label(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )

    label = models.CharField(
        max_length=2,
        choices=Label.choices,
    )

    option_text = models.CharField(
        max_length=500,
    )

    is_correct = models.BooleanField(
        default=False,
    )

    serial_number = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        db_table = "assessment_question_options"

        ordering = [
            "serial_number",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "question",
                    "label",
                ],
                condition=models.Q(is_deleted=False),
                name="unique_assessment_question_option_label",
            ),
        ]

        indexes = [
            models.Index(fields=["question"]),
        ]

    def __str__(self):
        return f"{self.label}. {self.option_text}"


# =====================================================================
#  ASSESSMENT QUESTION MAPPING
#  Step 3 (Questions) - questions added to an assessment
#  serial_number supports drag-to-reorder
# =====================================================================
class AssessmentQuestionMapping(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="question_mappings",
    )

    question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.PROTECT,
        related_name="assessment_mappings",
    )

    serial_number = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        db_table = "assessment_question_mappings"

        ordering = [
            "serial_number",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "assessment",
                    "question",
                ],
                condition=models.Q(is_deleted=False),
                name="unique_assessment_question_mapping",
            ),
        ]

        indexes = [
            models.Index(fields=["assessment"]),
            models.Index(fields=["question"]),
        ]

    def __str__(self):
        return f"{self.assessment.title} - Q{self.serial_number}"

class AssessmentQuestionImport(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        VALIDATED = "VALIDATED", "Validated"
        IMPORTED = "IMPORTED", "Imported"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    grade = models.ForeignKey(
        "vocabbee.Grades",
        on_delete=models.PROTECT,
        related_name="assessment_question_imports",
    )

    subject = models.ForeignKey(
        "curriculum.CurriculumSubject",
        on_delete=models.PROTECT,
        related_name="assessment_question_imports",
    )

    lesson = models.ForeignKey(
        "curriculum.CurriculumLesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_question_imports",
    )

    file_name = models.CharField(
        max_length=255,
    )

    file_url = models.CharField(
        max_length=500,
    )

    total_rows = models.PositiveIntegerField(
        default=0,
    )

    valid_rows = models.PositiveIntegerField(
        default=0,
    )

    error_rows = models.PositiveIntegerField(
        default=0,
    )

    imported_rows = models.PositiveIntegerField(
        default=0,
    )

    # [{"row": 4, "field": "correct", "message": "Must be A, B, C or D"}]
    errors = models.JSONField(
        default=list,
        blank=True,
    )

    # Parsed valid rows kept between Validate and Import steps
    parsed_rows = models.JSONField(
        default=list,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
    )

    imported_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "assessment_question_imports"

        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(fields=["status"]),
            models.Index(
                fields=[
                    "grade",
                    "subject",
                ]
            ),
        ]

    def __str__(self):
        return self.file_name
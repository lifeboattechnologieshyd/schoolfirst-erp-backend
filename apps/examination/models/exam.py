import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear, Grade, Student, Subject
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


class ExaminationSchedule(AuditModel):
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
        related_name="schedules",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="examination_schedules",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="examination_schedules",
    )

    exam_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    room_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    maximum_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
    )

    passing_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
    )

    instructions = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "examination_schedules"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "examination",
                    "grade",
                    "subject",
                ],
                name="unique_exam_schedule_subject",
            ),
        ]

        indexes = [
            models.Index(fields=["examination"]),
            models.Index(fields=["grade"]),
            models.Index(fields=["subject"]),
            models.Index(fields=["exam_date"]),
            models.Index(
                fields=[
                    "examination",
                    "grade",
                ]
            ),
        ]

    def __str__(self):
        return f"{self.examination.name} - {self.grade.name} - {self.subject.name}"

class HallTicket(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        GENERATED = "GENERATED", "Generated"
        PUBLISHED = "PUBLISHED", "Published"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    examination = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name="hall_tickets",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="hall_tickets",
    )

    hall_ticket_number = models.CharField(
        max_length=100,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.GENERATED,
    )

    generated_at = models.DateTimeField(
        auto_now_add=True,
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "hall_tickets"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "examination",
                    "student",
                ],
                name="unique_hall_ticket_per_exam_student",
            ),
            models.UniqueConstraint(
                fields=[
                    "examination",
                    "hall_ticket_number",
                ],
                name="unique_hall_ticket_number_per_exam",
            ),
        ]

        indexes = [
            models.Index(fields=["examination"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.hall_ticket_number



class ExaminationAttendance(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        EXCUSED = "EXCUSED", "Excused"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    examination = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )

    examination_schedule = models.ForeignKey(
        ExaminationSchedule,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="examination_attendance",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT,
    )

    attendance_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "examination_attendance"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "examination_schedule",
                    "student",
                ],
                name="unique_exam_attendance_per_student",
            ),
        ]

        indexes = [
            models.Index(fields=["examination"]),
            models.Index(fields=["examination_schedule"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.examination_schedule}"



class ExaminationResult(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    examination = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name="results",
    )

    examination_schedule = models.ForeignKey(
        ExaminationSchedule,
        on_delete=models.CASCADE,
        related_name="results",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="examination_results",
    )

    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "examination_results"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "examination_schedule",
                    "student",
                ],
                name="unique_exam_result_per_student",
            ),
        ]

        indexes = [
            models.Index(fields=["examination"]),
            models.Index(fields=["examination_schedule"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.examination_schedule}"



class GradeConfiguration(AuditModel):
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
        related_name="grade_configurations",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grade_configurations",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="grade_configurations",
    )

    grade = models.CharField(
        max_length=10,
    )

    min_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )

    max_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )

    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "grade_configurations"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "academic_year",
                    "grade",
                ],
                name="unique_grade_configuration",
            ),
        ]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["academic_year"]),
        ]

    def __str__(self):
        return self.grade


class ReportCard(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    examination = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name="report_cards",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="report_cards",
    )

    total_marks = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    obtained_marks = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    grade = models.CharField(
        max_length=10,
        null=True,
        blank=True,
    )

    grade_point = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )

    result = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    teacher_remarks = models.TextField(
        null=True,
        blank=True,
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
        db_table = "report_cards"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "examination",
                    "student",
                ],
                name="unique_report_card_per_exam_student",
            ),
        ]

        indexes = [
            models.Index(fields=["examination"]),
            models.Index(fields=["student"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.examination}"



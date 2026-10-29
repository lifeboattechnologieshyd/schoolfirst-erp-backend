import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear, Grade, Section, Subject, Staff
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class TimetableTerm(AuditModel):
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
        related_name="timetable_terms",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="timetable_terms",
        null=True,
        blank=True,
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="timetable_terms",
    )

    name = models.CharField(
        max_length=100
    )

    start_date = models.DateField()

    end_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["start_date"]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["academic_year"]),
            models.Index(fields=["school", "academic_year"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    # "branch",
                    "academic_year",
                    "name",
                ],
                name="unique_timetable_term",
            )
        ]

    def __str__(self):
        return self.name

class TimetablePeriod(AuditModel):
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
        related_name="timetable_periods",
    )

    name = models.CharField(
        max_length=50
    )

    period_number = models.PositiveIntegerField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    is_break = models.BooleanField(
        default=False
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
        ],
        default="ACTIVE",
    )

    class Meta:
        ordering = ["period_number"]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["school", "period_number"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "period_number",
                ],
                name="unique_school_period_number",
            ),
        ]

    def __str__(self):
        return self.name

class Room(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class RoomType(models.TextChoices):
        CLASSROOM = "CLASSROOM", "Classroom"
        LAB = "LAB", "Lab"
        LECTURE_HALL = "LECTURE_HALL", "Lecture Hall"
        ACTIVITY = "ACTIVITY", "Activity"
        OUTDOOR = "OUTDOOR", "Outdoor"
        OTHER = "OTHER", "Other"

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
        related_name="rooms",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="rooms",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=100
    )

    room_type = models.CharField(
        max_length=30,
        choices=RoomType.choices,
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    facilities = models.TextField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    class Meta:
        ordering = ["name"]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["branch"]),
            models.Index(fields=["room_type"]),
            models.Index(fields=["status"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "name",
                ],
                name="unique_school_room_name",
            )
        ]

    def __str__(self):
        return self.name

class Timetable(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
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
        related_name="timetables",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="timetables",
        null=True,
        blank=True,
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="timetables",
    )

    term = models.ForeignKey(
        TimetableTerm,
        on_delete=models.CASCADE,
        related_name="timetables",
    )

    name = models.CharField(
        max_length=150
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["school"]),
            models.Index(fields=["academic_year"]),
            models.Index(fields=["term"]),
            models.Index(fields=["status"]),
            models.Index(
                fields=[
                    "school",
                    "academic_year",
                    "term",
                ]
            ),
        ]

    def __str__(self):
        return self.name

class TimetableEntry(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class DayOfWeek(models.TextChoices):
        MONDAY = "MONDAY", "Monday"
        TUESDAY = "TUESDAY", "Tuesday"
        WEDNESDAY = "WEDNESDAY", "Wednesday"
        THURSDAY = "THURSDAY", "Thursday"
        FRIDAY = "FRIDAY", "Friday"
        SATURDAY = "SATURDAY", "Saturday"
        SUNDAY = "SUNDAY", "Sunday"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    timetable = models.ForeignKey(
        Timetable,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    teacher = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    # room = models.ForeignKey(
    #     Room,
    #     on_delete=models.SET_NULL,
    #     related_name="timetable_entries",
    #     null=True,
    #     blank=True,
    # )

    period = models.ForeignKey(
        TimetablePeriod,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    day_of_week = models.CharField(
        max_length=15,
        choices=DayOfWeek.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    class Meta:
        ordering = [
            "day_of_week",
            "period__period_number",
        ]

        indexes = [
            models.Index(fields=["timetable"]),
            models.Index(fields=["grade"]),
            models.Index(fields=["section"]),
            models.Index(fields=["subject"]),
            models.Index(fields=["teacher"]),
            # models.Index(fields=["room"]),
            models.Index(fields=["period"]),
            models.Index(fields=["day_of_week"]),
            models.Index(
                fields=[
                    "section",
                    "day_of_week",
                    "period",
                ]
            ),
            models.Index(
                fields=[
                    "teacher",
                    "day_of_week",
                    "period",
                ]
            ),
            models.Index(
                fields=[
                    # "room",
                    "day_of_week",
                    "period",
                ]
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "timetable",
                    "section",
                    "day_of_week",
                    "period",
                ],
                name="unique_section_timetable_period",
            ),
        ]

    def __str__(self):
        return (
            f"{self.section} - "
            f"{self.subject} - "
            f"{self.day_of_week}"
        )

class TimetableSubstitution(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    timetable_entry = models.ForeignKey(
        TimetableEntry,
        on_delete=models.CASCADE,
        related_name="substitutions",
    )

    date = models.DateField()

    original_teacher = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="original_timetable_substitutions",
    )

    substitute_teacher = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="substitute_timetable_substitutions",
    )

    reason = models.TextField(
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    class Meta:
        ordering = ["-date"]

        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["timetable_entry"]),
            models.Index(fields=["original_teacher"]),
            models.Index(fields=["substitute_teacher"]),
            models.Index(fields=["status"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "timetable_entry",
                    "date",
                ],
                name="unique_timetable_substitution_date",
            )
        ]
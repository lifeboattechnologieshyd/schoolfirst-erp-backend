import uuid

from django.db import models

from apps.calendar.models import AcademicCalendar
from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear, Grade, Section, Student, Staff
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class CalendarEvent(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class EventType(models.TextChoices):
        PTM = "PTM", "Parent Teacher Meeting"
        FEE = "FEE", "Fee Due"
        EXAM = "EXAM", "Exam"
        HOLIDAY = "HOLIDAY", "Holiday"
        EVENT = "EVENT", "School Event"
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
        HOMEWORK = "HOMEWORK", "Homework"
        ASSIGNMENT = "ASSIGNMENT", "Assignment"
        TRANSPORT = "TRANSPORT", "Transport"
        LIBRARY = "LIBRARY", "Library"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="calendar_events",
    )
    calendar = models.ForeignKey(
        AcademicCalendar,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
    )

    event_date = models.DateField()

    start_time = models.TimeField(
        null=True,
        blank=True,
    )

    end_time = models.TimeField(
        null=True,
        blank=True,
    )

    is_all_day = models.BooleanField(
        default=False,
    )

    color = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    icon = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Stores the UUID of the original record
    # Example:
    # PTM.id
    # StudentFee.id
    # Exam.id
    reference_id = models.UUIDField(
        null=True,
        blank=True,
    )

    class Meta:

        db_table = "calendar_events"

        ordering = [
            "event_date",
            "start_time",
        ]

        indexes = [
            models.Index(
                fields=[
                    "school",
                    "event_date",
                ],
                name="calendar_event_school_date_idx",
            ),
            models.Index(
                fields=[
                    "calendar",
                    "event_date",
                ],
                name="calendar_event_date_idx",
            ),
            models.Index(
                fields=[
                    "calendar",
                    "event_type",
                    "event_date",
                ],
                name="calendar_event_type_date_idx",
            ),
            models.Index(
                fields=[
                    "event_type",
                ],
                name="calendar_event_type_idx",
            ),
            models.Index(
                fields=[
                    "status",
                ],
                name="calendar_event_status_idx",
            ),
        ]

    def __str__(self):
        return self.title


class CalendarEventTarget(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class TargetType(models.TextChoices):

        SCHOOL = "SCHOOL", "School"

        BRANCH = "BRANCH", "Branch"

        GRADE = "GRADE", "Grade"

        SECTION = "SECTION", "Section"

        STUDENT = "STUDENT", "Student"

        STAFF = "STAFF", "Staff"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    event = models.ForeignKey(
        CalendarEvent,
        on_delete=models.CASCADE,
        related_name="targets",
    )

    target_type = models.CharField(
        max_length=20,
        choices=TargetType.choices,
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_targets",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_targets",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_targets",
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_targets",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_targets",
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_targets",
    )

    class Meta:

        db_table = "calendar_event_targets"

        indexes = [

            models.Index(
                fields=[
                    "target_type",
                ]
            ),

            models.Index(
                fields=[
                    "branch",
                ]
            ),

            models.Index(
                fields=[
                    "grade",
                ]
            ),

            models.Index(
                fields=[
                    "section",
                ]
            ),

            models.Index(
                fields=[
                    "student",
                ]
            ),

            models.Index(
                fields=[
                    "staff",
                ]
            ),

        ]

    def __str__(self):
        return f"{self.event.title} - {self.target_type}"



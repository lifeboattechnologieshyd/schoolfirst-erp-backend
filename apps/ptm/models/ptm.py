import uuid

from django.db import models

from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class ParentTeacherMeeting(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class MeetingMode(models.TextChoices):
        OFFLINE = "OFFLINE", "Offline"
        ONLINE = "ONLINE", "Online"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class MeetingType(models.TextChoices):

        GENERAL = "GENERAL", "General"
        ACADEMIC = "ACADEMIC", "Academic"
        RESULT_DISCUSSION = "RESULT_DISCUSSION", "Result Discussion"
        PROGRESS_REVIEW = "PROGRESS_REVIEW", "Progress Review"
        BEHAVIORAL = "BEHAVIORAL", "Behavioral"
        ORIENTATION = "ORIENTATION", "Orientation"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)

    school = models.ForeignKey(
        "school.School",
        on_delete=models.CASCADE,
        related_name="parent_teacher_meetings",
    )

    branch = models.ForeignKey(
        "school.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_teacher_meetings",
    )

    academic_year = models.ForeignKey(
        "school.AcademicYear",
        on_delete=models.CASCADE,
        related_name="parent_teacher_meetings",
    )

    grade = models.ForeignKey(
        "school.Grade",
        on_delete=models.CASCADE,
        related_name="parent_teacher_meetings",
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    meeting_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    meeting_mode = models.CharField(
        max_length=20,
        choices=MeetingMode.choices,
        default=MeetingMode.OFFLINE,
    )
    meeting_type = models.CharField(
    max_length=30,
    choices=MeetingType.choices,
    default=MeetingType.GENERAL,
    )

    location = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    meeting_link = models.URLField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )



    class Meta:
        db_table = "parent_teacher_meetings"

        indexes = [
            models.Index(
                fields=["school", "meeting_date"],
                name="ptm_school_date_idx",
            ),
            models.Index(
                fields=["school", "branch", "status"],
                name="ptm_branch_status_idx",
            ),
            models.Index(
                fields=["grade", "meeting_date"],
                name="ptm_grade_date_idx",
            ),
        ]

        ordering = [
            "-meeting_date",
            "-start_time",
        ]


class ParentTeacherMeetingSection(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    meeting = models.ForeignKey(
        ParentTeacherMeeting,
        on_delete=models.CASCADE,
        related_name="meeting_sections",
    )

    section = models.ForeignKey(
        "school.Section",
        on_delete=models.CASCADE,
        related_name="parent_teacher_meetings",
    )

    class Meta:
        db_table = "parent_teacher_meeting_sections"

        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "section"],
                name="unique_section_per_ptm",
            ),
        ]


class ParentTeacherMeetingResponse(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class ResponseStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ATTENDING = "ATTENDING", "Attending"
        NOT_ATTENDING = "NOT_ATTENDING", "Not Attending"

    class AttendanceStatus(models.TextChoices):
        NOT_MARKED = "NOT_MARKED", "Not Marked"
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    meeting = models.ForeignKey(
        ParentTeacherMeeting,
        on_delete=models.CASCADE,
        related_name="parent_responses",
    )

    student = models.ForeignKey(
        "school.Student",
        on_delete=models.CASCADE,
        related_name="parent_teacher_meeting_responses",
    )

    response_status = models.CharField(
        max_length=20,
        choices=ResponseStatus.choices,
        default=ResponseStatus.PENDING,
    )

    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    attendance_status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.NOT_MARKED,
    )

    attended_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "parent_teacher_meeting_responses"

        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "student"],
                name="unique_student_response_per_ptm",
            ),
        ]
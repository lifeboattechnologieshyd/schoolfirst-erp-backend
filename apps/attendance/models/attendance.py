
import uuid

from django.db import models
from django.utils import timezone

from apps.core.models import UserMaster
from apps.school.models import School
from apps.school.models.school import Branch, Student, Grade, Section, Staff
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class StudentAttendance(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class AttendanceStatus(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        HALF_DAY = "HALF_DAY", "Half Day"
        LEAVE = "LEAVE", "Leave"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="student_attendances",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_attendances",
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendances",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name="student_attendances",
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        related_name="student_attendances",
    )

    attendance_date = models.DateField(
        default=timezone.localdate,
    )

    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )



    remarks = models.TextField(
        null=True,
        blank=True,
    )

    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_student_attendances",
    )

    class Meta:
        db_table = "student_attendance"

        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "attendance_date"],
                name="unique_student_attendance_per_day",
            )
        ]

        indexes = [
            models.Index(
                fields=["school", "attendance_date"],
            ),
            models.Index(
                fields=["school", "section", "attendance_date"],
            ),
            models.Index(
                fields=["school", "status", "attendance_date"],
            ),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.attendance_date} - {self.status}"




class StaffAttendance(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class AttendanceStatus(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        HALF_DAY = "HALF_DAY", "Half Day"
        LEAVE = "LEAVE", "Leave"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="staff_attendances",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_attendances",
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="attendances",
    )

    attendance_date = models.DateField(
        default=timezone.localdate,
    )

    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )

    check_in = models.TimeField(
        null=True,
        blank=True,
    )

    check_out = models.TimeField(
        null=True,
        blank=True,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_staff_attendances",
    )

    class Meta:
        db_table = "staff_attendance"

        constraints = [
            models.UniqueConstraint(
                fields=["school", "staff", "attendance_date"],
                name="unique_staff_attendance_per_day",
            )
        ]

        indexes = [
            models.Index(
                fields=["school", "attendance_date"],
            ),
            models.Index(
                fields=["school", "status", "attendance_date"],
            ),
        ]

    def __str__(self):
        return f"{self.staff.name} - {self.attendance_date} - {self.status}"





class Leave(AuditModel):

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    # class LeaveDuration(models.TextChoices):
    #     FULL_DAY = "FULL_DAY", "Full Day"
    #     HALF_DAY = "HALF_DAY", "Half Day"

    class LeaveType(models.TextChoices):
        SICK = "SICK", "Sick Leave"
        CASUAL = "CASUAL", "Casual Leave"
        EMERGENCY = "EMERGENCY", "Emergency Leave"
        PERSONAL = "PERSONAL", "Personal Leave"
        OTHER = "OTHER", "Other"

    class LeaveStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    class ApplicantType(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        STAFF = "STAFF", "Staff"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="leaves",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leaves",
    )

    applicant_type = models.CharField(
        max_length=20,
        choices=ApplicantType.choices,
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="leave_applications",
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="leave_applications",
    )

    leave_type = models.CharField(
        max_length=20,
        choices=LeaveType.choices,
        default=LeaveType.CASUAL,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    reason = models.TextField()

    note = models.TextField(blank=True, null=True)

    pdf = models.CharField(max_length=500, blank=True, null=True)


    status = models.CharField(
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING,
    )
    # duration = models.CharField(
    #     max_length=20,
    #     choices=LeaveDuration.choices,
    #     default=LeaveDuration.FULL_DAY,
    # )

    total_days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=1.0,
    )

    reviewed_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leaves",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    review_remarks = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "leaves"

        indexes = [
            models.Index(
                fields=["school", "status"],
            ),
            models.Index(
                fields=["school", "start_date", "end_date"],
            ),
            models.Index(
                fields=["student", "status"],
            ),
            models.Index(
                fields=["staff", "status"],
            ),
        ]

    def __str__(self):
        applicant = self.student or self.staff

        return (
            f"{applicant} - "
            f"{self.start_date} to {self.end_date} - "
            f"{self.status}"
        )


class LeaveDay(AuditModel):

    class Duration(models.TextChoices):
        FULL_DAY = "FULL_DAY", "Full Day"
        HALF_DAY = "HALF_DAY", "Half Day"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    leave = models.ForeignKey(
        Leave,
        on_delete=models.CASCADE,
        related_name="leave_days",
    )

    leave_date = models.DateField()

    duration = models.CharField(
        max_length=20,
        choices=Duration.choices,
        default=Duration.FULL_DAY,
    )

    class Meta:
        db_table = "leave_days"

        constraints = [
            models.UniqueConstraint(
                fields=["leave", "leave_date"],
                name="unique_leave_date_per_request",
            )
        ]

        ordering = ["leave_date"]

    def __str__(self):
        return f"{self.leave_id} - {self.leave_date} - {self.duration}"
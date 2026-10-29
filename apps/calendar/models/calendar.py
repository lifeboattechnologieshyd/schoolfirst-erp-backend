import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import Branch, AcademicYear
from apps.timetable.models import TimetableTerm
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class AcademicCalendar(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="academic_calendars",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="academic_calendars",
        null=True,
        blank=True,
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="academic_calendars",
    )

    term = models.ForeignKey(
        TimetableTerm,
        on_delete=models.CASCADE,
        related_name="academic_calendars",
    )

    name = models.CharField(
        max_length=150,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    class Meta:
        db_table = "academic_calendars"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "school",
                    "branch",
                    "term",
                ],
                name="unique_academic_calendar_term",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "school",
                    "academic_year",
                    "status",
                ],
                name="calendar_school_year_idx",
            ),
            models.Index(
                fields=[
                    "branch",
                    "academic_year",
                    "status",
                ],
                name="calendar_branch_year_idx",
            ),
            models.Index(
                fields=[
                    "term",
                    "status",
                ],
                name="calendar_term_status_idx",
            ),
        ]

    def __str__(self):
        return self.name



class AcademicCalendarHoliday(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class HolidayType(models.TextChoices):
        PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY", "Public Holiday"
        SCHOOL_HOLIDAY = "SCHOOL_HOLIDAY", "School Holiday"
        SPECIAL_HOLIDAY = "SPECIAL_HOLIDAY", "Special Holiday"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    calendar = models.ForeignKey(
        AcademicCalendar,
        on_delete=models.CASCADE,
        related_name="holidays",
    )

    date = models.DateField()

    holiday_type = models.CharField(
        max_length=30,
        choices=HolidayType.choices,
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "academic_calendar_holidays"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "calendar",
                    "date",
                ],
                name="unique_calendar_holiday_date",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "calendar",
                    "date",
                ],
                name="calendar_holiday_date_idx",
            ),
            models.Index(
                fields=[
                    "calendar",
                    "holiday_type",
                    "date",
                ],
                name="calendar_holiday_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.date} - {self.title}"



class AcademicCalendarWeekendRule(AuditModel):
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

    class RuleType(models.TextChoices):
        EVERY_WEEK = "EVERY_WEEK", "Every Week"
        SELECTED_WEEKS = "SELECTED_WEEKS", "Selected Weeks"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    calendar = models.ForeignKey(
        AcademicCalendar,
        on_delete=models.CASCADE,
        related_name="weekend_rules",
    )

    day_of_week = models.CharField(
        max_length=15,
        choices=DayOfWeek.choices,
    )

    rule_type = models.CharField(
        max_length=20,
        choices=RuleType.choices,
    )

    week_numbers = models.JSONField(
        default=list,
        blank=True,
    )

    class Meta:
        db_table = "academic_calendar_weekend_rules"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "calendar",
                    "day_of_week",
                ],
                name="unique_calendar_weekday_rule",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "calendar",
                    "day_of_week",
                ],
                name="calendar_weekday_rule_idx",
            ),
        ]

    def __str__(self):
        return f"{self.calendar.name} - {self.day_of_week}"
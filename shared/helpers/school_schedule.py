"""
School working days + working hours, built from data that already exists.
No new model fields.

File: shared/helpers/school_schedule.py

Sources:
    working hours -> TimetablePeriod (earliest start_time, latest end_time, ACTIVE periods)
    working days  -> AcademicCalendarWeekendRule of the school's ACTIVE academic calendar
                     (EVERY_WEEK rule = weekly off; SELECTED_WEEKS = off only on some weeks)

Result shape:
    {
        "start_time": "08:30",            # null if no timetable periods
        "end_time": "15:30",
        "working_days": ["MONDAY", ..., "SATURDAY"],   # null if no active calendar
        "weekly_offs": [
            {"day": "SUNDAY",   "rule_type": "EVERY_WEEK",     "week_numbers": []},
            {"day": "SATURDAY", "rule_type": "SELECTED_WEEKS", "week_numbers": [2, 4]},
        ],
    }
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.db.models import F, Max, Min, Q

from apps.calendar.models.calendar import AcademicCalendar, AcademicCalendarWeekendRule
from apps.timetable.models.timetable import TimetablePeriod


IST = ZoneInfo("Asia/Kolkata")

ALL_DAYS = [
    AcademicCalendarWeekendRule.DayOfWeek.MONDAY,
    AcademicCalendarWeekendRule.DayOfWeek.TUESDAY,
    AcademicCalendarWeekendRule.DayOfWeek.WEDNESDAY,
    AcademicCalendarWeekendRule.DayOfWeek.THURSDAY,
    AcademicCalendarWeekendRule.DayOfWeek.FRIDAY,
    AcademicCalendarWeekendRule.DayOfWeek.SATURDAY,
    AcademicCalendarWeekendRule.DayOfWeek.SUNDAY,
]


def get_school_working_hours(school_id):
    """
    Earliest start and latest end of the school's ACTIVE timetable periods
    (breaks included: a break between periods is still school time).
    """

    hours = TimetablePeriod.objects.filter(
        school_id=school_id,
        status="ACTIVE",
    ).aggregate(
        start_time=Min("start_time"),
        end_time=Max("end_time"),
    )

    return {
        "start_time": hours["start_time"].strftime("%H:%M") if hours["start_time"] else None,
        "end_time": hours["end_time"].strftime("%H:%M") if hours["end_time"] else None,
    }


def get_active_calendar(school_id, branch_id=None, academic_year_id=None):
    """
    The ACTIVE academic calendar for this school (and year), preferring:
      1. a calendar whose term covers today
      2. the student's branch over a school-wide (branch = NULL) calendar
    """

    calendars = AcademicCalendar.objects.filter(
        school_id=school_id,
        status=AcademicCalendar.Status.ACTIVE,
    ).filter(
        Q(branch_id=branch_id) | Q(branch__isnull=True)
    )

    if academic_year_id:
        calendars = calendars.filter(academic_year_id=academic_year_id)

    calendars = calendars.order_by(
        F("branch_id").asc(nulls_last=True),
        "-term__start_date",
    )

    today = datetime.now(IST).date()

    current = calendars.filter(
        term__start_date__lte=today,
        term__end_date__gte=today,
    ).first()

    return current or calendars.first()


def get_school_working_days(school_id, branch_id=None, academic_year_id=None):

    calendar = get_active_calendar(
        school_id,
        branch_id,
        academic_year_id,
    )

    if calendar is None:
        return {
            "working_days": None,
            "weekly_offs": [],
        }

    rules = AcademicCalendarWeekendRule.objects.filter(
        calendar=calendar,
    )

    weekly_offs = []
    every_week_off = set()

    for rule in rules:

        weekly_offs.append(
            {
                "day": rule.day_of_week,
                "rule_type": rule.rule_type,
                "week_numbers": rule.week_numbers or [],
            }
        )

        if rule.rule_type == AcademicCalendarWeekendRule.RuleType.EVERY_WEEK:
            every_week_off.add(rule.day_of_week)

    # A SELECTED_WEEKS day (e.g. 2nd/4th Saturday off) is still a working day
    # in the other weeks, so it stays in working_days; weekly_offs explains it.
    working_days = [
        str(day) for day in ALL_DAYS if day not in every_week_off
    ]

    weekly_offs.sort(key=lambda item: ALL_DAYS.index(item["day"]))

    return {
        "working_days": working_days,
        "weekly_offs": weekly_offs,
    }


def get_school_schedule(school_id, branch_id=None, academic_year_id=None):

    return {
        **get_school_working_hours(school_id),
        **get_school_working_days(school_id, branch_id, academic_year_id),
    }

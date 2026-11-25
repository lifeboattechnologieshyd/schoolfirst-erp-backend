from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.attendance.models import Leave, StudentAttendance
from apps.bulletin.models import Bulletin
from apps.calendar.models import CalendarEvent
from apps.core.models import UserRoles
from apps.fee.models import StudentFee, StudentFeePayment
from apps.ptm.models import ParentTeacherMeeting
from apps.school.models.school import AcademicYear, Staff, Student
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


# =====================================================================
#  CONSTANTS
# =====================================================================

# settings.TIME_ZONE is UTC; "today", "this week" and "this month" are school-local.
SCHOOL_TIME_ZONE = ZoneInfo("Asia/Kolkata")

TREND_MONTHS = 6
UPCOMING_EVENTS_LIMIT = 5
SCHOOL_UPDATES_LIMIT = 5
BIRTHDAY_WINDOW_DAYS = 7

PRESENT_STATUSES = [
    StudentAttendance.AttendanceStatus.PRESENT,
    StudentAttendance.AttendanceStatus.LATE,
    StudentAttendance.AttendanceStatus.HALF_DAY,
]

UNPAID_FEE_STATUSES = [
    StudentFee.Status.PENDING,
    StudentFee.Status.PARTIAL,
    StudentFee.Status.OVERDUE,
]

ZERO = Decimal("0")
MONEY = DecimalField(max_digits=14, decimal_places=2)


# =====================================================================
#  DATE HELPERS
# =====================================================================
def get_school_now():
    return timezone.now().astimezone(SCHOOL_TIME_ZONE)


def get_greeting(now):
    if now.hour < 12:
        return "Good morning"

    if now.hour < 17:
        return "Good afternoon"

    return "Good evening"


def month_start(day, months_back=0):
    year = day.year
    month = day.month - months_back

    while month <= 0:
        month += 12
        year -= 1

    return date(year, month, 1)


def next_month_start(first_day):
    if first_day.month == 12:
        return date(first_day.year + 1, 1, 1)

    return date(first_day.year, first_day.month + 1, 1)


def local_start(day):
    """
    Aware datetime for 00:00 school time, for DateTimeField filters.
    """
    return datetime.combine(day, time.min, tzinfo=SCHOOL_TIME_ZONE)


def percent_change(current, previous):
    if not previous:
        return None

    return round(float((Decimal(current) - Decimal(previous)) * 100 / Decimal(previous)), 1)


def to_float(value):
    return float(value or 0)


def get_current_academic_year(school, today):
    academic_years = AcademicYear.objects.filter(
        school=school,
        status=AcademicYear.Status.ACTIVE,
    )

    return (
        academic_years.filter(
            start_date__lte=today,
            end_date__gte=today,
        ).order_by("-start_date").first()
        or academic_years.order_by("-start_date").first()
    )


def next_birthday(date_of_birth, today):
    """
    Next birthday on or after today (29 Feb -> 28 Feb in non-leap years).
    """
    for year in (today.year, today.year + 1):
        try:
            birthday = date_of_birth.replace(year=year)
        except ValueError:
            birthday = date(year, 2, 28)

        if birthday >= today:
            return birthday

    return None


# =====================================================================
#  SECTION BUILDERS
# =====================================================================
def build_count_card(queryset, today, months):
    """
    Cumulative count card (students / teaching staff) using created_at.
    """
    current = queryset.count()

    month_starts = [month_start(today, back) for back in range(months - 1, -1, -1)]

    trend = []

    for first_day in month_starts:
        end = local_start(next_month_start(first_day))
        trend.append(queryset.filter(created_at__lt=end).count())

    last_month_total = queryset.filter(
        created_at__lt=local_start(month_start(today)),
    ).count()

    return {
        "value": current,
        "change_percentage": percent_change(current, last_month_total),
        "trend": trend,
    }


def build_attendance_card(school, today, months):
    first_month = month_start(today, months - 1)

    rows = {
        row["month"]: row
        for row in StudentAttendance.objects.filter(
            school=school,
            attendance_date__gte=first_month,
            attendance_date__lte=today,
        ).annotate(
            month=TruncMonth("attendance_date"),
        ).values(
            "month",
        ).annotate(
            marked=Count("id"),
            present=Count("id", filter=Q(status__in=PRESENT_STATUSES)),
        )
    }

    trend = []

    for back in range(months - 1, -1, -1):
        first_day = month_start(today, back)
        row = rows.get(first_day)

        trend.append(
            round(row["present"] * 100 / row["marked"], 1)
            if row and row["marked"]
            else None
        )

    current = trend[-1]
    previous = trend[-2] if len(trend) > 1 else None

    return {
        "value": current,
        "change_points": (
            round(current - previous, 1)
            if current is not None and previous is not None
            else None
        ),
        "trend": trend,
    }


def build_fee_card(school, academic_year, today, months):
    payments = StudentFeePayment.objects.filter(
        school=school,
        is_cancelled=False,
    )

    if academic_year:
        payments = payments.filter(student_fee__student__academic_year=academic_year)

    collected = payments.aggregate(
        total=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY),
    )["total"]

    first_month = month_start(today, months - 1)

    monthly = {
        row["month"].date() if isinstance(row["month"], datetime) else row["month"]: row["total"]
        for row in payments.filter(
            payment_date__gte=local_start(first_month),
        ).annotate(
            month=TruncMonth("payment_date", tzinfo=SCHOOL_TIME_ZONE),
        ).values(
            "month",
        ).annotate(
            total=Sum("amount"),
        )
    }

    trend = [
        to_float(monthly.get(month_start(today, back)))
        for back in range(months - 1, -1, -1)
    ]

    return {
        "value": to_float(collected),
        "this_month": trend[-1],
        "change_percentage": percent_change(trend[-1], trend[-2]) if len(trend) > 1 else None,
        "trend": trend,
    }


def build_weekly_attendance(school, today):
    """
    Mon..today of the current week, compared with the same days last week.
    """
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)

    rows = {
        row["attendance_date"]: row
        for row in StudentAttendance.objects.filter(
            school=school,
            attendance_date__gte=last_week_start,
            attendance_date__lte=today,
        ).values(
            "attendance_date",
        ).annotate(
            marked=Count("id"),
            present=Count("id", filter=Q(status__in=PRESENT_STATUSES)),
        )
    }

    def summarize(start, end):
        marked = present = 0
        days = []

        current = start

        while current <= end:
            row = rows.get(current)

            if row and row["marked"]:
                marked += row["marked"]
                present += row["present"]
                days.append({
                    "date": current,
                    "day": current.strftime("%a"),
                    "percentage": round(row["present"] * 100 / row["marked"], 1),
                    "present": row["present"],
                    "marked": row["marked"],
                })

            current += timedelta(days=1)

        average = round(present * 100 / marked, 1) if marked else None

        return days, average

    days, average = summarize(week_start, today)
    _, last_week_average = summarize(last_week_start, last_week_start + (today - week_start))

    best_day = max(days, key=lambda item: item["percentage"]) if days else None

    return {
        "week_start": week_start,
        "days": days,
        "average": average,
        "change_points": (
            round(average - last_week_average, 1)
            if average is not None and last_week_average is not None
            else None
        ),
        "best_day": best_day,
    }


def build_fee_overview(school, academic_year, today):
    fees = StudentFee.objects.filter(
        school=school,
    ).exclude(
        status=StudentFee.Status.WAIVED,
    )

    if academic_year:
        fees = fees.filter(student__academic_year=academic_year)

    totals = fees.aggregate(
        total=Coalesce(
            Sum(F("total_amount") - F("concession_amount") + F("late_fee")),
            Value(ZERO),
            output_field=MONEY,
        ),
        collected=Coalesce(Sum("paid_amount"), Value(ZERO), output_field=MONEY),
    )

    total = totals["total"]
    collected = totals["collected"]
    pending = max(total - collected, ZERO)

    overdue = fees.filter(
        status__in=UNPAID_FEE_STATUSES,
        due_date__lt=today,
    )

    return {
        "academic_year": {
            "id": str(academic_year.id),
            "name": academic_year.name,
        } if academic_year else None,
        "total": to_float(total),
        "collected": to_float(collected),
        "pending": to_float(pending),
        "collected_percentage": round(float(collected * 100 / total), 1) if total else 0,
        "pending_percentage": round(float(pending * 100 / total), 1) if total else 0,
        "overdue_fees_count": overdue.count(),
        "overdue_students_count": overdue.values("student_id").distinct().count(),
    }


def build_birthdays(school, today):
    window_end = today + timedelta(days=BIRTHDAY_WINDOW_DAYS - 1)

    people = []

    students = Student.objects.filter(
        school=school,
        status=Student.Status.ACTIVE,
        date_of_birth__isnull=False,
    ).select_related(
        "grade",
        "section",
    ).only(
        "id",
        "name",
        "date_of_birth",
        "photo_url",
        "grade__name",
        "section__name",
    )

    for student in students:
        birthday = next_birthday(student.date_of_birth, today)

        if birthday and birthday <= window_end:
            people.append({
                "type": "STUDENT",
                "id": str(student.id),
                "name": student.name,
                "image": student.photo_url,
                "subtitle": " ".join(
                    part for part in [
                        student.grade.name if student.grade_id else None,
                        student.section.name if student.section_id else None,
                    ] if part
                ),
                "birthday": birthday,
                "turns": birthday.year - student.date_of_birth.year,
                "is_today": birthday == today,
            })

    staff_members = Staff.objects.filter(
        school=school,
        status=Staff.Status.ACTIVE,
        date_of_birth__isnull=False,
    ).only(
        "id",
        "name",
        "date_of_birth",
        "profile_image",
        "staff_type",
        "department",
    )

    for staff in staff_members:
        birthday = next_birthday(staff.date_of_birth, today)

        if birthday and birthday <= window_end:
            people.append({
                "type": "STAFF",
                "id": str(staff.id),
                "name": staff.name,
                "image": staff.profile_image,
                "subtitle": staff.department or staff.get_staff_type_display(),
                "birthday": birthday,
                "turns": None,
                "is_today": birthday == today,
            })

    people.sort(key=lambda item: (item["birthday"], item["name"]))

    today_list = [item for item in people if item["is_today"]]

    return {
        "total": len(people),
        "today_count": len(today_list),
        "this_week_count": len(people) - len(today_list),
        "today": today_list,
        "this_week": [item for item in people if not item["is_today"]],
    }


def build_upcoming_events(school, today):
    events = CalendarEvent.objects.filter(
        school=school,
        status=CalendarEvent.Status.ACTIVE,
        event_date__gte=today,
    ).order_by(
        "event_date",
        "start_time",
    )[:UPCOMING_EVENTS_LIMIT]

    return [
        {
            "id": str(event.id),
            "title": event.title,
            "event_type": event.event_type,
            "event_date": event.event_date,
            "start_time": event.start_time.strftime("%H:%M") if event.start_time else None,
            "end_time": event.end_time.strftime("%H:%M") if event.end_time else None,
            "is_all_day": event.is_all_day,
            "days_until": (event.event_date - today).days,
            "color": event.color,
            "icon": event.icon,
        }
        for event in events
    ]


def build_school_updates(school):
    bulletins = Bulletin.objects.filter(
        school=school,
        status=Bulletin.Status.PUBLISHED,
        is_active=True,
    ).order_by(
        "-is_pinned",
        "-created_at",
    )[:SCHOOL_UPDATES_LIMIT]

    return [
        {
            "id": str(bulletin.id),
            "title": bulletin.title,
            "summary": bulletin.summary,
            "priority": bulletin.priority,
            "is_pinned": bulletin.is_pinned,
            "created_at": bulletin.created_at,
        }
        for bulletin in bulletins
    ]


def build_action_items(school, today, fee_overview):
    """
    "A little focus goes a long way" - pending work derived from live data.
    """
    items = []

    pending_leaves = Leave.objects.filter(
        school=school,
        status=Leave.LeaveStatus.PENDING,
    )

    pending_leave_count = pending_leaves.count()

    if pending_leave_count:
        overdue_leaves = pending_leaves.filter(start_date__lte=today).count()

        items.append({
            "type": "LEAVE_APPROVALS",
            "title": "Approve leave requests",
            "count": pending_leave_count,
            "priority": "HIGH",
            "due": "OVERDUE" if overdue_leaves else "TODAY",
        })

    if fee_overview["overdue_students_count"]:
        items.append({
            "type": "FEE_DEFAULTERS",
            "title": "Review fee defaulters",
            "count": fee_overview["overdue_students_count"],
            "priority": "HIGH",
            "due": "TODAY",
        })

    draft_ptms = ParentTeacherMeeting.objects.filter(
        school=school,
        status=ParentTeacherMeeting.Status.DRAFT,
        meeting_date__gte=today,
    ).order_by("meeting_date")

    next_draft_ptm = draft_ptms.first()

    if next_draft_ptm:
        items.append({
            "type": "PTM_CONFIRMATION",
            "title": "Confirm PTM schedule",
            "count": draft_ptms.count(),
            "priority": "MEDIUM",
            "due": next_draft_ptm.meeting_date,
            "days_until": (next_draft_ptm.meeting_date - today).days,
        })

    return items


def build_insights(school, today, weekly_attendance, fee_overview):
    insights = []

    # Biggest day-over-day attendance drop this week
    days = weekly_attendance["days"]
    biggest_drop = None

    for previous, current in zip(days, days[1:]):
        drop = round(previous["percentage"] - current["percentage"], 1)

        if drop > 0 and (biggest_drop is None or drop > biggest_drop[0]):
            biggest_drop = (drop, current)

    if biggest_drop:
        insights.append({
            "type": "ATTENDANCE_DIP",
            "title": f"Attendance dipped {biggest_drop[0]} pp on {biggest_drop[1]['date'].strftime('%A')}",
            "action": "Review attendance",
        })

    if fee_overview["overdue_fees_count"]:
        insights.append({
            "type": "FEE_REMINDERS",
            "title": f"{fee_overview['overdue_fees_count']} fee reminders are due",
            "action": "Send reminders",
        })

    next_ptm = ParentTeacherMeeting.objects.filter(
        school=school,
        status=ParentTeacherMeeting.Status.SCHEDULED,
        meeting_date__gte=today,
    ).order_by("meeting_date", "start_time").first()

    if next_ptm:
        days_until = (next_ptm.meeting_date - today).days

        insights.append({
            "type": "UPCOMING_PTM",
            "title": (
                "Parent-Teacher Meeting is today"
                if days_until == 0
                else f"Parent-Teacher Meeting is in {days_until} days"
            ),
            "action": "View event details",
            "ptm_id": str(next_ptm.id),
        })

    return insights


# =====================================================================
#  MAIN DASHBOARD
# =====================================================================
class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "dashboard.view"

    def get(self, request):

        school = request.school

        if school is None:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        now = get_school_now()
        today = now.date()

        try:
            academic_year = get_current_academic_year(school, today)

            # --------------------------------------------------
            # KPI CARDS
            # --------------------------------------------------

            students = Student.objects.filter(
                school=school,
                status=Student.Status.ACTIVE,
            )

            if academic_year:
                students = students.filter(academic_year=academic_year)

            teaching_staff = Staff.objects.filter(
                school=school,
                status=Staff.Status.ACTIVE,
                staff_type=Staff.StaffType.TEACHER,
            )

            fee_overview = build_fee_overview(school, academic_year, today)
            weekly_attendance = build_weekly_attendance(school, today)

            # --------------------------------------------------
            # HEADER
            # --------------------------------------------------

            user = request.user

            role_names = list(
                UserRoles.objects.filter(
                    user=user,
                ).values_list("role__role_name", flat=True)
            )

            full_name = " ".join(
                part for part in [user.first_name, user.last_name] if part
            ) or user.username

            data = {
                "greeting": get_greeting(now),
                "date": today,
                "time": now.strftime("%H:%M"),
                "user": {
                    "id": str(user.id),
                    "name": full_name,
                    "roles": role_names,
                },
                "school": {
                    "id": str(school.id),
                    "name": school.name,
                    "code": school.code,
                    "logo": school.logo,
                },
                "academic_year": {
                    "id": str(academic_year.id),
                    "name": academic_year.name,
                    "start_date": academic_year.start_date,
                    "end_date": academic_year.end_date,
                } if academic_year else None,
                "school_updates": build_school_updates(school),
                "stats": {
                    "total_students": build_count_card(students, today, TREND_MONTHS),
                    "teaching_staff": build_count_card(teaching_staff, today, TREND_MONTHS),
                    "attendance": build_attendance_card(school, today, TREND_MONTHS),
                    "fees_collected": build_fee_card(school, academic_year, today, TREND_MONTHS),
                },
                "birthdays": build_birthdays(school, today),
                "weekly_attendance": weekly_attendance,
                "fee_overview": fee_overview,
                "upcoming_events": build_upcoming_events(school, today),
                "action_items": build_action_items(school, today, fee_overview),
                "insights": build_insights(school, today, weekly_attendance, fee_overview),
            }

            application_logger.info(
                "dashboard_fetched",
                school_id=str(school.id),
                requested_by=str(user.id),
            )

            return CustomResponse.successResponse(
                data=data,
                description="Dashboard fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "dashboard_failed",
                school_id=str(school.id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch dashboard.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

from datetime import date

from apps.calendar.models import CalendarEvent, CalendarEventTarget, AcademicCalendarWeekendRule
from apps.school.models.school import Staff, Student, Section, Grade, Branch


def create_calendar_event(
    *,
    school,
    title,
    event_type,
    event_date,
    target_type,
    reference_id=None,
    description="",
    start_time=None,
    end_time=None,
    is_all_day=False,
    academic_year=None,
    branch=None,
    grade=None,
    sections=None,
    students=None,
    staffs=None,
):
    """
    Creates a calendar event and its targets.
    """
    if reference_id is not None:
        existing_event = CalendarEvent.objects.filter(
            event_type=event_type,
            reference_id=reference_id,
        ).first()

        if existing_event:
            return existing_event

    event = CalendarEvent.objects.create(
        school=school,
        title=title,
        description=description,
        event_type=event_type,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        is_all_day=is_all_day,
        reference_id=reference_id,
    )

    targets = []

    if target_type == CalendarEventTarget.TargetType.SCHOOL:

        targets.append(
            CalendarEventTarget(
                event=event,
                target_type=target_type,
                academic_year=academic_year,
            )
        )

    elif target_type == CalendarEventTarget.TargetType.BRANCH:

        targets.append(
            CalendarEventTarget(
                event=event,
                target_type=target_type,
                academic_year=academic_year,
                branch=branch,
            )
        )

    elif target_type == CalendarEventTarget.TargetType.GRADE:

        targets.append(
            CalendarEventTarget(
                event=event,
                target_type=target_type,
                academic_year=academic_year,
                branch=branch,
                grade=grade,
            )
        )

    elif target_type == CalendarEventTarget.TargetType.SECTION:

        for section in sections or []:

            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=academic_year,
                    branch=branch,
                    grade=grade,
                    section=section,
                )
            )

    elif target_type == CalendarEventTarget.TargetType.STUDENT:

        for student in students or []:

            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=student.academic_year,
                    branch=student.branch,
                    grade=student.grade,
                    section=student.section,
                    student=student,
                )
            )

    elif target_type == CalendarEventTarget.TargetType.STAFF:

        for staff in staffs or []:

            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    branch=staff.branch,
                    staff=staff,
                )
            )

    if targets:
        CalendarEventTarget.objects.bulk_create(targets)

    return event




def get_week_number(date_value):
    """
    1-7   -> week 1
    8-14  -> week 2
    15-21 -> week 3
    22-28 -> week 4
    29-31 -> week 5
    """
    return ((date_value.day - 1) // 7) + 1


def weekend_rule_applies(rule, date_value):
    day_name = date_value.strftime("%A").upper()

    if rule.day_of_week != day_name:
        return False

    if rule.rule_type == AcademicCalendarWeekendRule.RuleType.EVERY_WEEK:
        return True

    if rule.rule_type == AcademicCalendarWeekendRule.RuleType.SELECTED_WEEKS:
        return get_week_number(date_value) in (rule.week_numbers or [])

    return False


def is_working_day(calendar, date_value):
    """
    A date is a working day when:

    - It is inside the term date range
    - It does not have an active HOLIDAY event
    - No weekend rule applies
    """

    if not (
        calendar.term.start_date
        <= date_value
        <= calendar.term.end_date
    ):
        return False

    holiday_exists = CalendarEvent.objects.filter(
        calendar=calendar,
        event_date=date_value,
        event_type=CalendarEvent.EventType.HOLIDAY,
        status=CalendarEvent.Status.ACTIVE,
    ).exists()

    if holiday_exists:
        return False

    rules = AcademicCalendarWeekendRule.objects.filter(
        calendar=calendar,
        day_of_week=date_value.strftime("%A").upper(),
    )

    for rule in rules:
        if weekend_rule_applies(rule, date_value):
            return False

    return True







def validate_event_date(
    calendar,
    event_date,
    event_type,
    exclude_event_id=None,
):
    """
    Validate whether an event can be created/updated
    on the given date.

    Rules:

    1. Event date must be inside the academic term.
    2. HOLIDAY can be created on any date inside the term.
    3. Non-holiday events cannot be created on:
       - an active holiday
       - an applicable weekend rule
    """

    # --------------------------------------------------------
    # Validate term date
    # --------------------------------------------------------

    if not (
        calendar.term.start_date
        <= event_date
        <= calendar.term.end_date
    ):
        return "Event date must be within the academic term."

    # --------------------------------------------------------
    # Holiday events are allowed on any date in the term
    # --------------------------------------------------------

    if event_type == CalendarEvent.EventType.HOLIDAY:
        return None

    # --------------------------------------------------------
    # Check active holiday
    # --------------------------------------------------------

    holidays = CalendarEvent.objects.filter(
        calendar=calendar,
        event_date=event_date,
        event_type=CalendarEvent.EventType.HOLIDAY,
        status=CalendarEvent.Status.ACTIVE,
    )

    if exclude_event_id:
        holidays = holidays.exclude(
            id=exclude_event_id,
        )

    if holidays.exists():
        return "Cannot create an event on a holiday."

    # --------------------------------------------------------
    # Check weekend rules
    # --------------------------------------------------------

    rules = AcademicCalendarWeekendRule.objects.filter(
        calendar=calendar,
        day_of_week=event_date.strftime("%A").upper(),
    )

    for rule in rules:
        if weekend_rule_applies(rule, event_date):
            return "Cannot create an event on a weekend."

    return None


def parse_event_date(event_date):
    """
    Convert YYYY-MM-DD string into date object.
    """

    if isinstance(event_date, date):
        return event_date

    try:
        return date.fromisoformat(event_date)
    except (TypeError, ValueError):
        return None


def build_event_targets(
    event,
    target_type,
    school,
    academic_year=None,
    data=None,
):
    """
    Build CalendarEventTarget objects.

    This keeps Create and Update target logic consistent.
    """

    data = data or {}

    targets = []

    # --------------------------------------------------------
    # SCHOOL
    # --------------------------------------------------------

    if target_type == CalendarEventTarget.TargetType.SCHOOL:

        targets.append(
            CalendarEventTarget(
                event=event,
                target_type=target_type,
                academic_year=academic_year,
            )
        )

    # --------------------------------------------------------
    # BRANCH
    # --------------------------------------------------------

    elif target_type == CalendarEventTarget.TargetType.BRANCH:

        branch_ids = data.get("branch_ids", [])

        branches = Branch.objects.filter(
            school=school,
            id__in=branch_ids,
        )

        for branch in branches:
            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=academic_year,
                    branch=branch,
                )
            )

    # --------------------------------------------------------
    # GRADE
    # --------------------------------------------------------

    elif target_type == CalendarEventTarget.TargetType.GRADE:

        grade_ids = data.get("grade_ids", [])

        grades = Grade.objects.filter(
            school=school,
            id__in=grade_ids,
        )

        for grade in grades:
            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=academic_year,
                    grade=grade,
                )
            )

    # --------------------------------------------------------
    # SECTION
    # --------------------------------------------------------

    elif target_type == CalendarEventTarget.TargetType.SECTION:

        section_ids = data.get("section_ids", [])

        sections = Section.objects.select_related(
            "grade",
            "branch",
        ).filter(
            grade__school=school,
            id__in=section_ids,
        )

        for section in sections:
            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=academic_year,
                    branch=section.branch,
                    grade=section.grade,
                    section=section,
                )
            )

    # --------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------

    elif target_type == CalendarEventTarget.TargetType.STUDENT:

        student_ids = data.get("student_ids", [])

        students = Student.objects.select_related(
            "academic_year",
            "branch",
            "grade",
            "section",
        ).filter(
            school=school,
            id__in=student_ids,
        )

        for student in students:
            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    academic_year=student.academic_year,
                    branch=student.branch,
                    grade=student.grade,
                    section=student.section,
                    student=student,
                )
            )

    # --------------------------------------------------------
    # STAFF
    # --------------------------------------------------------

    elif target_type == CalendarEventTarget.TargetType.STAFF:

        staff_ids = data.get("staff_ids", [])

        staffs = Staff.objects.select_related(
            "branch",
        ).filter(
            school=school,
            id__in=staff_ids,
        )

        for staff in staffs:
            targets.append(
                CalendarEventTarget(
                    event=event,
                    target_type=target_type,
                    branch=staff.branch,
                    staff=staff,
                )
            )

    return targets


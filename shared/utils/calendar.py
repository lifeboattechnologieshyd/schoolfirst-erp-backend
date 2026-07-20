from apps.calendar.models import CalendarEvent, CalendarEventTarget


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
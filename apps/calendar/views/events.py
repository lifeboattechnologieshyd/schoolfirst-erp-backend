from django.db.models import Prefetch, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import CalendarEventTarget, CalendarEvent, AcademicCalendar
from apps.school.models.school import Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class AcademicCalendarListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "calendar.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "academic_calendar_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
        )

        # ----------------------------------------------------
        # Get calendars
        # ----------------------------------------------------

        calendars = (
            AcademicCalendar.objects
            .select_related(
                "school",
                "branch",
                "academic_year",
                "term",
            )
            .prefetch_related(
                "weekend_rules",
            )
            .filter(
                school=school,
            )
            .order_by(
                "-academic_year",
                "term__start_date",
            )
        )

        # ----------------------------------------------------
        # Pagination
        # ----------------------------------------------------

        paginator = CustomPageNumberPagination()

        calendars = paginator.paginate_queryset(
            calendars,
            request,
        )

        # ----------------------------------------------------
        # Response data
        # ----------------------------------------------------

        data = []

        for calendar in calendars:

            weekend_rules = []

            for rule in calendar.weekend_rules.all():

                weekend_rules.append({
                    "id": str(rule.id),
                    "day_of_week": rule.day_of_week,
                    "rule_type": rule.rule_type,
                    "week_numbers": rule.week_numbers or [],
                })

            data.append({
                "id": str(calendar.id),
                "name": calendar.name,
                "status": calendar.status,

                "school": {
                    "id": str(calendar.school.id),
                    "name": calendar.school.name,
                } if calendar.school else None,

                "branch": {
                    "id": str(calendar.branch.id),
                    "name": calendar.branch.name,
                } if calendar.branch else None,

                "academic_year": {
                    "id": str(calendar.academic_year.id),
                    "name": calendar.academic_year.name,
                } if calendar.academic_year else None,

                "term": {
                    "id": str(calendar.term.id),
                    "name": calendar.term.name,
                    "start_date": calendar.term.start_date,
                    "end_date": calendar.term.end_date,
                } if calendar.term else None,

                "weekend_rules": weekend_rules,
            })

        application_logger.info(
            "academic_calendar_list_fetched",
            user_id=str(request.user.id),
            school_id=str(school.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Academic calendars fetched successfully.",
            data=data,
        )

class CalendarEventListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "calendar.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "student_calendar_event_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
        )

        # ----------------------------------------------------
        # Student
        # ----------------------------------------------------

        student_id = request.query_params.get(
            "student_id"
        )

        if not student_id:
            return CustomResponse.errorResponse(
                description="student_id is required.",
            )

        student = (
            Student.objects
            .select_related(
                "academic_year",
                "branch",
                "grade",
                "section",
            )
            .filter(
                id=student_id,
                school=school,
            )
            .first()
        )

        if not student:
            return CustomResponse.errorResponse(
                description="Student not found.",
            )

        # ----------------------------------------------------
        # Query parameters
        # ----------------------------------------------------

        calendar_id = request.query_params.get(
            "calendar_id"
        )

        event_type = request.query_params.get(
            "event_type"
        )

        status = request.query_params.get(
            "status"
        )

        event_date = request.query_params.get(
            "event_date"
        )

        from_date = request.query_params.get(
            "from_date"
        )

        to_date = request.query_params.get(
            "to_date"
        )

        search = request.query_params.get(
            "search"
        )

        # ----------------------------------------------------
        # Base events
        # ----------------------------------------------------

        events = CalendarEvent.objects.filter(
            school=school,
        )

        # ----------------------------------------------------
        # Calendar
        # ----------------------------------------------------

        if calendar_id:

            calendar = AcademicCalendar.objects.filter(
                id=calendar_id,
                school=school,
            ).first()

            if not calendar:
                return CustomResponse.errorResponse(
                    description="Calendar not found.",
                )

            events = events.filter(
                calendar=calendar,
            )

        # ----------------------------------------------------
        # Student applicable targets
        # ----------------------------------------------------

        events = events.filter(
            Q(
                targets__target_type=CalendarEventTarget.TargetType.SCHOOL,
            )
            |
            Q(
                targets__target_type=CalendarEventTarget.TargetType.BRANCH,
                targets__branch=student.branch,
            )
            |
            Q(
                targets__target_type=CalendarEventTarget.TargetType.GRADE,
                targets__grade=student.grade,
            )
            |
            Q(
                targets__target_type=CalendarEventTarget.TargetType.SECTION,
                targets__section=student.section,
            )
            |
            Q(
                targets__target_type=CalendarEventTarget.TargetType.STUDENT,
                targets__student=student,
            )
        )

        # ----------------------------------------------------
        # Academic year
        # ----------------------------------------------------

        events = events.filter(
            Q(
                targets__academic_year__isnull=True,
            )
            |
            Q(
                targets__academic_year=student.academic_year,
            )
        )

        # ----------------------------------------------------
        # Filters
        # ----------------------------------------------------

        if event_type:
            events = events.filter(
                event_type=event_type,
            )

        if status:
            events = events.filter(
                status=status,
            )

        if event_date:
            events = events.filter(
                event_date=event_date,
            )

        if from_date:
            events = events.filter(
                event_date__gte=from_date,
            )

        if to_date:
            events = events.filter(
                event_date__lte=to_date,
            )

        if search:
            events = events.filter(
                Q(title__icontains=search)
                |
                Q(description__icontains=search)
            )

        # ----------------------------------------------------
        # Query optimization
        # ----------------------------------------------------

        events = (
            events
            .distinct()
            .prefetch_related(
                Prefetch(
                    "targets",
                    queryset=CalendarEventTarget.objects.select_related(
                        "academic_year",
                        "branch",
                        "grade",
                        "section",
                        "student",
                        "staff",
                    ),
                ),
            )
            .order_by(
                "event_date",
                "start_time",
            )
        )

        # ----------------------------------------------------
        # Pagination
        # ----------------------------------------------------

        paginator = CustomPageNumberPagination()

        events = paginator.paginate_queryset(
            events,
            request,
        )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        data = []

        for event in events:

            data.append({
                "id": str(event.id),
                "title": event.title,
                "description": event.description,
                "event_type": event.event_type,
                "event_date": event.event_date,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "is_all_day": event.is_all_day,
                "status": event.status,
                "color": event.color,
                "reference_id": (
                    str(event.reference_id)
                    if event.reference_id
                    else None
                ),
            })

        application_logger.info(
            "student_calendar_event_list_fetched",
            user_id=str(request.user.id),
            school_id=str(school.id),
            student_id=str(student.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Calendar events fetched successfully.",
            data=data,
        )
from django.db.models import Prefetch, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import CalendarEventTarget, CalendarEvent
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger

class AcademicCalendarDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "calendar.view"

    def get(self, request):

        school = request.school

        application_logger.info(
            "academic_calendar_detail_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
        )

        calendar_id = request.query_params.get(
            "calendar_id"
        )

        if not calendar_id:
            return CustomResponse.errorResponse(
                description="calendar_id is required.",
            )

        # ----------------------------------------------------
        # Get calendar
        # ----------------------------------------------------

        calendar = (
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
                id=calendar_id,
                school=school,
            )
            .first()
        )

        if not calendar:

            application_logger.warning(
                "academic_calendar_detail_failed",
                user_id=str(request.user.id),
                school_id=str(school.id),
                calendar_id=str(calendar_id),
                reason="calendar_not_found",
            )

            return CustomResponse.errorResponse(
                description="Calendar not found.",
            )

        # ----------------------------------------------------
        # Weekend rules
        # ----------------------------------------------------

        weekend_rules = []

        for rule in calendar.weekend_rules.all():

            weekend_rules.append({
                "id": str(rule.id),
                "day_of_week": rule.day_of_week,
                "rule_type": rule.rule_type,
                "week_numbers": rule.week_numbers or [],
            })

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        data = {
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
        }

        application_logger.info(
            "academic_calendar_detail_fetched",
            user_id=str(request.user.id),
            school_id=str(school.id),
            calendar_id=str(calendar.id),
        )

        return CustomResponse.successResponse(
            description="Academic calendar fetched successfully.",
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
            "calendar_event_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
        )

        events = CalendarEvent.objects.filter(
            school=school,
        )

        calendar_id = request.query_params.get(
            "calendar_id"
        )

        event_type = request.query_params.get("event_type")
        status = request.query_params.get("status")
        event_date = request.query_params.get("event_date")
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        target_type = request.query_params.get("target_type")
        academic_year_id = request.query_params.get("academic_year_id")
        branch_id = request.query_params.get("branch_id")
        grade_id = request.query_params.get("grade_id")
        section_id = request.query_params.get("section_id")
        student_id = request.query_params.get("student_id")
        staff_id = request.query_params.get("staff_id")
        search = request.query_params.get("search")

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

        if target_type:
            events = events.filter(
                targets__target_type=target_type,
            )

        if academic_year_id:
            events = events.filter(
                targets__academic_year_id=academic_year_id,
            )

        if branch_id:
            events = events.filter(
                targets__branch_id=branch_id,
            )

        if grade_id:
            events = events.filter(
                targets__grade_id=grade_id,
            )

        if section_id:
            events = events.filter(
                targets__section_id=section_id,
            )

        if student_id:
            events = events.filter(
                targets__student_id=student_id,
            )

        if staff_id:
            events = events.filter(
                targets__staff_id=staff_id,
            )

        if search:
            events = events.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
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
                )
            )
            .order_by(
                "event_date",
                "start_time",
            )
        )

        # ----------------------------------------------------
        # Pagination
        # ----------------------------------------------------

        paginator = CustomPagination()

        events = paginator.paginate_queryset(
            events,
            request,
        )

        # ----------------------------------------------------
        # Response data
        # ----------------------------------------------------

        data = []

        for event in events:

            targets = []

            for target in event.targets.all():

                targets.append({
                    "id": str(target.id),
                    "target_type": target.target_type,

                    "academic_year": {
                        "id": str(target.academic_year.id),
                        "name": target.academic_year.name,
                    } if target.academic_year else None,

                    "branch": {
                        "id": str(target.branch.id),
                        "name": target.branch.name,
                    } if target.branch else None,

                    "grade": {
                        "id": str(target.grade.id),
                        "name": target.grade.name,
                    } if target.grade else None,

                    "section": {
                        "id": str(target.section.id),
                        "name": target.section.name,
                    } if target.section else None,

                    "student": {
                        "id": str(target.student.id),
                        "name": target.student.name,
                    } if target.student else None,

                    "staff": {
                        "id": str(target.staff.id),
                        "name": target.staff.name,
                    } if target.staff else None,
                })

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
                "targets": targets,
            })

        application_logger.info(
            "calendar_event_list_fetched",
            user_id=str(request.user.id),
            school_id=str(school.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            description="Calendar events fetched successfully.",
            data=data,
        )
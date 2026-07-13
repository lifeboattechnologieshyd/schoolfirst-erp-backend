from django.db.models import Prefetch, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import CalendarEventTarget, CalendarEvent
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class CalendarEventListAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

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
                |
                Q(description__icontains=search)
            )

        events = events.distinct().prefetch_related(
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
        ).order_by(
            "event_date",
            "start_time",
        )

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
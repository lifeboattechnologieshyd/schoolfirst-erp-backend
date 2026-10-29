from datetime import datetime
from calendar import Calendar

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import CalendarEventTarget, CalendarEvent, AcademicCalendar, AcademicCalendarWeekendRule
from apps.school.models.school import AcademicYear, Branch, Grade, Section, Student, Staff
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.calendar import weekend_rule_applies, parse_event_date, validate_event_date, build_event_targets
from shared.utils.logger import application_logger, audit_logger


class CreateCalendarEventAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "calendar.create"

    @transaction.atomic
    def post(self, request):

        user = request.user
        school = request.school

        application_logger.info(
            "calendar_event_create_started",
            user_id=str(user.id),
            school_id=str(school.id),
        )

        title = request.data.get("title")
        event_type = request.data.get("event_type")
        event_date = request.data.get("event_date")
        target_type = request.data.get("target_type")
        calendar_id = request.data.get("calendar_id")

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        if not title:
            return CustomResponse.errorResponse(
                description="title is required."
            )

        if not event_type:
            return CustomResponse.errorResponse(
                description="event_type is required."
            )

        if event_type not in CalendarEvent.EventType.values:
            return CustomResponse.errorResponse(
                description="Invalid event type."
            )

        if not event_date:
            return CustomResponse.errorResponse(
                description="event_date is required."
            )

        if not calendar_id:
            return CustomResponse.errorResponse(
                description="calendar_id is required."
            )

        if target_type not in CalendarEventTarget.TargetType.values:
            return CustomResponse.errorResponse(
                description="Invalid target type."
            )

        # ----------------------------------------------------
        # Parse event date
        # ----------------------------------------------------

        event_date = parse_event_date(event_date)

        if event_date is None:
            return CustomResponse.errorResponse(
                description="Invalid event date. Use YYYY-MM-DD format."
            )

        # ----------------------------------------------------
        # Get calendar
        # ----------------------------------------------------

        calendar = (
            AcademicCalendar.objects
            .select_related("term")
            .filter(
                id=calendar_id,
                school=school,
            )
            .first()
        )

        if not calendar:
            return CustomResponse.errorResponse(
                description="Calendar not found."
            )

        # ----------------------------------------------------
        # Validate event date
        # ----------------------------------------------------

        error = validate_event_date(
            calendar=calendar,
            event_date=event_date,
            event_type=event_type,
        )

        if error:
            return CustomResponse.errorResponse(
                description=error
            )

        # ----------------------------------------------------
        # Academic year
        # ----------------------------------------------------

        academic_year = None

        academic_year_id = request.data.get(
            "academic_year_id"
        )

        if academic_year_id:

            academic_year = AcademicYear.objects.filter(
                id=academic_year_id,
                school=school,
            ).first()

            if academic_year is None:
                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

        # ----------------------------------------------------
        # Create event
        # ----------------------------------------------------

        event = CalendarEvent.objects.create(
            school=school,
            calendar=calendar,
            title=title,
            description=request.data.get("description"),
            event_type=event_type,
            event_date=event_date,
            start_time=request.data.get("start_time"),
            end_time=request.data.get("end_time"),
            is_all_day=request.data.get(
                "is_all_day",
                False,
            ),
        )

        # ----------------------------------------------------
        # Create targets
        # ----------------------------------------------------

        targets = build_event_targets(
            event=event,
            target_type=target_type,
            school=school,
            academic_year=academic_year,
            data=request.data,
        )

        CalendarEventTarget.objects.bulk_create(
            targets
        )

        # ----------------------------------------------------
        # Audit log
        # ----------------------------------------------------

        audit_logger.info(
            "calendar_event_created",
            user_id=str(user.id),
            school_id=str(school.id),
            event_id=str(event.id),
            target_type=target_type,
            target_count=len(targets),
        )

        return CustomResponse.successResponse(
            description="Calendar event created successfully.",
            data={
                "id": str(event.id),
            },
        )

class CalendarEventListAPIView(APIView):

    permission_classes = [IsAuthenticated,HasPermission,]

    required_permission = "calendar.view"

    def get(self, request):

        school = request.school
        calendar_id = request.query_params.get(
            "calendar_id"
        )

        if not calendar_id:
            return CustomResponse.errorResponse(
                description="calendar_id is required."
            )

        # ----------------------------------------------------
        # Validate calendar belongs to school
        # ----------------------------------------------------

        calendar = AcademicCalendar.objects.filter(
            id=calendar_id,
            school=school,
        ).first()

        if not calendar:
            return CustomResponse.errorResponse(
                description="Calendar not found."
            )

        application_logger.info(
            "calendar_event_list_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
            calendar_id=str(calendar.id),
        )

        # ----------------------------------------------------
        # Events
        # ----------------------------------------------------

        events = (
            CalendarEvent.objects
            .filter(
                school=school,
                calendar=calendar,
                status=CalendarEvent.Status.ACTIVE,
            )
            .prefetch_related(
                "targets",
                "targets__branch",
                "targets__grade",
                "targets__section",
                "targets__student",
                "targets__staff",
                "targets__academic_year",
            )
            .order_by(
                "event_date",
                "start_time",
            )
        )

        # ----------------------------------------------------
        # Filters
        # ----------------------------------------------------

        event_type = request.query_params.get(
            "event_type"
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

        if event_type:

            events = events.filter(
                event_type=event_type
            )

        if event_date:

            events = events.filter(
                event_date=event_date
            )

        if from_date:

            events = events.filter(
                event_date__gte=from_date
            )

        if to_date:

            events = events.filter(
                event_date__lte=to_date
            )

        # ----------------------------------------------------
        # Custom pagination
        # ----------------------------------------------------

        paginator = CustomPageNumberPagination()

        paginated_events = paginator.paginate_queryset(
            events,
            request,
        )

        data = []

        for event in paginated_events:

            targets = []

            for target in event.targets.all():

                targets.append({
                    "id": str(target.id),

                    "target_type": target.target_type,

                    "academic_year": (
                        {
                            "id": str(target.academic_year.id),
                            "name": target.academic_year.name,
                        }
                        if target.academic_year
                        else None
                    ),

                    "branch": (
                        {
                            "id": str(target.branch.id),
                            "name": target.branch.name,
                        }
                        if target.branch
                        else None
                    ),

                    "grade": (
                        {
                            "id": str(target.grade.id),
                            "name": target.grade.name,
                        }
                        if target.grade
                        else None
                    ),

                    "section": (
                        {
                            "id": str(target.section.id),
                            "name": target.section.name,
                        }
                        if target.section
                        else None
                    ),

                    "student": (
                        {
                            "id": str(target.student.id),
                            "name": target.student.name,
                        }
                        if target.student
                        else None
                    ),

                    "staff": (
                        {
                            "id": str(target.staff.id),
                            "name": target.staff.name,
                        }
                        if target.staff
                        else None
                    ),
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

        audit_logger.info(
            "calendar_event_list_fetched",
            user_id=str(request.user.id),
            school_id=str(school.id),
            calendar_id=str(calendar.id),
            total_count=len(data),
        )



        return CustomResponse.successResponse(
            description="Calendar events fetched successfully.",
            data=data,
        )

class UpdateCalendarEventAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "calendar.update"

    @transaction.atomic
    def put(self, request, event_id):

        school = request.school

        application_logger.info(
            "calendar_event_update_started",
            user_id=str(request.user.id),
            school_id=str(school.id),
            event_id=str(event_id),
        )

        # ----------------------------------------------------
        # Get event + calendar + term
        # ----------------------------------------------------

        event = (
            CalendarEvent.objects
            .select_related(
                "calendar",
                "calendar__term",
            )
            .filter(
                id=event_id,
                school=school,
            )
            .first()
        )

        if event is None:

            application_logger.warning(
                "calendar_event_update_failed",
                user_id=str(request.user.id),
                school_id=str(school.id),
                event_id=str(event_id),
                reason="event_not_found",
            )

            return CustomResponse.errorResponse(
                description="Calendar event not found."
            )

        # ----------------------------------------------------
        # Existing values
        # ----------------------------------------------------

        event_type = request.data.get(
            "event_type",
            event.event_type,
        )

        event_date = request.data.get(
            "event_date",
            event.event_date,
        )

        # ----------------------------------------------------
        # Validate event type
        # ----------------------------------------------------

        if event_type not in CalendarEvent.EventType.values:

            return CustomResponse.errorResponse(
                description="Invalid event type."
            )

        # ----------------------------------------------------
        # Parse event date
        # ----------------------------------------------------

        event_date = parse_event_date(event_date)

        if event_date is None:

            return CustomResponse.errorResponse(
                description="Invalid event date. Use YYYY-MM-DD format."
            )

        # ----------------------------------------------------
        # Validate event date
        #
        # IMPORTANT:
        # Exclude current event so it doesn't block itself
        # when it is already a HOLIDAY.
        # ----------------------------------------------------

        error = validate_event_date(
            calendar=event.calendar,
            event_date=event_date,
            event_type=event_type,
            exclude_event_id=event.id,
        )

        if error:

            return CustomResponse.errorResponse(
                description=error
            )

        # ----------------------------------------------------
        # Update basic fields
        # ----------------------------------------------------

        event.title = request.data.get(
            "title",
            event.title,
        )

        event.description = request.data.get(
            "description",
            event.description,
        )

        event.event_type = event_type

        event.event_date = event_date

        event.start_time = request.data.get(
            "start_time",
            event.start_time,
        )

        event.end_time = request.data.get(
            "end_time",
            event.end_time,
        )

        event.is_all_day = request.data.get(
            "is_all_day",
            event.is_all_day,
        )

        event.status = request.data.get(
            "status",
            event.status,
        )

        event.save()

        # ----------------------------------------------------
        # Update targets only when target_type is supplied
        # ----------------------------------------------------

        target_type = request.data.get(
            "target_type"
        )

        if target_type:

            if (
                target_type
                not in CalendarEventTarget.TargetType.values
            ):
                return CustomResponse.errorResponse(
                    description="Invalid target type."
                )

            # Delete existing targets
            CalendarEventTarget.objects.filter(
                event=event,
            ).delete()

            # ------------------------------------------------
            # Academic year
            # ------------------------------------------------

            academic_year = None

            academic_year_id = request.data.get(
                "academic_year_id"
            )

            if academic_year_id:

                academic_year = AcademicYear.objects.filter(
                    id=academic_year_id,
                    school=school,
                ).first()

                if academic_year is None:

                    return CustomResponse.errorResponse(
                        description="Academic year not found."
                    )

            # ------------------------------------------------
            # Create new targets
            # ------------------------------------------------

            targets = build_event_targets(
                event=event,
                target_type=target_type,
                school=school,
                academic_year=academic_year,
                data=request.data,
            )

            CalendarEventTarget.objects.bulk_create(
                targets
            )

        audit_logger.info(
            "calendar_event_updated",
            user_id=str(request.user.id),
            school_id=str(school.id),
            event_id=str(event.id),
            event_type=event.event_type,
        )

        return CustomResponse.successResponse(
            description="Calendar event updated successfully.",
            data={
                "id": str(event.id),
            },
        )

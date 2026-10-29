import uuid

from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.calendar.models import AcademicCalendar, AcademicCalendarWeekendRule
from apps.timetable.models import TimetableTerm
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class AcademicCalendarLISTAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar.view"

    def get(self, request):
        try:
            school = request.school

            branch_id = request.GET.get("branch_id")
            academic_year_id = request.GET.get("academic_year_id")
            status = request.GET.get("status")

            calendars = (
                AcademicCalendar.objects
                .filter(school=school)
                .select_related(
                    "school",
                    "branch",
                    "academic_year",
                    "term",
                )
                .order_by("-term__start_date")
            )

            if branch_id:
                try:
                    branch_id = uuid.UUID(branch_id)
                except ValueError:
                    return CustomResponse.errorResponse(
                        message="Invalid branch_id."
                    )

                calendars = calendars.filter(
                    branch_id=branch_id
                )

            if academic_year_id:
                try:
                    academic_year_id = uuid.UUID(academic_year_id)
                except ValueError:
                    return CustomResponse.errorResponse(
                        message="Invalid academic_year_id."
                    )

                calendars = calendars.filter(
                    academic_year_id=academic_year_id
                )

            if status:
                calendars = calendars.filter(
                    status=status
                )

            paginator = CustomPageNumberPagination()

            paginated_calendars = paginator.paginate_queryset(
                calendars,
                request,
            )

            data = [
                {
                    "id": str(calendar.id),
                    "school_id": str(calendar.school_id),
                    "branch_id": (
                        str(calendar.branch_id)
                        if calendar.branch_id
                        else None
                    ),
                    "academic_year_id": str(
                        calendar.academic_year_id
                    ),
                    "term_id": str(calendar.term_id),
                    "term_start_date": calendar.term.start_date,
                    "term_end_date": calendar.term.end_date,
                    "name": calendar.name,
                    "status": calendar.status,
                }
                for calendar in paginated_calendars
            ]

            return CustomResponse.successResponse(
                message="Academic calendars fetched successfully.",
                data=data,
            )

        except Exception:
            application_logger.exception(
                "Error while fetching academic calendars."
            )

            return CustomResponse.errorResponse(
                message="Unable to fetch academic calendars."
            )

class AcademicCalendarAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar.view"

    def post(self, request):
        try:
            school = request.school

            term_id = request.data.get("term_id")
            branch_id = request.data.get("branch_id")
            name = request.data.get("name")

            if not term_id or not name:
                return CustomResponse.errorResponse(
                    message="term_id and name are required."
                )

            try:
                term_id = uuid.UUID(str(term_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid term_id."
                )

            term = (
                TimetableTerm.objects
                .select_related("school", "branch", "academic_year")
                .filter(
                    id=term_id,
                    school=school,
                )
                .first()
            )

            if not term:
                return CustomResponse.errorResponse(
                    message="Timetable term not found."
                )

            if branch_id:
                try:
                    branch_id = uuid.UUID(str(branch_id))
                except ValueError:
                    return CustomResponse.errorResponse(
                        message="Invalid branch_id."
                    )

                if term.branch_id and term.branch_id != branch_id:
                    return CustomResponse.errorResponse(
                        message="Branch does not belong to the selected term."
                    )
            else:
                branch_id = term.branch_id

            existing = AcademicCalendar.all_objects.filter(
                school=school,
                branch_id=branch_id,
                term=term,
            ).first()

            if existing:
                return CustomResponse.errorResponse(
                    message="Academic calendar already exists for this term."
                )

            with transaction.atomic():
                calendar = AcademicCalendar.objects.create(
                    school=school,
                    branch_id=branch_id,
                    academic_year=term.academic_year,
                    term=term,
                    name=name,
                    status=AcademicCalendar.Status.DRAFT,
                )

            application_logger.info(
                "Academic calendar created: %s",
                calendar.id,
            )

            return CustomResponse.successResponse(
                message="Academic calendar created successfully.",
                data={
                    "id": str(calendar.id),
                    "name": calendar.name,
                    "status": calendar.status,
                },
            )

        except Exception:
            application_logger.exception(
                "Error while creating academic calendar."
            )
            return CustomResponse.errorResponse(
                message="Unable to create academic calendar."
            )

class AcademicCalendarUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar.update"

    def put(self, request, calendar_id):
        try:
            try:
                calendar_id = uuid.UUID(str(calendar_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid calendar_id."
                )

            calendar = AcademicCalendar.objects.filter(
                id=calendar_id,
                school=request.user.school,
            ).first()

            if not calendar:
                return CustomResponse.errorResponse(
                    message="Academic calendar not found."
                )

            name = request.data.get("name")

            if name is not None:
                calendar.name = name

            calendar.save()

            return CustomResponse.successResponse(
                message="Academic calendar updated successfully.",
                data={
                    "id": str(calendar.id),
                    "name": calendar.name,
                    "status": calendar.status,
                },
            )

        except Exception:
            application_logger.exception(
                "Error while updating academic calendar."
            )
            return CustomResponse.errorResponse(
                message="Unable to update academic calendar."
            )

class AcademicCalendarWeekendRuleCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar_weekend_rule.create"

    def post(self, request):
        try:
            calendar_id = request.data.get("calendar_id")
            day_of_week = request.data.get("day_of_week")
            rule_type = request.data.get("rule_type")
            week_numbers = request.data.get("week_numbers", [])

            if not calendar_id:
                return CustomResponse.errorResponse(
                    message="calendar_id is required."
                )

            if not day_of_week:
                return CustomResponse.errorResponse(
                    message="day_of_week is required."
                )

            if not rule_type:
                return CustomResponse.errorResponse(
                    message="rule_type is required."
                )

            try:
                calendar_id = uuid.UUID(str(calendar_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid calendar_id."
                )

            calendar = AcademicCalendar.objects.filter(
                id=calendar_id,
                school=request.user.school,
            ).first()

            if not calendar:
                return CustomResponse.errorResponse(
                    message="Academic calendar not found."
                )

            valid_days = {
                choice[0]
                for choice in AcademicCalendarWeekendRule.DayOfWeek.choices
            }

            if day_of_week not in valid_days:
                return CustomResponse.errorResponse(
                    message="Invalid day_of_week."
                )

            valid_rule_types = {
                choice[0]
                for choice in AcademicCalendarWeekendRule.RuleType.choices
            }

            if rule_type not in valid_rule_types:
                return CustomResponse.errorResponse(
                    message="Invalid rule_type."
                )

            if rule_type == (
                AcademicCalendarWeekendRule.RuleType.SELECTED_WEEKS
            ):
                if not isinstance(week_numbers, list) or not week_numbers:
                    return CustomResponse.errorResponse(
                        message="week_numbers is required for SELECTED_WEEKS."
                    )

                if any(
                    not isinstance(week, int) or week < 1 or week > 5
                    for week in week_numbers
                ):
                    return CustomResponse.errorResponse(
                        message="week_numbers must contain values from 1 to 5."
                    )

                week_numbers = sorted(set(week_numbers))

            else:
                week_numbers = []

            if AcademicCalendarWeekendRule.objects.filter(
                calendar=calendar,
                day_of_week=day_of_week,
            ).exists():
                return CustomResponse.errorResponse(
                    message="Weekend rule already exists for this day."
                )

            with transaction.atomic():
                rule = AcademicCalendarWeekendRule.objects.create(
                    calendar=calendar,
                    day_of_week=day_of_week,
                    rule_type=rule_type,
                    week_numbers=week_numbers,
                )

            application_logger.info(
                "Academic calendar weekend rule created: %s",
                rule.id,
            )

            return CustomResponse.successResponse(
                message="Weekend rule created successfully.",
                data={
                    "id": str(rule.id),
                    "calendar_id": str(rule.calendar_id),
                    "day_of_week": rule.day_of_week,
                    "rule_type": rule.rule_type,
                    "week_numbers": rule.week_numbers,
                },
            )

        except Exception:
            application_logger.exception(
                "Error while creating academic calendar weekend rule."
            )

            return CustomResponse.errorResponse(
                message="Unable to create weekend rule."
            )

class AcademicCalendarWeekendRuleLISTAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar_weekend_rule.view"

    def get(self, request):
        try:
            calendar_id = request.GET.get("calendar_id")

            if not calendar_id:
                return CustomResponse.errorResponse(
                    message="calendar_id is required."
                )

            try:
                calendar_id = uuid.UUID(str(calendar_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid calendar_id."
                )

            calendar = AcademicCalendar.objects.filter(
                id=calendar_id,
                school=request.user.school,
            ).first()

            if not calendar:
                return CustomResponse.errorResponse(
                    message="Academic calendar not found."
                )

            rules = (
                AcademicCalendarWeekendRule.objects
                .filter(calendar=calendar)
                .order_by("day_of_week")
            )

            data = [
                {
                    "id": str(rule.id),
                    "calendar_id": str(rule.calendar_id),
                    "day_of_week": rule.day_of_week,
                    "rule_type": rule.rule_type,
                    "week_numbers": rule.week_numbers,
                }
                for rule in rules
            ]

            return CustomResponse.successResponse(
                message="Weekend rules fetched successfully.",
                data=data,
            )

        except Exception:
            application_logger.exception(
                "Error while fetching academic calendar weekend rules."
            )

            return CustomResponse.errorResponse(
                message="Unable to fetch weekend rules."
            )


class AcademicCalendarWeekendRuleUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar_weekend_rule.update"

    def put(self, request, rule_id):
        try:
            rule_type = request.data.get("rule_type")
            week_numbers = request.data.get("week_numbers", [])

            if not rule_id:
                return CustomResponse.errorResponse(
                    message="rule_id is required."
                )

            try:
                rule_id = uuid.UUID(str(rule_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid rule_id."
                )

            rule = (
                AcademicCalendarWeekendRule.objects
                .select_related("calendar")
                .filter(
                    id=rule_id,
                    calendar__school=request.user.school,
                )
                .first()
            )

            if not rule:
                return CustomResponse.errorResponse(
                    message="Weekend rule not found."
                )

            if not rule_type:
                return CustomResponse.errorResponse(
                    message="rule_type is required."
                )

            valid_rule_types = {
                choice[0]
                for choice in AcademicCalendarWeekendRule.RuleType.choices
            }

            if rule_type not in valid_rule_types:
                return CustomResponse.errorResponse(
                    message="Invalid rule_type."
                )

            if rule_type == (
                AcademicCalendarWeekendRule.RuleType.SELECTED_WEEKS
            ):
                if not isinstance(week_numbers, list) or not week_numbers:
                    return CustomResponse.errorResponse(
                        message="week_numbers is required for SELECTED_WEEKS."
                    )

                if any(
                    not isinstance(week, int) or week < 1 or week > 5
                    for week in week_numbers
                ):
                    return CustomResponse.errorResponse(
                        message="week_numbers must contain values from 1 to 5."
                    )

                week_numbers = sorted(set(week_numbers))

            else:
                week_numbers = []

            rule.rule_type = rule_type
            rule.week_numbers = week_numbers

            rule.save(
                update_fields=[
                    "rule_type",
                    "week_numbers",
                    "updated_at",
                ]
            )

            application_logger.info(
                "Academic calendar weekend rule updated: %s",
                rule.id,
            )

            return CustomResponse.successResponse(
                message="Weekend rule updated successfully.",
                data={
                    "id": str(rule.id),
                    "calendar_id": str(rule.calendar_id),
                    "day_of_week": rule.day_of_week,
                    "rule_type": rule.rule_type,
                    "week_numbers": rule.week_numbers,
                },
            )

        except Exception:
            application_logger.exception(
                "Error while updating academic calendar weekend rule."
            )

            return CustomResponse.errorResponse(
                message="Unable to update weekend rule."
            )


class AcademicCalendarWeekendRuleDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "academic_calendar_weekend_rule.delete"

    def delete(self, request,rule_id):
        try:

            if not rule_id:
                return CustomResponse.errorResponse(
                    message="rule_id is required."
                )

            try:
                rule_id = uuid.UUID(str(rule_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid rule_id."
                )

            rule = (
                AcademicCalendarWeekendRule.objects
                .select_related("calendar")
                .filter(
                    id=rule_id,
                    calendar__school=request.user.school,
                )
                .first()
            )

            if not rule:
                return CustomResponse.errorResponse(
                    message="Weekend rule not found."
                )

            rule.delete()

            application_logger.info(
                "Academic calendar weekend rule deleted: %s",
                rule_id,
            )

            return CustomResponse.successResponse(
                message="Weekend rule deleted successfully.",
                data={},
            )

        except Exception:
            application_logger.exception(
                "Error while deleting academic calendar weekend rule."
            )

            return CustomResponse.errorResponse(
                message="Unable to delete weekend rule."
            )
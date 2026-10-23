import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models.school import Branch, AcademicYear
from apps.timetable.models import TimetableTerm, TimetablePeriod
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class TimetableTermCreateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_term.create"

    def post(self, request):
        try:
            school = request.school

            if not school:
                return CustomResponse.errorResponse(
                    description="School is required."
                )

            name = request.data.get("name")
            academic_year_id = request.data.get("academic_year_id")
            branch_id = request.data.get("branch_id")

            start_date = request.data.get("start_date")
            end_date = request.data.get("end_date")

            # ---------------------------------
            # Required fields
            # ---------------------------------

            if not name:
                return CustomResponse.errorResponse(
                    description="Term name is required."
                )

            if not academic_year_id:
                return CustomResponse.errorResponse(
                    description="Academic year is required."
                )

            if not start_date:
                return CustomResponse.errorResponse(
                    description="Start date is required."
                )

            if not end_date:
                return CustomResponse.errorResponse(
                    description="End date is required."
                )

            # ---------------------------------
            # Validate UUIDs
            # ---------------------------------

            try:
                academic_year_uuid = uuid.UUID(
                    str(academic_year_id)
                )
            except (ValueError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid academic_year_id."
                )

            branch = None

            if branch_id:
                try:
                    branch_uuid = uuid.UUID(str(branch_id))
                except (ValueError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid branch_id."
                    )

                branch = Branch.objects.filter(
                    id=branch_uuid,
                    school=school,
                ).first()

                if not branch:
                    return CustomResponse.errorResponse(
                        description="Invalid branch."
                    )

            # ---------------------------------
            # Validate dates
            # ---------------------------------

            if start_date > end_date:
                return CustomResponse.errorResponse(
                    description="Start date cannot be after end date."
                )

            # ---------------------------------
            # Academic Year
            # ---------------------------------

            academic_year = AcademicYear.objects.filter(
                id=academic_year_uuid,
                school=school,
            ).first()

            if not academic_year:
                return CustomResponse.errorResponse(
                    description="Invalid academic year."
                )

            # ---------------------------------
            # Duplicate term
            # ---------------------------------

            if TimetableTerm.objects.filter(
                school=school,
                academic_year=academic_year,
                name__iexact=name.strip(),
            ).exists():
                return CustomResponse.errorResponse(
                    description=(
                        "Timetable term with this name "
                        "already exists."
                    )
                )

            # ---------------------------------
            # Create
            # ---------------------------------

            term = TimetableTerm.objects.create(
                school=school,
                branch=branch,
                academic_year=academic_year,
                name=name.strip(),
                start_date=start_date,
                end_date=end_date,
                status=TimetableTerm.Status.ACTIVE,
            )

            application_logger.info(
                "timetable_term_created",
                school_id=str(school.id),
                term_id=str(term.id),
                academic_year_id=str(
                    academic_year.id
                ),
            )

            return CustomResponse.successResponse(
                data={
                    "id": term.id,
                    "name": term.name,
                    "academic_year_id": term.academic_year_id,
                    "branch_id": term.branch_id,
                    "start_date": term.start_date,
                    "end_date": term.end_date,
                    "status": term.status,
                },
                description="Timetable term created successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "timetable_term_create_failed",
                error=str(e),
                school_id=(
                    str(request.school.id)
                    if getattr(request, "school", None)
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to create timetable term."
            )

class TimetableTermListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_term.view"

    def get(self, request):
        try:
            school = request.school

            academic_year_id = request.query_params.get(
                "academic_year_id"
            )
            branch_id = request.query_params.get("branch_id")
            status = request.query_params.get("status")
            search = request.query_params.get("search")

            queryset = (
                TimetableTerm.objects
                .filter(
                    school=school
                )
                .select_related(
                    "academic_year",
                    "branch",
                )
                .order_by(
                    "-academic_year__start_date",
                    "start_date",
                )
            )

            # ---------------------------------
            # Academic year
            # ---------------------------------

            if academic_year_id:
                try:
                    academic_year_uuid = uuid.UUID(
                        str(academic_year_id)
                    )
                except (ValueError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid academic_year_id."
                    )

                queryset = queryset.filter(
                    academic_year_id=academic_year_uuid
                )

            # ---------------------------------
            # Branch
            # ---------------------------------

            if branch_id:
                try:
                    branch_uuid = uuid.UUID(
                        str(branch_id)
                    )
                except (ValueError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid branch_id."
                    )

                queryset = queryset.filter(
                    branch_id=branch_uuid
                )

            # ---------------------------------
            # Status
            # ---------------------------------

            if status:
                valid_statuses = [
                    choice[0]
                    for choice in TimetableTerm.Status.choices
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                queryset = queryset.filter(
                    status=status
                )

            # ---------------------------------
            # Search
            # ---------------------------------

            if search:
                queryset = queryset.filter(
                    name__icontains=search.strip()
                )

            total = queryset.count()

            # ---------------------------------
            # Pagination
            # ---------------------------------

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                queryset,
                request,
            )

            data = []

            for term in page:
                data.append({
                    "id": term.id,
                    "name": term.name,

                    "academic_year": {
                        "id": term.academic_year.id,
                        "name": term.academic_year.name,
                    },

                    "branch": (
                        {
                            "id": term.branch.id,
                            "name": term.branch.name,
                        }
                        if term.branch
                        else None
                    ),

                    "start_date": term.start_date,
                    "end_date": term.end_date,
                    "status": term.status,
                })

            application_logger.info(
                "timetable_term_list_fetched",
                school_id=str(school.id),
                academic_year_id=academic_year_id,
                branch_id=branch_id,
                status=status,
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Timetable terms fetched successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "timetable_term_list_failed",
                error=str(e),
                school_id=(
                    str(school.id)
                    if school
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch timetable terms."
            )

class TimetableTermUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_term.update"

    def put(self, request):
        try:
            school = request.school

            term_id = request.data.get("term_id")

            if not term_id:
                return CustomResponse.errorResponse(
                    description="term_id is required."
                )

            try:
                term_uuid = uuid.UUID(str(term_id))
            except (ValueError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid term_id."
                )

            term = TimetableTerm.objects.filter(
                id=term_uuid,
                school=school,
            ).first()

            if not term:
                return CustomResponse.errorResponse(
                    description="Timetable term not found."
                )

            name = request.data.get("name")
            academic_year_id = request.data.get(
                "academic_year_id"
            )
            branch_id = request.data.get("branch_id")

            start_date = request.data.get("start_date")
            end_date = request.data.get("end_date")
            status = request.data.get("status")

            # ---------------------------------
            # Name
            # ---------------------------------

            if name is not None:
                name = name.strip()

                if not name:
                    return CustomResponse.errorResponse(
                        description="Term name cannot be empty."
                    )

                if TimetableTerm.objects.filter(
                    school=school,
                    academic_year=term.academic_year,
                    name__iexact=name,
                ).exclude(
                    id=term.id
                ).exists():
                    return CustomResponse.errorResponse(
                        description=(
                            "Timetable term with this name "
                            "already exists."
                        )
                    )

                term.name = name

            # ---------------------------------
            # Academic Year
            # ---------------------------------

            if academic_year_id:

                try:
                    academic_year_uuid = uuid.UUID(
                        str(academic_year_id)
                    )
                except (ValueError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid academic_year_id."
                    )

                academic_year = AcademicYear.objects.filter(
                    id=academic_year_uuid,
                    school=school,
                ).first()

                if not academic_year:
                    return CustomResponse.errorResponse(
                        description="Invalid academic year."
                    )

                if TimetableTerm.objects.filter(
                    school=school,
                    academic_year=academic_year,
                    name__iexact=term.name,
                ).exclude(
                    id=term.id
                ).exists():
                    return CustomResponse.errorResponse(
                        description=(
                            "Timetable term with this name "
                            "already exists for this academic year."
                        )
                    )

                term.academic_year = academic_year

            # ---------------------------------
            # Branch
            # ---------------------------------

            if branch_id is not None:

                if branch_id:
                    try:
                        branch_uuid = uuid.UUID(
                            str(branch_id)
                        )
                    except (ValueError, AttributeError):
                        return CustomResponse.errorResponse(
                            description="Invalid branch_id."
                        )

                    branch = Branch.objects.filter(
                        id=branch_uuid,
                        school=school,
                    ).first()

                    if not branch:
                        return CustomResponse.errorResponse(
                            description="Invalid branch."
                        )

                    term.branch = branch

                else:
                    term.branch = None

            # ---------------------------------
            # Dates
            # ---------------------------------

            final_start_date = (
                start_date
                if start_date is not None
                else term.start_date
            )

            final_end_date = (
                end_date
                if end_date is not None
                else term.end_date
            )

            if final_start_date > final_end_date:
                return CustomResponse.errorResponse(
                    description=(
                        "Start date cannot be after end date."
                    )
                )

            if start_date is not None:
                term.start_date = start_date

            if end_date is not None:
                term.end_date = end_date

            # ---------------------------------
            # Status
            # ---------------------------------

            if status is not None:

                valid_statuses = [
                    choice[0]
                    for choice in TimetableTerm.Status.choices
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                term.status = status

            term.save()

            application_logger.info(
                "timetable_term_updated",
                school_id=str(school.id),
                term_id=str(term.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": term.id,
                    "name": term.name,
                    "academic_year_id": (
                        term.academic_year_id
                    ),
                    "branch_id": term.branch_id,
                    "start_date": term.start_date,
                    "end_date": term.end_date,
                    "status": term.status,
                },
                description="Timetable term updated successfully.",
            )

        except Exception as e:

            application_logger.exception(
                "timetable_term_update_failed",
                error=str(e),
                school_id=(
                    str(school.id)
                    if school
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to update timetable term."
            )


class TimetablePeriodCreateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_period.create"

    def post(self, request):
        try:
            school = request.school

            if not school:
                return CustomResponse.errorResponse(
                    description="School is required."
                )

            name = request.data.get("name")
            period_number = request.data.get("period_number")
            start_time = request.data.get("start_time")
            end_time = request.data.get("end_time")
            is_break = request.data.get("is_break", False)

            # ---------------------------------
            # Required fields
            # ---------------------------------

            if not name:
                return CustomResponse.errorResponse(
                    description="Period name is required."
                )

            if period_number is None:
                return CustomResponse.errorResponse(
                    description="Period number is required."
                )

            if not start_time:
                return CustomResponse.errorResponse(
                    description="Start time is required."
                )

            if not end_time:
                return CustomResponse.errorResponse(
                    description="End time is required."
                )

            # ---------------------------------
            # Period number
            # ---------------------------------

            try:
                period_number = int(period_number)
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid period number."
                )

            if period_number <= 0:
                return CustomResponse.errorResponse(
                    description="Period number must be greater than 0."
                )

            # ---------------------------------
            # Validate time
            # ---------------------------------

            if start_time >= end_time:
                return CustomResponse.errorResponse(
                    description="Start time must be before end time."
                )

            # ---------------------------------
            # Duplicate period number
            # ---------------------------------

            if TimetablePeriod.objects.filter(
                school=school,
                period_number=period_number,
            ).exists():
                return CustomResponse.errorResponse(
                    description=(
                        "A period with this period number "
                        "already exists."
                    )
                )

            # ---------------------------------
            # Overlapping period
            # ---------------------------------

            overlapping_period = (
                TimetablePeriod.objects
                .filter(
                    school=school,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                .exists()
            )

            if overlapping_period:
                return CustomResponse.errorResponse(
                    description=(
                        "This period overlaps with an "
                        "existing period."
                    )
                )

            # ---------------------------------
            # Validate break
            # ---------------------------------

            if not isinstance(is_break, bool):
                is_break = str(is_break).lower() == "true"

            # ---------------------------------
            # Create
            # ---------------------------------

            period = TimetablePeriod.objects.create(
                school=school,
                name=name.strip(),
                period_number=period_number,
                start_time=start_time,
                end_time=end_time,
                is_break=is_break,
                status=TimetablePeriod.Status.ACTIVE,
            )

            application_logger.info(
                "timetable_period_created",
                school_id=str(school.id),
                period_id=str(period.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": period.id,
                    "name": period.name,
                    "period_number": period.period_number,
                    "start_time": period.start_time,
                    "end_time": period.end_time,
                    "is_break": period.is_break,
                    "status": period.status,
                },
                description="Timetable period created successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "timetable_period_create_failed",
                error=str(e),
                school_id=(
                    str(request.school.id)
                    if getattr(request, "school", None)
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to create timetable period."
            )

class TimetablePeriodListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_period.view"

    def get(self, request):
        try:
            school = request.school

            status = request.query_params.get("status")
            is_break = request.query_params.get("is_break")
            search = request.query_params.get("search")

            queryset = (
                TimetablePeriod.objects
                .filter(
                    school=school
                )
                .order_by("period_number")
            )

            # ---------------------------------
            # Status
            # ---------------------------------

            if status:
                valid_statuses = [
                    choice[0]
                    for choice in TimetablePeriod.Status.choices
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                queryset = queryset.filter(
                    status=status
                )

            # ---------------------------------
            # Break filter
            # ---------------------------------

            if is_break is not None:
                if str(is_break).lower() not in [
                    "true",
                    "false",
                ]:
                    return CustomResponse.errorResponse(
                        description="Invalid is_break value."
                    )

                queryset = queryset.filter(
                    is_break=str(is_break).lower() == "true"
                )

            # ---------------------------------
            # Search
            # ---------------------------------

            if search:
                queryset = queryset.filter(
                    name__icontains=search.strip()
                )

            total = queryset.count()

            # ---------------------------------
            # Pagination
            # ---------------------------------

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                queryset,
                request,
            )

            data = []

            for period in page:
                data.append({
                    "id": period.id,
                    "name": period.name,
                    "period_number": period.period_number,
                    "start_time": period.start_time,
                    "end_time": period.end_time,
                    "is_break": period.is_break,
                    "status": period.status,
                })

            application_logger.info(
                "timetable_period_list_fetched",
                school_id=str(school.id),
                status=status,
                is_break=is_break,
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Timetable periods fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "timetable_period_list_failed",
                error=str(e),
                school_id=(
                    str(school.id)
                    if school
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch timetable periods."
            )
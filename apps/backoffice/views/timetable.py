import uuid
from django.http import HttpResponse
from io import BytesIO
from openpyxl import load_workbook, Workbook

from django.db import transaction
from openpyxl.styles import Alignment, PatternFill, Font
from openpyxl.worksheet.datavalidation import DataValidation
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models.school import Branch, AcademicYear
from apps.timetable.models import TimetableTerm, TimetablePeriod, Room, Timetable
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

    def put(self, request,term_id):
        try:
            school = request.school


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


class TimetablePeriodUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_period.update"

    def put(self, request,period_id):
        try:
            school = request.school


            if not period_id:
                return CustomResponse.errorResponse(
                    description="period_id is required."
                )

            try:
                period_uuid = uuid.UUID(str(period_id))
            except (ValueError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid period_id."
                )

            period = TimetablePeriod.objects.filter(
                id=period_uuid,
                school=school,
            ).first()

            if not period:
                return CustomResponse.errorResponse(
                    description="Timetable period not found."
                )

            name = request.data.get("name")
            period_number = request.data.get("period_number")
            start_time = request.data.get("start_time")
            end_time = request.data.get("end_time")
            is_break = request.data.get("is_break")
            status = request.data.get("status")

            # ---------------------------------
            # Name
            # ---------------------------------

            if name is not None:
                name = name.strip()

                if not name:
                    return CustomResponse.errorResponse(
                        description="Period name cannot be empty."
                    )

                period.name = name

            # ---------------------------------
            # Period number
            # ---------------------------------

            if period_number is not None:

                try:
                    period_number = int(period_number)
                except (ValueError, TypeError):
                    return CustomResponse.errorResponse(
                        description="Invalid period number."
                    )

                if period_number <= 0:
                    return CustomResponse.errorResponse(
                        description=(
                            "Period number must be greater than 0."
                        )
                    )

                if TimetablePeriod.objects.filter(
                    school=school,
                    period_number=period_number,
                ).exclude(
                    id=period.id
                ).exists():
                    return CustomResponse.errorResponse(
                        description=(
                            "A period with this period number "
                            "already exists."
                        )
                    )

                period.period_number = period_number

            # ---------------------------------
            # Final times
            # ---------------------------------

            final_start_time = (
                start_time
                if start_time is not None
                else period.start_time
            )

            final_end_time = (
                end_time
                if end_time is not None
                else period.end_time
            )

            if final_start_time >= final_end_time:
                return CustomResponse.errorResponse(
                    description="Start time must be before end time."
                )

            # ---------------------------------
            # Overlapping period
            # ---------------------------------

            overlapping_period = (
                TimetablePeriod.objects
                .filter(
                    school=school,
                    start_time__lt=final_end_time,
                    end_time__gt=final_start_time,
                )
                .exclude(
                    id=period.id
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

            if start_time is not None:
                period.start_time = start_time

            if end_time is not None:
                period.end_time = end_time

            # ---------------------------------
            # Break
            # ---------------------------------

            if is_break is not None:

                if not isinstance(is_break, bool):
                    is_break = (
                        str(is_break).lower() == "true"
                    )

                period.is_break = is_break

            # ---------------------------------
            # Status
            # ---------------------------------

            if status is not None:

                valid_statuses = [
                    choice[0]
                    for choice in TimetablePeriod.Status.choices
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                period.status = status

            period.save()

            application_logger.info(
                "timetable_period_updated",
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
                description="Timetable period updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "timetable_period_update_failed",
                error=str(e),
                school_id=(
                    str(school.id)
                    if school
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to update timetable period."
            )

class TimetablePeriodDeleteAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "timetable_period.delete"

    def delete(self, request,period_id):
        try:
            school = request.school


            if not period_id:
                return CustomResponse.errorResponse(
                    description="period_id is required."
                )

            try:
                period_uuid = uuid.UUID(str(period_id))
            except (ValueError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid period_id."
                )

            period = TimetablePeriod.objects.filter(
                id=period_uuid,
                school=school,
            ).first()

            if not period:
                return CustomResponse.errorResponse(
                    description="Timetable period not found."
                )

            period.status = TimetablePeriod.Status.INACTIVE

            period.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            application_logger.info(
                "timetable_period_deactivated",
                school_id=str(school.id),
                period_id=str(period.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": period.id,
                    "status": period.status,
                },
                description="Timetable period deactivated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "timetable_period_deactivate_failed",
                error=str(e),
                school_id=(
                    str(school.id)
                    if school
                    else None
                ),
            )

            return CustomResponse.errorResponse(
                description="Failed to deactivate timetable period."
            )

class RoomCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "room.create"

    def post(self, request):
        try:
            school = request.school

            name = request.data.get("name")
            room_type = request.data.get("room_type")
            location = request.data.get("location")
            capacity = request.data.get("capacity", 0)
            facilities = request.data.get("facilities")
            branch_id = request.data.get("branch_id")

            if not name:
                return CustomResponse.errorResponse(
                    message="Room name is required"
                )

            if not room_type:
                return CustomResponse.errorResponse(
                    message="Room type is required"
                )

            valid_room_types = dict(Room.ROOM_TYPE_CHOICES)

            if room_type not in valid_room_types:
                return CustomResponse.errorResponse(
                    message="Invalid room type"
                )

            try:
                capacity = int(capacity)
            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    message="Capacity must be a valid number"
                )

            if capacity < 0:
                return CustomResponse.errorResponse(
                    message="Capacity cannot be negative"
                )

            branch = None

            if branch_id:
                try:
                    branch_id = uuid.UUID(str(branch_id))
                except ValueError:
                    return CustomResponse.errorResponse(
                        message="Invalid branch_id"
                    )

                branch = Branch.objects.filter(
                    id=branch_id,
                    school=school
                ).first()

                if not branch:
                    return CustomResponse.errorResponse(
                        message="Branch not found"
                    )

            if Room.objects.filter(
                school=school,
                name__iexact=name.strip()
            ).exists():
                return CustomResponse.errorResponse(
                    message="Room with this name already exists"
                )

            room = Room.objects.create(
                school=school,
                branch=branch,
                name=name.strip(),
                room_type=room_type,
                location=location,
                capacity=capacity,
                facilities=facilities,
                status="ACTIVE"
            )

            application_logger.info(
                "room_created | room_id=%s | school_id=%s",
                room.id,
                school.id
            )

            return CustomResponse.successResponse(
                message="Room created successfully",
                data={
                    "id": str(room.id),
                    "name": room.name,
                    "room_type": room.room_type,
                    "location": room.location,
                    "capacity": room.capacity,
                    "facilities": room.facilities,
                    "status": room.status,
                    "branch_id": str(room.branch_id) if room.branch_id else None
                }
            )

        except Exception:
            application_logger.exception("room_create_failed")

            return CustomResponse.errorResponse(
                message="Failed to create room"
            )

class RoomListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "room.view"

    def get(self, request):
        try:
            school = request.school

            search = request.GET.get("search")
            room_type = request.GET.get("room_type")
            branch_id = request.GET.get("branch_id")
            status = request.GET.get("status")

            rooms = Room.objects.filter(
                school=school
            ).select_related("branch").order_by("name")

            if search:
                rooms = rooms.filter(
                    Q(name__icontains=search) |
                    Q(location__icontains=search) |
                    Q(facilities__icontains=search)
                )

            if room_type:
                rooms = rooms.filter(
                    room_type=room_type
                )

            if status:
                rooms = rooms.filter(
                    status=status
                )

            if branch_id:
                try:
                    branch_id = uuid.UUID(str(branch_id))
                except ValueError:
                    return CustomResponse.errorResponse(
                        message="Invalid branch_id"
                    )

                rooms = rooms.filter(
                    branch_id=branch_id
                )

            paginator = CustomPageNumberPagination()
            paginated_rooms = paginator.paginate_queryset(
                rooms,
                request
            )

            data = []

            for room in paginated_rooms:
                data.append({
                    "id": str(room.id),
                    "name": room.name,
                    "room_type": room.room_type,
                    "room_type_display": room.get_room_type_display(),
                    "location": room.location,
                    "capacity": room.capacity,
                    "facilities": room.facilities,
                    "status": room.status,
                    "branch": {
                        "id": str(room.branch_id),
                        "name": room.branch.name
                    } if room.branch else None
                })

            return paginator.get_paginated_response(data)

        except Exception:
            application_logger.exception("room_list_failed")

            return CustomResponse.errorResponse(
                message="Failed to fetch rooms"
            )

class RoomUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "room.update"

    def put(self, request):
        try:
            school = request.school
            room_id = request.data.get("room_id")

            if not room_id:
                return CustomResponse.errorResponse(
                    message="room_id is required"
                )

            try:
                room_id = uuid.UUID(str(room_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid room_id"
                )

            room = Room.objects.filter(
                id=room_id,
                school=school
            ).first()

            if not room:
                return CustomResponse.errorResponse(
                    message="Room not found"
                )

            name = request.data.get("name")
            room_type = request.data.get("room_type")
            location = request.data.get("location")
            capacity = request.data.get("capacity")
            facilities = request.data.get("facilities")
            branch_id = request.data.get("branch_id")
            status = request.data.get("status")

            if name is not None:
                name = name.strip()

                if not name:
                    return CustomResponse.errorResponse(
                        message="Room name cannot be empty"
                    )

                if Room.objects.filter(
                    school=school,
                    name__iexact=name
                ).exclude(id=room.id).exists():
                    return CustomResponse.errorResponse(
                        message="Room with this name already exists"
                    )

                room.name = name

            if room_type is not None:
                valid_room_types = dict(Room.ROOM_TYPE_CHOICES)

                if room_type not in valid_room_types:
                    return CustomResponse.errorResponse(
                        message="Invalid room type"
                    )

                room.room_type = room_type

            if location is not None:
                room.location = location

            if capacity is not None:
                try:
                    capacity = int(capacity)
                except (TypeError, ValueError):
                    return CustomResponse.errorResponse(
                        message="Capacity must be a valid number"
                    )

                if capacity < 0:
                    return CustomResponse.errorResponse(
                        message="Capacity cannot be negative"
                    )

                room.capacity = capacity

            if facilities is not None:
                room.facilities = facilities

            if branch_id is not None:
                if branch_id:
                    try:
                        branch_id = uuid.UUID(str(branch_id))
                    except ValueError:
                        return CustomResponse.errorResponse(
                            message="Invalid branch_id"
                        )

                    branch = Branch.objects.filter(
                        id=branch_id,
                        school=school
                    ).first()

                    if not branch:
                        return CustomResponse.errorResponse(
                            message="Branch not found"
                        )

                    room.branch = branch
                else:
                    room.branch = None

            if status is not None:
                valid_statuses = dict(Room.STATUS_CHOICES)

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        message="Invalid status"
                    )

                room.status = status

            room.save()

            application_logger.info(
                "room_updated | room_id=%s | school_id=%s",
                room.id,
                school.id
            )

            return CustomResponse.successResponse(
                message="Room updated successfully",
                data={
                    "id": str(room.id),
                    "name": room.name,
                    "room_type": room.room_type,
                    "location": room.location,
                    "capacity": room.capacity,
                    "facilities": room.facilities,
                    "status": room.status,
                    "branch_id": (
                        str(room.branch_id)
                        if room.branch_id else None
                    )
                }
            )

        except Exception:
            application_logger.exception("room_update_failed")

            return CustomResponse.errorResponse(
                message="Failed to update room"
            )

class RoomDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "room.delete"

    def delete(self, request):
        try:
            school = request.school
            room_id = request.GET.get("room_id")

            if not room_id:
                return CustomResponse.errorResponse(
                    message="room_id is required"
                )

            try:
                room_id = uuid.UUID(str(room_id))
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid room_id"
                )

            room = Room.objects.filter(
                id=room_id,
                school=school
            ).first()

            if not room:
                return CustomResponse.errorResponse(
                    message="Room not found"
                )

            room.status = "INACTIVE"
            room.save(update_fields=["status"])

            application_logger.info(
                "room_deactivated | room_id=%s | school_id=%s",
                room.id,
                school.id
            )

            return CustomResponse.successResponse(
                message="Room deactivated successfully"
            )

        except Exception:
            application_logger.exception("room_delete_failed")

            return CustomResponse.errorResponse(
                message="Failed to deactivate room"
            )

class RoomExcelImportAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "room.create"

    def post(self, request):
        try:
            school = request.school
            excel_file = request.FILES.get("file")

            if not excel_file:
                return CustomResponse.errorResponse(
                    message="Excel file is required"
                )

            if not excel_file.name.lower().endswith(
                (".xlsx", ".xls")
            ):
                return CustomResponse.errorResponse(
                    message="Only Excel files are allowed"
                )

            try:
                workbook = load_workbook(
                    excel_file,
                    data_only=True
                )
            except Exception:
                return CustomResponse.errorResponse(
                    message="Invalid Excel file"
                )

            if "Rooms" not in workbook.sheetnames:
                return CustomResponse.errorResponse(
                    message="Rooms sheet is required"
                )

            sheet = workbook["Rooms"]

            rows = list(sheet.iter_rows(values_only=True))

            if not rows:
                return CustomResponse.errorResponse(
                    message="Excel file is empty"
                )

            headers = [
                str(value).strip().lower()
                if value is not None else ""
                for value in rows[0]
            ]

            required_columns = [
                "name",
                "room_type",
                "capacity",
            ]

            missing_columns = [
                column
                for column in required_columns
                if column not in headers
            ]

            if missing_columns:
                return CustomResponse.errorResponse(
                    message="Required columns are missing",
                    data={
                        "missing_columns": missing_columns
                    }
                )

            column_index = {
                column: headers.index(column)
                for column in headers
                if column
            }

            valid_room_types = dict(Room.ROOM_TYPE_CHOICES)
            valid_statuses = dict(Room.STATUS_CHOICES)

            errors = []
            valid_rows = []

            for row_number, row in enumerate(
                rows[1:],
                start=2
            ):
                # Skip completely empty rows
                if not any(
                    value is not None
                    for value in row
                ):
                    continue

                def get_value(column):
                    index = column_index.get(column)

                    if index is None or index >= len(row):
                        return None

                    value = row[index]

                    if isinstance(value, str):
                        return value.strip()

                    return value

                name = get_value("name")
                room_type = get_value("room_type")
                location = get_value("location")
                capacity = get_value("capacity")
                facilities = get_value("facilities")
                status = get_value("status") or "ACTIVE"
                branch_id = get_value("branch_id")

                row_errors = []

                # -------------------------
                # Name validation
                # -------------------------

                if not name:
                    row_errors.append(
                        "Room name is required"
                    )

                # -------------------------
                # Room type validation
                # -------------------------

                if not room_type:
                    row_errors.append(
                        "Room type is required"
                    )
                elif room_type not in valid_room_types:
                    row_errors.append(
                        f"Invalid room_type '{room_type}'. "
                        f"Allowed values: "
                        f"{', '.join(valid_room_types.keys())}"
                    )

                # -------------------------
                # Capacity validation
                # -------------------------

                try:
                    capacity = int(capacity)
                    if capacity < 0:
                        row_errors.append(
                            "Capacity cannot be negative"
                        )
                except (TypeError, ValueError):
                    row_errors.append(
                        "Capacity must be a valid number"
                    )

                # -------------------------
                # Status validation
                # -------------------------

                if status not in valid_statuses:
                    row_errors.append(
                        f"Invalid status '{status}'"
                    )

                # -------------------------
                # Branch validation
                # -------------------------

                branch = None

                if branch_id:

                    try:
                        branch_uuid = uuid.UUID(
                            str(branch_id)
                        )
                    except ValueError:
                        row_errors.append(
                            "Invalid branch_id"
                        )
                        branch_uuid = None

                    if branch_uuid:
                        branch = Branch.objects.filter(
                            id=branch_uuid,
                            school=school
                        ).first()

                        if not branch:
                            row_errors.append(
                                "Branch not found"
                            )

                # -------------------------
                # Duplicate in database
                # -------------------------

                if name:
                    if Room.objects.filter(
                        school=school,
                        name__iexact=name
                    ).exists():
                        row_errors.append(
                            f"Room '{name}' already exists"
                        )

                # -------------------------
                # Duplicate inside Excel
                # -------------------------

                if name:
                    duplicate_excel = any(
                        item["name"].lower() == name.lower()
                        for item in valid_rows
                    )

                    if duplicate_excel:
                        row_errors.append(
                            f"Duplicate room '{name}' "
                            f"found in Excel"
                        )

                if row_errors:
                    errors.append({
                        "row": row_number,
                        "name": name,
                        "errors": row_errors
                    })
                    continue

                valid_rows.append({
                    "name": name,
                    "room_type": room_type,
                    "location": location,
                    "capacity": capacity,
                    "facilities": facilities,
                    "status": status,
                    "branch": branch
                })

            # --------------------------------
            # Do not insert anything if errors
            # --------------------------------

            if errors:
                return CustomResponse.errorResponse(
                    message="Excel validation failed",
                    data={
                        "total_rows": len(rows) - 1,
                        "valid_rows": len(valid_rows),
                        "error_rows": len(errors),
                        "errors": errors
                    }
                )

            # --------------------------------
            # Create rooms atomically
            # --------------------------------

            with transaction.atomic():

                rooms = Room.objects.bulk_create([
                    Room(
                        school=school,
                        branch=item["branch"],
                        name=item["name"],
                        room_type=item["room_type"],
                        location=item["location"],
                        capacity=item["capacity"],
                        facilities=item["facilities"],
                        status=item["status"]
                    )
                    for item in valid_rows
                ])

            application_logger.info(
                "rooms_excel_imported | school_id=%s | count=%s",
                school.id,
                len(rooms)
            )

            return CustomResponse.successResponse(
                message="Rooms imported successfully",
                data={
                    "total_rooms": len(rooms),
                    "rooms": [
                        {
                            "id": str(room.id),
                            "name": room.name,
                            "room_type": room.room_type,
                            "location": room.location,
                            "capacity": room.capacity,
                            "facilities": room.facilities,
                            "status": room.status,
                            "branch_id": (
                                str(room.branch_id)
                                if room.branch_id
                                else None
                            )
                        }
                        for room in rooms
                    ]
                }
            )

        except Exception:
            application_logger.exception(
                "rooms_excel_import_failed"
            )

            return CustomResponse.errorResponse(
                message="Failed to import rooms"
            )

class RoomExcelTemplateDownloadAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "room.create"

    def get(self, request):
        try:
            workbook = Workbook()

            sheet = workbook.active
            sheet.title = "Rooms"

            # -------------------------
            # Headers
            # -------------------------

            headers = [
                "name",
                "room_type",
                "location",
                "capacity",
                "facilities",
                "status",
                "branch_id",
            ]

            for column, header in enumerate(headers, start=1):
                cell = sheet.cell(
                    row=1,
                    column=column,
                    value=header
                )

                cell.font = Font(bold=True)
                cell.fill = PatternFill(
                    start_color="D9EAF7",
                    end_color="D9EAF7",
                    fill_type="solid"
                )
                cell.alignment = Alignment(
                    horizontal="center"
                )

            # -------------------------
            # Example rows
            # -------------------------

            example_rows = [
                [
                    "Room 101",
                    "CLASSROOM",
                    "First Floor",
                    40,
                    "Projector",
                    "ACTIVE",
                    ""
                ],
                [
                    "Science Lab",
                    "LAB",
                    "Ground Floor",
                    30,
                    "Computers, Projector",
                    "ACTIVE",
                    ""
                ],
            ]

            for row in example_rows:
                sheet.append(row)

            # -------------------------
            # Column widths
            # -------------------------

            sheet.column_dimensions["A"].width = 25
            sheet.column_dimensions["B"].width = 20
            sheet.column_dimensions["C"].width = 25
            sheet.column_dimensions["D"].width = 12
            sheet.column_dimensions["E"].width = 35
            sheet.column_dimensions["F"].width = 15
            sheet.column_dimensions["G"].width = 40

            # -------------------------
            # Room type dropdown
            # -------------------------

            room_types = [
                choice[0]
                for choice in Room.ROOM_TYPE_CHOICES
            ]

            room_type_formula = (
                '"' + ",".join(room_types) + '"'
            )

            room_type_validation = DataValidation(
                type="list",
                formula1=room_type_formula,
                allow_blank=False
            )

            room_type_validation.error = (
                "Please select a valid room type."
            )

            room_type_validation.errorTitle = (
                "Invalid Room Type"
            )

            sheet.add_data_validation(
                room_type_validation
            )

            room_type_validation.add(
                "B2:B1000"
            )

            # -------------------------
            # Status dropdown
            # -------------------------

            statuses = [
                choice[0]
                for choice in Room.RoomType
            ]

            status_formula = (
                '"' + ",".join(statuses) + '"'
            )

            status_validation = DataValidation(
                type="list",
                formula1=status_formula,
                allow_blank=False
            )

            status_validation.error = (
                "Please select a valid status."
            )

            status_validation.errorTitle = (
                "Invalid Status"
            )

            sheet.add_data_validation(
                status_validation
            )

            status_validation.add(
                "F2:F1000"
            )

            # -------------------------
            # Capacity validation
            # -------------------------

            capacity_validation = DataValidation(
                type="whole",
                operator="greaterThanOrEqual",
                formula1="0",
                allow_blank=False
            )

            capacity_validation.error = (
                "Capacity must be 0 or greater."
            )

            capacity_validation.errorTitle = (
                "Invalid Capacity"
            )

            sheet.add_data_validation(
                capacity_validation
            )

            capacity_validation.add(
                "D2:D1000"
            )

            # -------------------------
            # Freeze header
            # -------------------------

            sheet.freeze_panes = "A2"

            # -------------------------
            # Create response
            # -------------------------

            output = BytesIO()

            workbook.save(output)
            output.seek(0)

            application_logger.info(
                "room_excel_template_downloaded | "
                "school_id=%s",
                request.school.id
            )

            response = HttpResponse(
                output.getvalue(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )

            response[
                "Content-Disposition"
            ] = (
                'attachment; '
                'filename="room_import_template.xlsx"'
            )

            return response

        except Exception:
            application_logger.exception(
                "room_excel_template_download_failed"
            )

            return CustomResponse.errorResponse(
                message="Failed to generate room Excel template"
            )

class TimetableCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "timetable.create"

    def post(self, request):
        try:
            school = request.school

            name = request.data.get("name")
            academic_year_id = request.data.get("academic_year_id")
            term_id = request.data.get("term_id")
            branch_id = request.data.get("branch_id")
            status = request.data.get("status", "DRAFT")

            if not name:
                return CustomResponse.errorResponse(
                    message="Timetable name is required"
                )

            if not academic_year_id:
                return CustomResponse.errorResponse(
                    message="Academic year is required"
                )

            if not term_id:
                return CustomResponse.errorResponse(
                    message="Timetable term is required"
                )

            # -------------------------
            # UUID validation
            # -------------------------

            try:
                academic_year_uuid = uuid.UUID(
                    str(academic_year_id)
                )
                term_uuid = uuid.UUID(
                    str(term_id)
                )
            except (ValueError, AttributeError):
                return CustomResponse.errorResponse(
                    message="Invalid academic_year_id or term_id"
                )

            # -------------------------
            # Academic Year
            # -------------------------

            academic_year = AcademicYear.objects.filter(
                id=academic_year_uuid,
                school=school,
            ).first()

            if not academic_year:
                return CustomResponse.errorResponse(
                    message="Academic year not found"
                )

            # -------------------------
            # Timetable Term
            # -------------------------

            term = TimetableTerm.objects.filter(
                id=term_uuid,
                school=school,
                academic_year=academic_year,
            ).first()

            if not term:
                return CustomResponse.errorResponse(
                    message="Timetable term not found"
                )

            # -------------------------
            # Branch
            # -------------------------

            branch = None

            if branch_id:
                try:
                    branch_uuid = uuid.UUID(
                        str(branch_id)
                    )
                except (ValueError, AttributeError):
                    return CustomResponse.errorResponse(
                        message="Invalid branch_id"
                    )

                branch = Branch.objects.filter(
                    id=branch_uuid,
                    school=school,
                ).first()

                if not branch:
                    return CustomResponse.errorResponse(
                        message="Branch not found"
                    )

            # -------------------------
            # Status
            # -------------------------

            valid_statuses = dict(
                Timetable.STATUS_CHOICES
            )

            if status not in valid_statuses:
                return CustomResponse.errorResponse(
                    message="Invalid timetable status"
                )

            # -------------------------
            # Duplicate
            # -------------------------

            if Timetable.objects.filter(
                school=school,
                academic_year=academic_year,
                term=term,
                name__iexact=name.strip(),
            ).exists():
                return CustomResponse.errorResponse(
                    message="Timetable with this name already exists"
                )

            # -------------------------
            # Create
            # -------------------------

            timetable = Timetable.objects.create(
                school=school,
                branch=branch,
                academic_year=academic_year,
                term=term,
                name=name.strip(),
                status=status,
            )

            application_logger.info(
                "timetable_created | timetable_id=%s | school_id=%s",
                timetable.id,
                school.id,
            )

            return CustomResponse.successResponse(
                message="Timetable created successfully",
                data={
                    "id": str(timetable.id),
                    "name": timetable.name,
                    "status": timetable.status,
                    "academic_year": {
                        "id": str(academic_year.id),
                        "name": academic_year.name,
                    },
                    "term": {
                        "id": str(term.id),
                        "name": term.name,
                    },
                    "branch": {
                        "id": str(branch.id),
                        "name": branch.name,
                    } if branch else None,
                },
            )

        except Exception:
            application_logger.exception(
                "timetable_create_failed"
            )

            return CustomResponse.errorResponse(
                message="Failed to create timetable"
            )
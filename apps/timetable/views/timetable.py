import uuid
from datetime import date
from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models.school import Student
from apps.timetable.models import TimetableEntry, TimetableSubstitution, TimetableTerm
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger

class TimetableTermLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]


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
class TimetableAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        application_logger.info(
            "student_timetable_started",
            extra={
                "requested_by": str(request.user.id),
            },
        )

        # ==========================================================
        # REQUEST PARAMETERS
        # ==========================================================

        student_id = request.GET.get("student_id")
        term_id = request.GET.get("term_id")
        date_value = request.GET.get("date")

        # ==========================================================
        # STUDENT ID VALIDATION
        # ==========================================================

        if not student_id:

            return CustomResponse.errorResponse(
                description="student_id is required."
            )

        try:

            student_uuid = UUID(
                str(student_id)
            )

        except (
            ValueError,
            TypeError,
            AttributeError,
        ):

            return CustomResponse.errorResponse(
                description="Invalid student_id."
            )

        # ==========================================================
        # GET STUDENT
        # ==========================================================

        student = (
            Student.objects
            .filter(
                id=student_uuid,
                is_active=True,
            )
            .select_related(
                "school",
                "branch",
                "academic_year",
                "grade",
                "section",
            )
            .first()
        )

        if not student:

            application_logger.warning(
                "student_timetable_failed",
                extra={
                    "requested_by": str(
                        request.user.id
                    ),
                    "student_id": str(
                        student_id
                    ),
                    "reason": "student_not_found",
                },
            )

            return CustomResponse.errorResponse(
                description="Student not found."
            )

        # ==========================================================
        # PARENT OWNERSHIP VALIDATION
        # ==========================================================

        # parent_mobile = getattr(
        #     request.user,
        #     "mobile",
        #     None,
        # )

        # if not parent_mobile:

        #     return CustomResponse.errorResponse(
        #         description=(
        #             "Parent mobile number is not available."
        #         )
        #     )

        # parent_mobile = str(
        #     parent_mobile
        # ).strip()

        # student_parent_match = (
        #     Student.objects
        #     .filter(
        #         id=student.id,
        #     )
        #     .filter(
        #         Q(father_mobile=parent_mobile)
        #         | Q(mother_mobile=parent_mobile)
        #         | Q(guardian_mobile=parent_mobile)
        #     )
        #     .exists()
        # )

        # if not student_parent_match:

        #     application_logger.warning(
        #         "student_timetable_unauthorized",
        #         extra={
        #             "requested_by": str(
        #                 request.user.id
        #             ),
        #             "student_id": str(
        #                 student.id
        #             ),
        #             "reason": (
        #                 "student_not_linked_to_parent"
        #             ),
        #         },
        #     )

        #     return CustomResponse.errorResponse(
        #         description=(
        #             "You are not authorized to view "
        #             "this student's timetable."
        #         )
        #     )

        # ==========================================================
        # TERM VALIDATION
        # ==========================================================

        term = None

        if term_id:

            try:

                term_uuid = UUID(
                    str(term_id)
                )

            except (
                ValueError,
                TypeError,
                AttributeError,
            ):

                return CustomResponse.errorResponse(
                    description="Invalid term_id."
                )

            term = (
                TimetableTerm.objects
                .filter(
                    id=term_uuid,
                    school=student.school,
                    status=TimetableTerm.Status.ACTIVE,
                )
                .first()
            )

            if not term:

                application_logger.warning(
                    "student_timetable_failed",
                    extra={
                        "requested_by": str(
                            request.user.id
                        ),
                        "student_id": str(
                            student.id
                        ),
                        "term_id": str(
                            term_id
                        ),
                        "reason": "term_not_found",
                    },
                )

                return CustomResponse.errorResponse(
                    description="Timetable term not found."
                )

        # ==========================================================
        # DATE VALIDATION
        # ==========================================================

        selected_date = None

        if date_value:

            try:

                selected_date = date.fromisoformat(
                    str(date_value)
                )

            except (
                ValueError,
                TypeError,
            ):

                return CustomResponse.errorResponse(
                    description=(
                        "Invalid date. "
                        "Use YYYY-MM-DD format."
                    )
                )

        # ==========================================================
        # TIMETABLE ENTRIES
        # ==========================================================

        entries = (
            TimetableEntry.objects
            .filter(
                timetable__school=student.school,
                grade_id=student.grade_id,
                section_id=student.section_id,
                status=TimetableEntry.Status.ACTIVE,
            )
            .select_related(
                "timetable",
                "timetable__term",
                "grade",
                "section",
                "subject",
                "teacher",
                "period",
            )
            .order_by(
                "day_of_week",
                "period__period_number",
            )
        )

        # ==========================================================
        # TERM FILTER
        # ==========================================================

        if term:

            entries = entries.filter(
                timetable__term_id=term.id
            )

        # ==========================================================
        # DATE-SPECIFIC ENTRIES
        # ==========================================================

        if selected_date:

            selected_day = (
                selected_date
                .strftime("%A")
                .upper()
            )

            entries = entries.filter(
                day_of_week=selected_day
            )

        # ==========================================================
        # GET ENTRY IDS
        # ==========================================================

        entry_ids = list(
            entries.values_list(
                "id",
                flat=True,
            )
        )

        # ==========================================================
        # SUBSTITUTIONS
        # ==========================================================

        substitutions = {}

        if selected_date and entry_ids:

            substitution_queryset = (
                TimetableSubstitution.objects
                .filter(
                    timetable_entry_id__in=entry_ids,
                    date=selected_date,
                    status=(
                        TimetableSubstitution
                        .Status
                        .SCHEDULED
                    ),
                )
                .select_related(
                    "original_teacher",
                    "substitute_teacher",
                )
            )

            substitutions = {
                substitution.timetable_entry_id:
                    substitution
                for substitution
                in substitution_queryset
            }

        # ==========================================================
        # WEEKLY / DATE SCHEDULE
        # ==========================================================

        schedule = {
            "MONDAY": [],
            "TUESDAY": [],
            "WEDNESDAY": [],
            "THURSDAY": [],
            "FRIDAY": [],
            "SATURDAY": [],
            "SUNDAY": [],
        }

        total_periods = 0
        substitution_count = 0

        # ==========================================================
        # BUILD RESPONSE
        # ==========================================================

        for entry in entries:

            substitution = substitutions.get(
                entry.id
            )

            regular_teacher = entry.teacher

            current_teacher = (
                substitution.substitute_teacher
                if substitution
                else regular_teacher
            )

            if substitution:
                substitution_count += 1

            total_periods += 1

            schedule_entry = {

                "entry_id": str(
                    entry.id
                ),

                # --------------------------------------------------
                # PERIOD
                # --------------------------------------------------

                "period": {
                    "id": str(
                        entry.period.id
                    ),
                    "period_number": (
                        entry.period.period_number
                    ),
                    "start_time": getattr(
                        entry.period,
                        "start_time",
                        None,
                    ),
                    "end_time": getattr(
                        entry.period,
                        "end_time",
                        None,
                    ),
                },

                # --------------------------------------------------
                # SUBJECT
                # --------------------------------------------------

                "subject": {
                    "id": str(
                        entry.subject.id
                    ),
                    "name": (
                        entry.subject.name
                    ),
                },

                # --------------------------------------------------
                # REGULAR TEACHER
                # --------------------------------------------------

                "regular_teacher": {
                    "id": str(
                        regular_teacher.id
                    ),
                    "employee_id": getattr(
                        regular_teacher,
                        "employee_id",
                        None,
                    ),
                    "name": (
                        regular_teacher.name
                    ),
                },

                # --------------------------------------------------
                # CURRENT TEACHER
                # --------------------------------------------------

                "teacher": {
                    "id": str(
                        current_teacher.id
                    ),
                    "employee_id": getattr(
                        current_teacher,
                        "employee_id",
                        None,
                    ),
                    "name": (
                        current_teacher.name
                    ),
                },

                # --------------------------------------------------
                # SUBSTITUTION
                # --------------------------------------------------

                "substitution": (
                    {
                        "id": str(
                            substitution.id
                        ),
                        "date": (
                            substitution.date
                        ),
                        "status": (
                            substitution.status
                        ),
                        "reason": (
                            substitution.reason
                        ),

                        "original_teacher": {
                            "id": str(
                                substitution
                                .original_teacher
                                .id
                            ),
                            "name": (
                                substitution
                                .original_teacher
                                .name
                            ),
                        },

                        "substitute_teacher": {
                            "id": str(
                                substitution
                                .substitute_teacher
                                .id
                            ),
                            "name": (
                                substitution
                                .substitute_teacher
                                .name
                            ),
                        },
                    }
                    if substitution
                    else None
                ),

                "has_substitution": (
                    substitution is not None
                ),

                "notes": entry.notes,
            }

            schedule[
                entry.day_of_week
            ].append(
                schedule_entry
            )

        # ==========================================================
        # STUDENT DATA
        # ==========================================================

        student_data = {
            "id": str(
                student.id
            ),
            "name": student.name,
            "admission_number": (
                student.admission_number
            ),

            "grade": {
                "id": str(
                    student.grade.id
                ),
                "name": (
                    student.grade.name
                ),
            },

            "section": {
                "id": str(
                    student.section.id
                ),
                "name": (
                    student.section.name
                ),
            },
        }

        # ==========================================================
        # TERM DATA
        # ==========================================================

        selected_term = term

        if not selected_term:

            first_entry = entries.first()

            if first_entry:
                selected_term = (
                    first_entry.timetable.term
                )

        term_data = None

        if selected_term:

            term_data = {
                "id": str(
                    selected_term.id
                ),
                "name": (
                    selected_term.name
                ),
                "start_date": (
                    selected_term.start_date
                ),
                "end_date": (
                    selected_term.end_date
                ),
            }

        # ==========================================================
        # RESPONSE LOG
        # ==========================================================

        application_logger.info(
            "student_timetable_completed",
            extra={
                "requested_by": str(
                    request.user.id
                ),
                "student_id": str(
                    student.id
                ),
                "term_id": (
                    str(term.id)
                    if term
                    else None
                ),
                "date": (
                    str(selected_date)
                    if selected_date
                    else None
                ),
                "total_periods": (
                    total_periods
                ),
                "substitution_count": (
                    substitution_count
                ),
            },
        )

        # ==========================================================
        # RESPONSE
        # ==========================================================

        return CustomResponse.successResponse(
            description=(
                "Student timetable fetched successfully."
            ),
            data={
                "student": student_data,

                "term": term_data,

                "date": (
                    selected_date
                    if selected_date
                    else None
                ),

                "total_periods": (
                    total_periods
                ),

                "substitution_count": (
                    substitution_count
                ),

                "schedule": schedule,
            },
        )
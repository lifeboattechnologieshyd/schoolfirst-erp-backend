import uuid

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.examination.models import Examination, ExaminationSchedule, ReportCard, HallTicket, ExaminationAttendance, \
    ExaminationResult
from apps.school.models.school import Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger


class ExaminationLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school
        student_id = request.query_params.get("student_id")

        if not school:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not student_id:
            return CustomResponse.errorResponse(
                description="Student ID is required."
            )

        try:
            # -----------------------------------------
            # Validate student ID
            # -----------------------------------------
            try:
                student_uuid = uuid.UUID(str(student_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid student ID."
                )

            # -----------------------------------------
            # Get student
            # -----------------------------------------
            student = Student.objects.filter(
                id=student_uuid,
                school=school,
            ).select_related(
                "grade",
                "section",
                "branch",
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            if not student.grade_id:
                return CustomResponse.errorResponse(
                    description="Student grade not found."
                )

            # -----------------------------------------
            # Get examinations
            # -----------------------------------------
            examinations = Examination.objects.filter(
                school=school,
                examination_grades__grade_id=student.grade_id,
                status__in=[
                    Examination.Status.SCHEDULED,
                    Examination.Status.COMPLETED,
                ],
            ).select_related(
                "examination_type",
                "academic_year",
                "branch",
            ).distinct().order_by(
                "-start_date",
                "-created_at",
            )

            # -----------------------------------------
            # Total before pagination
            # -----------------------------------------
            total = examinations.count()

            # -----------------------------------------
            # Pagination
            # -----------------------------------------
            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                examinations,
                request,
            )

            page_records = list(page)

            # -----------------------------------------
            # Response
            # -----------------------------------------
            data = []

            for examination in page_records:

                data.append({
                    "id": str(examination.id),

                    "name": examination.name,

                    "examination_type": {
                        "id": str(
                            examination.examination_type.id
                        ),
                        "name": examination.examination_type.name,
                    } if examination.examination_type else None,

                    "academic_year": {
                        "id": str(
                            examination.academic_year.id
                        ),
                        "name": str(
                            examination.academic_year
                        ),
                    } if examination.academic_year else None,

                    "branch": {
                        "id": str(
                            examination.branch.id
                        ),
                        "name": examination.branch.name,
                    } if examination.branch else None,

                    "start_date": str(
                        examination.start_date
                    ),

                    "end_date": str(
                        examination.end_date
                    ),

                    "result_date": str(
                        examination.result_date
                    ),

                    "reporting_date": (
                        str(examination.reporting_date)
                        if examination.reporting_date
                        else None
                    ),

                    "status": examination.status,

                    "description": examination.description,
                })

            application_logger.info(
                "app_examination_list_fetched",
                school_id=str(school.id),
                student_id=str(student.id),
                requested_by=str(request.user.id),
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Examinations fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_examination_list_failed",
                school_id=str(school.id),
                student_id=str(student_id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch examinations."
            )


class ExaminationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        examination_id = request.query_params.get("examination_id")
        student_id = request.query_params.get("student_id")

        if not examination_id:
            return CustomResponse.errorResponse(
                description="Examination ID is required."
            )

        try:
            examination_uuid = uuid.UUID(str(examination_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid examination ID."
            )

        try:
            # -----------------------------------------
            # Get logged-in student
            # -----------------------------------------
            student = Student.objects.filter(
                id=student_id,
                school=school,
            ).select_related(
                "grade",
                "section",
                "branch",
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            if not student.grade_id:
                return CustomResponse.errorResponse(
                    description="Student grade not found."
                )

            # -----------------------------------------
            # Get examination
            # -----------------------------------------
            examination = Examination.objects.filter(
                id=examination_uuid,
                school=school,
                examination_grades__grade_id=student.grade_id,
            ).select_related(
                "examination_type",
                "school",
                "academic_year",
                "branch",
            ).first()

            if not examination:
                return CustomResponse.errorResponse(
                    description="Examination not found."
                )

            # -----------------------------------------
            # Get schedules for student's grade
            # -----------------------------------------
            schedules = ExaminationSchedule.objects.filter(
                examination=examination,
                grade_id=student.grade_id,
            ).select_related(
                "grade",
                "subject",
            ).order_by(
                "exam_date",
                "start_time",
            )

            # -----------------------------------------
            # Build schedule response
            # -----------------------------------------
            schedule_data = []

            for schedule in schedules:

                schedule_data.append({
                    "id": str(schedule.id),

                    "subject": {
                        "id": str(schedule.subject_id),
                        "name": schedule.subject.name,
                    },

                    "grade": {
                        "id": str(schedule.grade_id),
                        "name": schedule.grade.name,
                    },

                    "exam_date": str(
                        schedule.exam_date
                    ),

                    "start_time": str(
                        schedule.start_time
                    ),

                    "end_time": str(
                        schedule.end_time
                    ),

                    "room_number": schedule.room_number,

                    "maximum_marks": str(
                        schedule.maximum_marks
                    ),

                    "passing_marks": str(
                        schedule.passing_marks
                    ),

                    "internal_percentage": str(
                        schedule.internal_percentage
                    ),

                    "external_percentage": str(
                        schedule.external_percentage
                    ),

                    "practical_percentage": str(
                        schedule.practical_percentage
                    ),

                    "instructions": schedule.instructions,
                })

            # -----------------------------------------
            # Response
            # -----------------------------------------
            data = {
                "id": str(examination.id),

                "name": examination.name,
                "school": {
                    "id":str(examination.school_id),
                    "name": examination.school.name,
                    "phone_number": examination.school.phone_number,
                },

                "examination_type": {
                    "id": str(
                        examination.examination_type.id
                    ),
                    "name": examination.examination_type.name,
                } if examination.examination_type else None,

                "academic_year": {
                    "id": str(
                        examination.academic_year.id
                    ),
                    "name": str(
                        examination.academic_year.name
                    ),
                } if examination.academic_year else None,

                "start_date": str(
                    examination.start_date
                ),

                "end_date": str(
                    examination.end_date
                ),

                "result_date": str(
                    examination.result_date
                ),

                "reporting_date": (
                    str(examination.reporting_date)
                    if examination.reporting_date
                    else None
                ),

                "status": examination.status,

                "description": examination.description,

                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "admission_number": student.admission_number,
                    "grade": {
                        "id": str(student.grade_id),
                        "name": student.grade.name,
                    },
                    "section": {
                        "id": str(student.section_id),
                        "name": student.section.name,
                    } if student.section_id else None,
                },

                "schedules": schedule_data,
            }

            application_logger.info(
                "app_examination_detail_fetched",
                school_id=str(school.id),
                examination_id=str(examination.id),
                student_id=str(student.id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=data,
                description="Examination details fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_examination_detail_failed",
                school_id=str(school.id),
                examination_id=str(examination_id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch examination details."
            )

class UpcomingExaminationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school
        student_id = request.query_params.get("student_id")

        if not school:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not student_id:
            return CustomResponse.errorResponse(
                description="Student ID is required."
            )

        try:
            student_uuid = uuid.UUID(str(student_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid student ID."
            )

        try:
            # -----------------------------------------
            # Get student
            # -----------------------------------------
            student = Student.objects.filter(
                id=student_uuid,
                school=school,
            ).select_related(
                "grade",
                "section",
                "branch",
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            if not student.grade_id:
                return CustomResponse.errorResponse(
                    description="Student grade not found."
                )

            # -----------------------------------------
            # Get upcoming schedules
            # -----------------------------------------
            today = timezone.localdate()

            schedules = ExaminationSchedule.objects.filter(
                examination__school=school,
                examination__examination_grades__grade_id=student.grade_id,
                examination__status=Examination.Status.SCHEDULED,
                grade_id=student.grade_id,
                exam_date__gte=today,
            ).select_related(
                "examination",
                "examination__examination_type",
                "subject",
                "grade",
            ).distinct().order_by(
                "exam_date",
                "start_time",
            )

            # -----------------------------------------
            # Total before pagination
            # -----------------------------------------
            total = schedules.count()

            # -----------------------------------------
            # Pagination
            # -----------------------------------------
            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                schedules,
                request,
            )

            page_records = list(page)

            # -----------------------------------------
            # Response
            # -----------------------------------------
            data = []

            for schedule in page_records:

                data.append({
                    "id": str(schedule.id),

                    "examination": {
                        "id": str(
                            schedule.examination_id
                        ),
                        "name": schedule.examination.name,
                        "examination_type": {
                            "id": str(
                                schedule.examination.examination_type_id
                            ),
                            "name": schedule.examination.examination_type.name,
                        } if schedule.examination.examination_type else None,
                    },

                    "subject": {
                        "id": str(schedule.subject_id),
                        "name": schedule.subject.name,
                    },

                    "grade": {
                        "id": str(schedule.grade_id),
                        "name": schedule.grade.name,
                    },

                    "exam_date": str(
                        schedule.exam_date
                    ),

                    "start_time": str(
                        schedule.start_time
                    ),

                    "end_time": str(
                        schedule.end_time
                    ),

                    "room_number": schedule.room_number,

                    "maximum_marks": str(
                        schedule.maximum_marks
                    ),

                    "passing_marks": str(
                        schedule.passing_marks
                    ),

                    "instructions": schedule.instructions,
                })

            application_logger.info(
                "app_upcoming_examination_fetched",
                school_id=str(school.id),
                student_id=str(student.id),
                requested_by=str(request.user.id),
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Upcoming examinations fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_upcoming_examination_failed",
                school_id=str(school.id),
                student_id=str(student_id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch upcoming examinations."
            )


class ExaminationResultLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school
        student_id = request.query_params.get("student_id")

        if not school:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not student_id:
            return CustomResponse.errorResponse(
                description="Student ID is required."
            )

        try:
            student_uuid = uuid.UUID(str(student_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid student ID."
            )

        try:
            # -----------------------------------------
            # Get student
            # -----------------------------------------
            student = Student.objects.filter(
                id=student_uuid,
                school=school,
            ).select_related(
                "grade",
                "section",
                "branch",
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            # -----------------------------------------
            # Get published report cards
            # -----------------------------------------
            report_cards = ReportCard.objects.filter(
                examination__school=school,
                student=student,
                status=ReportCard.Status.PUBLISHED,
            ).select_related(
                "examination",
                "examination__examination_type",
                "examination__academic_year",
            ).order_by(
                "-examination__start_date",
                "-created_at",
            )

            # -----------------------------------------
            # Total before pagination
            # -----------------------------------------
            total = report_cards.count()

            # -----------------------------------------
            # Pagination
            # -----------------------------------------
            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                report_cards,
                request,
            )

            page_records = list(page)

            # -----------------------------------------
            # Response
            # -----------------------------------------
            data = []

            for report_card in page_records:

                data.append({
                    "id": str(report_card.id),

                    "examination": {
                        "id": str(
                            report_card.examination_id
                        ),
                        "name": report_card.examination.name,

                        "examination_type": {
                            "id": str(
                                report_card.examination.examination_type_id
                            ),
                            "name": (
                                report_card
                                .examination
                                .examination_type
                                .name
                            ),
                        } if report_card.examination.examination_type else None,

                        "start_date": str(
                            report_card.examination.start_date
                        ),

                        "end_date": str(
                            report_card.examination.end_date
                        ),
                    },

                    "academic_year": {
                        "id": str(
                            report_card
                            .examination
                            .academic_year_id
                        ),
                        "name": str(
                            report_card
                            .examination
                            .academic_year
                        ),
                    } if report_card.examination.academic_year else None,

                    "total_marks": str(
                        report_card.total_marks
                    ),

                    "obtained_marks": str(
                        report_card.obtained_marks
                    ),

                    "percentage": str(
                        report_card.percentage
                    ),

                    "grade": report_card.grade,

                    "grade_point": (
                        str(report_card.grade_point)
                        if report_card.grade_point is not None
                        else None
                    ),

                    "result": report_card.result,

                    "teacher_remarks": report_card.teacher_remarks,

                    "published_at": (
                        report_card.published_at.isoformat()
                        if report_card.published_at
                        else None
                    ),
                })

            application_logger.info(
                "app_examination_result_list_fetched",
                school_id=str(school.id),
                student_id=str(student.id),
                requested_by=str(request.user.id),
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Examination results fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_examination_result_list_failed",
                school_id=str(school.id),
                student_id=str(student_id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch examination results."
            )

class ExaminationResultDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school
        student_id = request.query_params.get("student_id")
        examination_id = request.query_params.get("examination_id")

        if not school:
            return CustomResponse.errorResponse(
                description="School not found."
            )

        if not student_id:
            return CustomResponse.errorResponse(
                description="Student ID is required."
            )

        if not examination_id:
            return CustomResponse.errorResponse(
                description="Examination ID is required."
            )

        try:
            student_uuid = uuid.UUID(str(student_id))
            examination_uuid = uuid.UUID(str(examination_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid student ID or examination ID."
            )

        try:
            # -----------------------------------------
            # Get student
            # -----------------------------------------
            student = Student.objects.filter(
                id=student_uuid,
                school=school,
            ).select_related(
                "grade",
                "section",
                "branch",
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            if not student.grade_id:
                return CustomResponse.errorResponse(
                    description="Student grade not found."
                )

            # -----------------------------------------
            # Get published report card
            # -----------------------------------------
            report_card = ReportCard.objects.filter(
                examination_id=examination_uuid,
                student=student,
                examination__school=school,
                examination__examination_grades__grade_id=student.grade_id,
                status=ReportCard.Status.PUBLISHED,
            ).select_related(
                "examination",
                "examination__examination_type",
                "examination__academic_year",
            ).first()

            if not report_card:
                return CustomResponse.errorResponse(
                    description="Examination result not found."
                )

            # -----------------------------------------
            # Get subject-wise results
            # -----------------------------------------
            results = ExaminationResult.objects.filter(
                examination=report_card.examination,
                student=student,
                examination_schedule__grade_id=student.grade_id,
                status=ExaminationResult.Status.PUBLISHED,
            ).select_related(
                "examination_schedule",
                "examination_schedule__subject",
            ).order_by(
                "examination_schedule__exam_date",
                "examination_schedule__start_time",
            )

            subject_results = []

            for result in results:
                schedule = result.examination_schedule

                subject_results.append({
                    "id": str(result.id),

                    "subject": {
                        "id": str(schedule.subject_id),
                        "name": schedule.subject.name,
                    },

                    "exam_date": str(
                        schedule.exam_date
                    ),

                    "maximum_marks": str(
                        schedule.maximum_marks
                    ),

                    "passing_marks": str(
                        schedule.passing_marks
                    ),

                    "internal_marks": str(
                        result.internal_marks
                    ),

                    "external_marks": str(
                        result.external_marks
                    ),

                    "practical_marks": str(
                        result.practical_marks
                    ),

                    "marks_obtained": str(
                        result.marks_obtained
                    ),

                    "grade": result.grade,

                    "grade_point": (
                        str(result.grade_point)
                        if result.grade_point is not None
                        else None
                    ),

                    "remarks": result.remarks,
                })

            # -----------------------------------------
            # Response
            # -----------------------------------------
            data = {
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "admission_number": student.admission_number,

                    "grade": {
                        "id": str(student.grade_id),
                        "name": student.grade.name,
                    },

                    "section": {
                        "id": str(student.section_id),
                        "name": student.section.name,
                    } if student.section_id else None,
                },

                "examination": {
                    "id": str(
                        report_card.examination_id
                    ),

                    "name": report_card.examination.name,

                    "examination_type": {
                        "id": str(
                            report_card
                            .examination
                            .examination_type_id
                        ),
                        "name": (
                            report_card
                            .examination
                            .examination_type
                            .name
                        ),
                    } if report_card.examination.examination_type else None,

                    "academic_year": {
                        "id": str(
                            report_card
                            .examination
                            .academic_year_id
                        ),
                        "name": str(
                            report_card
                            .examination
                            .academic_year
                        ),
                    } if report_card.examination.academic_year else None,

                    "start_date": str(
                        report_card.examination.start_date
                    ),

                    "end_date": str(
                        report_card.examination.end_date
                    ),

                    "result_date": str(
                        report_card.examination.result_date
                    ),
                },

                "summary": {
                    "total_marks": str(
                        report_card.total_marks
                    ),

                    "obtained_marks": str(
                        report_card.obtained_marks
                    ),

                    "percentage": str(
                        report_card.percentage
                    ),

                    "grade": report_card.grade,

                    "grade_point": (
                        str(report_card.grade_point)
                        if report_card.grade_point is not None
                        else None
                    ),

                    "result": report_card.result,

                    "teacher_remarks": report_card.teacher_remarks,
                },

                "subjects": subject_results,
            }

            application_logger.info(
                "app_examination_result_detail_fetched",
                school_id=str(school.id),
                student_id=str(student.id),
                examination_id=str(
                    report_card.examination_id
                ),
                requested_by=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=data,
                description="Examination result fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_examination_result_detail_failed",
                school_id=str(school.id),
                student_id=str(student_id),
                examination_id=str(examination_id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch examination result."
            )

class HallTicketDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        student_id = request.query_params.get("student_id")
        examination_id = request.query_params.get("examination_id")

        # ----------------------------------------------------------
        # REQUEST LOG
        # ----------------------------------------------------------

        application_logger.info(
            "app_hall_ticket_fetch_requested",
            school_id=str(school.id) if school else None,
            student_id=str(student_id) if student_id else None,
            examination_id=str(examination_id) if examination_id else None,
            requested_by=str(request.user.id),
        )

        # ----------------------------------------------------------
        # SCHOOL VALIDATION
        # ----------------------------------------------------------

        if not school:
            application_logger.warning(
                "app_hall_ticket_fetch_failed_school_not_found",
                student_id=str(student_id) if student_id else None,
                examination_id=str(examination_id)
                if examination_id
                else None,
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="School not found."
            )

        # ----------------------------------------------------------
        # REQUEST VALIDATION
        # ----------------------------------------------------------

        if not student_id:
            application_logger.warning(
                "app_hall_ticket_fetch_failed_student_id_missing",
                school_id=str(school.id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Student ID is required."
            )

        if not examination_id:
            application_logger.warning(
                "app_hall_ticket_fetch_failed_examination_id_missing",
                school_id=str(school.id),
                student_id=str(student_id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Examination ID is required."
            )

        # ----------------------------------------------------------
        # UUID VALIDATION
        # ----------------------------------------------------------

        try:
            student_uuid = uuid.UUID(str(student_id))
            examination_uuid = uuid.UUID(str(examination_id))

        except (ValueError, TypeError, AttributeError):
            application_logger.warning(
                "app_hall_ticket_fetch_failed_invalid_uuid",
                school_id=str(school.id),
                student_id=str(student_id),
                examination_id=str(examination_id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Invalid student ID or examination ID."
            )

        try:
            # ------------------------------------------------------
            # GET STUDENT
            # ------------------------------------------------------

            student = (
                Student.objects
                .filter(
                    id=student_uuid,
                    school=school,
                )
                .select_related(
                    "grade",
                    "section",
                    "branch",
                )
                .first()
            )

            if not student:
                application_logger.warning(
                    "app_hall_ticket_fetch_failed_student_not_found",
                    school_id=str(school.id),
                    student_id=str(student_uuid),
                    examination_id=str(examination_uuid),
                    requested_by=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            if not student.grade_id:
                application_logger.warning(
                    "app_hall_ticket_fetch_failed_student_grade_missing",
                    school_id=str(school.id),
                    student_id=str(student.id),
                    examination_id=str(examination_uuid),
                    requested_by=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="Student grade not found."
                )

            # ------------------------------------------------------
            # GET HALL TICKET
            # ------------------------------------------------------

            hall_ticket = (
                HallTicket.objects
                .filter(
                    student=student,
                    examination_id=examination_uuid,
                    examination__school=school,
                    examination__examination_grades__grade_id=(
                        student.grade_id
                    ),
                    status=HallTicket.Status.PUBLISHED,
                )
                .select_related(
                    "examination",
                    "examination__school",
                    "examination__examination_type",
                    "examination__academic_year",
                )
                .first()
            )

            if not hall_ticket:
                application_logger.warning(
                    "app_hall_ticket_fetch_failed_hall_ticket_not_found",
                    school_id=str(school.id),
                    student_id=str(student.id),
                    examination_id=str(examination_uuid),
                    requested_by=str(request.user.id),
                )

                return CustomResponse.errorResponse(
                    description="Hall ticket not found."
                )

            # ------------------------------------------------------
            # GET EXAMINATION SCHEDULES
            # ------------------------------------------------------

            schedules = (
                ExaminationSchedule.objects
                .filter(
                    examination=hall_ticket.examination,
                    grade_id=student.grade_id,
                )
                .select_related(
                    "subject",
                    "grade",
                )
                .order_by(
                    "exam_date",
                    "start_time",
                )
            )

            schedule_data = []

            for schedule in schedules:
                schedule_data.append({
                    "id": str(schedule.id),

                    "subject": {
                        "id": str(schedule.subject_id),
                        "name": schedule.subject.name,
                    },

                    "exam_date": str(
                        schedule.exam_date
                    ),

                    "start_time": str(
                        schedule.start_time
                    ),

                    "end_time": str(
                        schedule.end_time
                    ),

                    "room_number": schedule.room_number,

                    "maximum_marks": str(
                        schedule.maximum_marks
                    ),

                    "passing_marks": str(
                        schedule.passing_marks
                    ),

                    "instructions": schedule.instructions,
                    "pdf": schedule.pdf,
                })

            # ------------------------------------------------------
            # RESPONSE DATA
            # ------------------------------------------------------

            data = {
                "hall_ticket": {
                    "id": str(hall_ticket.id),

                    "hall_ticket_number": (
                        hall_ticket.hall_ticket_number
                    ),

                    "school": {
                        "id": str(school.id),
                        "name": school.name,
                        "address": school.address,
                        "board": school.board,
                    },

                    "status": hall_ticket.status,

                    "generated_at": (
                        hall_ticket.generated_at.isoformat()
                        if hall_ticket.generated_at
                        else None
                    ),

                    "published_at": (
                        hall_ticket.published_at.isoformat()
                        if hall_ticket.published_at
                        else None
                    ),
                },

                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "admission_number": (
                        student.admission_number
                    ),

                    "grade": {
                        "id": str(student.grade_id),
                        "name": student.grade.name,
                    },

                    "section": {
                        "id": str(student.section_id),
                        "name": student.section.name,
                    }
                    if student.section_id
                    else None,

                    "branch": {
                        "id": str(student.branch_id),
                        "name": student.branch.name,
                    }
                    if student.branch_id
                    else None,
                },

                "examination": {
                    "id": str(
                        hall_ticket.examination_id
                    ),

                    "name": (
                        hall_ticket.examination.name
                    ),

                    "examination_type": {
                        "id": str(
                            hall_ticket
                            .examination
                            .examination_type_id
                        ),

                        "name": (
                            hall_ticket
                            .examination
                            .examination_type
                            .name
                        ),
                    }
                    if hall_ticket.examination.examination_type
                    else None,

                    "academic_year": {
                        "id": str(
                            hall_ticket
                            .examination
                            .academic_year_id
                        ),

                        "name": str(
                            hall_ticket
                            .examination
                            .academic_year
                        ),
                    }
                    if hall_ticket.examination.academic_year
                    else None,

                    "start_date": str(
                        hall_ticket.examination.start_date
                    ),

                    "end_date": str(
                        hall_ticket.examination.end_date
                    ),

                    "result_date": str(
                        hall_ticket.examination.result_date
                    ),

                    "reporting_date": (
                        str(
                            hall_ticket
                            .examination
                            .reporting_date
                        )
                        if hall_ticket
                        .examination
                        .reporting_date
                        else None
                    ),
                },

                "schedules": schedule_data,
            }

            # ------------------------------------------------------
            # SUCCESS LOG
            # ------------------------------------------------------

            application_logger.info(
                "app_hall_ticket_fetched",
                school_id=str(school.id),
                student_id=str(student.id),
                examination_id=str(
                    hall_ticket.examination_id
                ),
                hall_ticket_id=str(hall_ticket.id),
                schedule_count=len(schedule_data),
                requested_by=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=data,
                description="Hall ticket fetched successfully.",
            )

        except Exception:
            # ------------------------------------------------------
            # EXCEPTION LOG
            # ------------------------------------------------------

            application_logger.exception(
                "app_hall_ticket_fetch_failed",
                school_id=str(school.id),
                student_id=str(student_id),
                examination_id=str(examination_id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch hall ticket."
            )


class ExaminationAttendanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            school = request.school

            student_id = request.query_params.get("student_id")
            examination_id = request.query_params.get("examination_id")

            if not student_id:
                return CustomResponse.errorResponse(
                    message="student_id is required."
                )

            if not examination_id:
                return CustomResponse.errorResponse(
                    message="examination_id is required."
                )

            try:
                student_uuid = uuid.UUID(student_id)
                examination_uuid = uuid.UUID(examination_id)
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid student_id or examination_id."
                )

            student = (
                Student.objects
                .select_related("grade", "section", "branch")
                .filter(
                    id=student_uuid,
                    school=school,
                )
                .first()
            )

            if not student:
                return CustomResponse.errorResponse(
                    message="Student not found."
                )

            if not student.grade_id:
                return CustomResponse.errorResponse(
                    message="Student grade is not assigned."
                )

            examination = (
                Examination.objects
                .select_related(
                    "examination_type",
                    "academic_year",
                    "branch",
                )
                .filter(
                    id=examination_uuid,
                    school=school,
                    examination_grades__grade_id=student.grade_id,
                )
                .first()
            )

            if not examination:
                return CustomResponse.errorResponse(
                    message="Examination not found."
                )

            attendance_records = (
                ExaminationAttendance.objects
                .filter(
                    examination=examination,
                    student=student,
                )
                .select_related(
                    "examination_schedule",
                    "examination_schedule__subject",
                    "examination_schedule__grade",
                )
                .order_by(
                    "examination_schedule__exam_date",
                    "examination_schedule__start_time",
                )
            )

            attendance_data = []

            for attendance in attendance_records:
                schedule = attendance.examination_schedule
                subject = schedule.subject

                attendance_data.append({
                    "attendance_id": str(attendance.id),

                    "subject": {
                        "id": str(subject.id),
                        "name": subject.name,
                    },

                    "exam_date": schedule.exam_date,
                    "start_time": schedule.start_time,
                    "end_time": schedule.end_time,
                    "room_number": schedule.room_number,

                    "status": attendance.status,
                    "attendance_time": attendance.attendance_time,
                    "remarks": attendance.remarks,
                })

            data = {
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "admission_number": student.admission_number,
                    "grade": (
                        student.grade.name
                        if student.grade
                        else None
                    ),
                    "section": (
                        student.section.name
                        if student.section
                        else None
                    ),
                },

                "examination": {
                    "id": str(examination.id),
                    "name": examination.name,
                    "examination_type": (
                        examination.examination_type.name
                        if examination.examination_type
                        else None
                    ),
                    "academic_year": (
                        examination.academic_year.name
                        if examination.academic_year
                        else None
                    ),
                    "start_date": examination.start_date,
                    "end_date": examination.end_date,
                    "status": examination.status,
                },

                "attendance": attendance_data,
            }

            application_logger.info(
                "app_examination_attendance_fetched",
                extra={
                    "school_id": str(school.id),
                    "student_id": str(student.id),
                    "examination_id": str(examination.id),
                },
            )

            return CustomResponse.successResponse(
                data=data,
                message="Examination attendance fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_examination_attendance_fetch_failed",
                extra={
                    "school_id": str(request.school.id)
                    if getattr(request, "school", None)
                    else None,
                },
            )

            return CustomResponse.errorResponse(
                message="Something went wrong."
            )

class ReportCardDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            school = request.school

            student_id = request.query_params.get("student_id")
            examination_id = request.query_params.get("examination_id")

            if not student_id:
                return CustomResponse.errorResponse(
                    message="student_id is required."
                )

            if not examination_id:
                return CustomResponse.errorResponse(
                    message="examination_id is required."
                )

            try:
                student_uuid = uuid.UUID(student_id)
                examination_uuid = uuid.UUID(examination_id)
            except ValueError:
                return CustomResponse.errorResponse(
                    message="Invalid student_id or examination_id."
                )

            student = (
                Student.objects
                .select_related("grade", "section", "branch")
                .filter(
                    id=student_uuid,
                    school=school,
                )
                .first()
            )

            if not student:
                return CustomResponse.errorResponse(
                    message="Student not found."
                )

            if not student.grade_id:
                return CustomResponse.errorResponse(
                    message="Student grade is not assigned."
                )

            report_card = (
                ReportCard.objects
                .select_related(
                    "examination",
                    "examination__examination_type",
                    "examination__academic_year",
                )
                .filter(
                    examination_id=examination_uuid,
                    examination__school=school,
                    examination__examination_grades__grade_id=student.grade_id,
                    student=student,
                    status=ReportCard.Status.PUBLISHED,
                )
                .first()
            )

            if not report_card:
                return CustomResponse.errorResponse(
                    message="Published report card not found."
                )

            results = (
                ExaminationResult.objects
                .filter(
                    examination=report_card.examination,
                    student=student,
                    examination_schedule__grade_id=student.grade_id,
                    status=ExaminationResult.Status.PUBLISHED,
                )
                .select_related(
                    "examination_schedule",
                    "examination_schedule__subject",
                )
                .order_by(
                    "examination_schedule__exam_date",
                    "examination_schedule__start_time",
                )
            )

            subjects = []

            for result in results:
                schedule = result.examination_schedule
                subject = schedule.subject

                subjects.append({
                    "result_id": str(result.id),

                    "subject": {
                        "id": str(subject.id),
                        "name": subject.name,
                    },

                    "exam_date": schedule.exam_date,
                    "maximum_marks": schedule.maximum_marks,
                    "passing_marks": schedule.passing_marks,

                    "marks": {
                        "internal_marks": result.internal_marks,
                        "external_marks": result.external_marks,
                        "practical_marks": result.practical_marks,
                        "marks_obtained": result.marks_obtained,
                    },

                    "grade": result.grade,
                    "grade_point": result.grade_point,
                    "remarks": result.remarks,
                })

            data = {
                "report_card": {
                    "id": str(report_card.id),
                    "status": report_card.status,
                    "total_marks": report_card.total_marks,
                    "obtained_marks": report_card.obtained_marks,
                    "percentage": report_card.percentage,
                    "grade": report_card.grade,
                    "grade_point": report_card.grade_point,
                    "result": report_card.result,
                    "teacher_remarks": report_card.teacher_remarks,
                    "published_at": report_card.published_at,
                    "pdf": report_card.pdf,
                },

                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "admission_number": student.admission_number,
                    "grade": (
                        student.grade.name
                        if student.grade
                        else None
                    ),
                    "section": (
                        student.section.name
                        if student.section
                        else None
                    ),
                },

                "examination": {
                    "id": str(report_card.examination.id),
                    "name": report_card.examination.name,
                    "examination_type": (
                        report_card.examination.examination_type.name
                        if report_card.examination.examination_type
                        else None
                    ),
                    "academic_year": (
                        report_card.examination.academic_year.name
                        if report_card.examination.academic_year
                        else None
                    ),
                    "start_date": report_card.examination.start_date,
                    "end_date": report_card.examination.end_date,
                    "result_date": report_card.examination.result_date,
                },

                "subjects": subjects,
            }

            application_logger.info(
                "app_report_card_detail_fetched",
                extra={
                    "school_id": str(school.id),
                    "student_id": str(student.id),
                    "examination_id": str(
                        report_card.examination.id
                    ),
                },
            )

            return CustomResponse.successResponse(
                data=data,
                message="Report card fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_report_card_detail_fetch_failed",
                extra={
                    "school_id": str(request.school.id)
                    if getattr(request, "school", None)
                    else None,
                },
            )

            return CustomResponse.errorResponse(
                message="Something went wrong."
            )
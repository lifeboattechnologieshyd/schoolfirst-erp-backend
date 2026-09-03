from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ptm.models import ParentTeacherMeeting, ParentTeacherMeetingResponse, ParentTeacherMeetingSection, \
    ParentTeacherMeetingStaff
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class StudentPTMListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        student_id = request.query_params.get("student_id")

        application_logger.info(
            "student_ptm_list_started",
            user_id=str(user.id),
            student_id=str(student_id) if student_id else None,
        )

        try:

            if not student_id:

                application_logger.warning(
                    "student_ptm_list_failed",
                    user_id=str(user.id),
                    reason="student_id_required",
                )

                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            student = Student.objects.select_related(
                "school",
                "branch",
                "academic_year",
                "grade",
                "section",
                "section__class_teacher",
            ).filter(
                id=student_id,
                status=Student.Status.ACTIVE,
            ).first()

            if student is None:

                application_logger.warning(
                    "student_ptm_list_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    reason="student_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            application_logger.info(
                "student_ptm_list_student_found",
                user_id=str(user.id),
                student_id=str(student.id),
                school_id=str(student.school_id),
                branch_id=str(student.branch_id) if student.branch_id else None,
                academic_year_id=str(student.academic_year_id),
                grade_id=str(student.grade_id),
                section_id=str(student.section_id),
            )

            meetings = ParentTeacherMeeting.objects.select_related(
                "academic_year",
                "branch",
                "grade",
            ).prefetch_related(
                Prefetch(
                    "meeting_sections",
                    queryset=ParentTeacherMeetingSection.objects.select_related(
                        "section",
                    ),
                ),
                Prefetch(
                    "meeting_staffs",
                    queryset=ParentTeacherMeetingStaff.objects.select_related(
                        "staff",
                    ),
                ),
            ).filter(
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                meeting_sections__section_id=student.section_id,
            )

            if student.branch_id:

                meetings = meetings.filter(
                    branch_id=student.branch_id,
                )

            else:

                meetings = meetings.filter(
                    branch__isnull=True,
                )

            meetings = meetings.exclude(
                status=ParentTeacherMeeting.Status.DRAFT,
            ).distinct().order_by(
                "-meeting_date",
                "-start_time",
            )

            responses = ParentTeacherMeetingResponse.objects.filter(
                meeting__in=meetings,
                student_id=student.id,
            )

            response_map = {
                response.meeting_id: response
                for response in responses
            }

            data = []

            for meeting in meetings:

                response = response_map.get(meeting.id)

                data.append({
                    "id": str(meeting.id),
                    "title": meeting.title,
                    "description": meeting.description,
                    "meeting_type": meeting.meeting_type,
                    "meeting_date": meeting.meeting_date,
                    "start_time": meeting.start_time,
                    "end_time": meeting.end_time,
                    "meeting_mode": meeting.meeting_mode,
                    "location": meeting.location,
                    "meeting_link": meeting.meeting_link,
                    "status": meeting.status,
                    "academic_year": {
                        "id": str(meeting.academic_year.id),
                        "name": meeting.academic_year.name,
                    },
                    "branch": {
                        "id": str(meeting.branch.id),
                        "name": meeting.branch.name,
                    } if meeting.branch else None,
                    "grade": {
                        "id": str(meeting.grade.id),
                        "name": meeting.grade.name,
                    },
                    "section": {
                        "id": str(student.section.id),
                        "name": student.section.name,
                    },
                    "staffs": [
                        {
                            "id": str(item.staff.id),
                            "name": item.staff.name,
                            "staff_type": item.staff.get_staff_type_display(),
                            "profile_image": item.staff.profile_image,
                            "is_host": (
                                    item.responsibility ==
                                    ParentTeacherMeetingStaff.Responsibility.HOST
                            ),
                        }
                        for item in meeting.meeting_staffs.all()
                    ],
                    "response": {
                        "response_status": (
                            response.response_status
                            if response
                            else ParentTeacherMeetingResponse.ResponseStatus.PENDING
                        ),
                        "responded_at": (
                            response.responded_at
                            if response
                            else None
                        ),
                        "remarks": (
                            response.remarks
                            if response
                            else None
                        ),
                    },
                })

            application_logger.info(
                "student_ptm_list_fetched",
                user_id=str(user.id),
                student_id=str(student.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Parent teacher meetings fetched successfully.",
                total=len(data),
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "admission_number": student.admission_number,
                        "class_teacher": (
                            {
                                "id": str(student.section.class_teacher.id),
                                "name": student.section.class_teacher.name,
                            }
                            if student.section.class_teacher
                            else None

                        ),
                    },
                    "meetings": data,
                },
            )

        except Exception:

            application_logger.exception(
                "student_ptm_list_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching parent teacher meetings."
            )


class StudentPTMResponseAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, meeting_id):

        user = request.user
        student_id = request.data.get("student_id")
        response_status = request.data.get("response_status")
        remarks = request.data.get("remarks")

        application_logger.info(
            "student_ptm_response_started",
            user_id=str(user.id),
            student_id=str(student_id) if student_id else None,
            meeting_id=str(meeting_id),
            response_status=response_status,
        )

        try:

            if not student_id:

                application_logger.warning(
                    "student_ptm_response_failed",
                    reason="student_id_required",
                    user_id=str(user.id),
                    meeting_id=str(meeting_id),
                )

                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            allowed_responses = [
                ParentTeacherMeetingResponse.ResponseStatus.ATTENDING,
                ParentTeacherMeetingResponse.ResponseStatus.NOT_ATTENDING,
            ]

            if response_status not in allowed_responses:

                application_logger.warning(
                    "student_ptm_response_failed",
                    reason="invalid_response_status",
                    user_id=str(user.id),
                    meeting_id=str(meeting_id),
                    student_id=str(student_id),
                    response_status=response_status,
                )

                return CustomResponse.errorResponse(
                    description="Invalid response status."
                )

            student = Student.objects.select_related(
                "school",
                "branch",
                "academic_year",
                "grade",
                "section",
            ).filter(
                id=student_id,
                status=Student.Status.ACTIVE,
            ).first()

            if student is None:

                application_logger.warning(
                    "student_ptm_response_failed",
                    reason="student_not_found",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    meeting_id=str(meeting_id),
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            application_logger.info(
                "student_ptm_response_student_found",
                user_id=str(user.id),
                student_id=str(student.id),
                meeting_id=str(meeting_id),
                school_id=str(student.school_id),
                branch_id=str(student.branch_id) if student.branch_id else None,
                academic_year_id=str(student.academic_year_id),
                grade_id=str(student.grade_id),
                section_id=str(student.section_id),
            )

            meetings = ParentTeacherMeeting.objects.filter(
                id=meeting_id,
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                meeting_sections__section_id=student.section_id,
            )

            if student.branch_id:

                meetings = meetings.filter(
                    branch_id=student.branch_id,
                )

            else:

                meetings = meetings.filter(
                    branch__isnull=True,
                )

            meeting = meetings.exclude(
                status__in=[
                    ParentTeacherMeeting.Status.DRAFT,
                    ParentTeacherMeeting.Status.COMPLETED,
                    ParentTeacherMeeting.Status.CANCELLED,
                ],
            ).distinct().first()

            if meeting is None:

                application_logger.warning(
                    "student_ptm_response_failed",
                    reason="meeting_not_found_or_student_not_eligible",
                    user_id=str(user.id),
                    meeting_id=str(meeting_id),
                    student_id=str(student.id),
                    school_id=str(student.school_id),
                    branch_id=str(student.branch_id) if student.branch_id else None,
                    grade_id=str(student.grade_id),
                    section_id=str(student.section_id),
                )

                return CustomResponse.errorResponse(
                    description="Parent teacher meeting not found."
                )

            with transaction.atomic():

                response, created = ParentTeacherMeetingResponse.objects.update_or_create(
                    meeting=meeting,
                    student=student,
                    defaults={
                        "response_status": response_status,
                        "responded_at": timezone.now(),
                        "remarks": remarks,
                    },
                )

            application_logger.info(
                "student_ptm_response_submitted",
                user_id=str(user.id),
                meeting_id=str(meeting.id),
                student_id=str(student.id),
                response_id=str(response.id),
                response_status=response.response_status,
                created=created,
            )

            return CustomResponse.successResponse(
                description="Parent teacher meeting response submitted successfully.",
                data={
                    "id": str(response.id),
                    "meeting_id": str(meeting.id),
                    "student_id": str(student.id),
                    "response_status": response.response_status,
                    "responded_at": response.responded_at,
                    "remarks": response.remarks,
                },
            )

        except Exception as e:

            application_logger.exception(
                "student_ptm_response_failed",
                user_id=str(user.id),
                meeting_id=str(meeting_id),
                student_id=str(student_id) if student_id else None,
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while submitting the response."
            )


class StudentCompletedPTMAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        student_id = request.query_params.get("student_id")

        application_logger.info(
            "student_completed_ptm_started",
            user_id=str(user.id),
            student_id=str(student_id) if student_id else None,
        )

        try:

            if not student_id:

                return CustomResponse.errorResponse(
                    description="student_id is required.",
                )

            student = Student.objects.select_related(
                "school",
                "branch",
                "academic_year",
                "grade",
                "section",
            ).filter(
                id=student_id,
                status=Student.Status.ACTIVE,
            ).first()

            if student is None:

                application_logger.warning(
                    "student_completed_ptm_student_not_found",
                    user_id=str(user.id),
                    student_id=str(student_id),
                )

                return CustomResponse.errorResponse(
                    description="Student not found.",
                )

            meetings = ParentTeacherMeeting.objects.select_related(
                "academic_year",
                "branch",
                "grade",
            ).prefetch_related(
                Prefetch(
                    "meeting_staffs",
                    queryset=ParentTeacherMeetingStaff.objects.select_related(
                        "staff",
                    ),
                ),
            ).filter(
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                meeting_sections__section_id=student.section_id,
                status=ParentTeacherMeeting.Status.COMPLETED,
            )

            if student.branch_id:

                meetings = meetings.filter(
                    branch_id=student.branch_id,
                )

            else:

                meetings = meetings.filter(
                    branch__isnull=True,
                )

            meetings = meetings.distinct().order_by(
                "-meeting_date",
                "-start_time",
            )

            responses = ParentTeacherMeetingResponse.objects.filter(
                meeting__in=meetings,
                student=student,
            )

            response_map = {
                response.meeting_id: response
                for response in responses
            }

            attended_count = responses.filter(
                attendance_status=ParentTeacherMeetingResponse.AttendanceStatus.PRESENT,
            ).count()

            absent_count = responses.filter(
                attendance_status=ParentTeacherMeetingResponse.AttendanceStatus.ABSENT,
            ).count()

            data = []

            for meeting in meetings:

                response = response_map.get(
                    meeting.id,
                )

                data.append(
                    {
                        "id": str(meeting.id),
                        "title": meeting.title,
                        "meeting_type": meeting.meeting_type,
                        "meeting_date": meeting.meeting_date,
                        "start_time": meeting.start_time,
                        "end_time": meeting.end_time,
                        "meeting_mode": meeting.meeting_mode,
                        "location": meeting.location,
                        "meeting_link": meeting.meeting_link,
                        # "response_status": meeting.response_status,
                        "attendance_status": (
                            response.attendance_status
                            if response
                            else ParentTeacherMeetingResponse.AttendanceStatus.NOT_MARKED
                        ),
                        "is_attended": (
                            response.attendance_status ==
                            ParentTeacherMeetingResponse.AttendanceStatus.PRESENT
                            if response
                            else False
                        ),
                        "attended_at": (
                            response.attended_at
                            if response
                            else None
                        ),
                        "remarks": (
                            response.remarks
                            if response
                            else None
                        ),
                        "staffs": [
                            {
                                "id": str(item.staff.id),
                                "name": item.staff.name,
                                "staff_type": item.staff.get_staff_type_display(),
                                "is_host": (
                                    item.responsibility ==
                                    ParentTeacherMeetingStaff.Responsibility.HOST
                                ),
                            }
                            for item in meeting.meeting_staffs.all()
                        ],
                    }
                )

            application_logger.info(
                "student_completed_ptm_fetched",
                user_id=str(user.id),
                student_id=str(student.id),
                total_completed=len(data),
            )

            return CustomResponse.successResponse(
                description="Completed parent teacher meetings fetched successfully.",
                data={
                    "summary": {
                        "total_completed": len(data),
                        "attended_count": attended_count,
                        "absent_count": absent_count,
                    },
                    "meetings": data,
                },
            )

        except Exception:

            application_logger.exception(
                "student_completed_ptm_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching completed parent teacher meetings.",
            )



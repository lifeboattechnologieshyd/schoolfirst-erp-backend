from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ptm.models import ParentTeacherMeeting, ParentTeacherMeetingResponse
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

        if not student_id:

            application_logger.warning(
                "student_ptm_list_validation_failed",
                user_id=str(user.id),
                reason="student_id_required",
            )

            return CustomResponse.errorResponse(
                description="student_id is required."
            )

        try:

            student = Student.objects.select_related(
                "school",
                "branch",
                "academic_year",
                "grade",
                "section",
            ).filter(
                id=student_id,
                student_parents__parent__user=user,
                status=Student.Status.ACTIVE,
            ).first()

            if student is None:

                student_exists = Student.objects.filter(
                    id=student_id,
                ).exists()

                active_student_exists = Student.objects.filter(
                    id=student_id,
                    status=Student.Status.ACTIVE,
                ).exists()

                parent_access_exists = Student.objects.filter(
                    id=student_id,
                    student_parents__parent__user=user,
                ).exists()

                application_logger.warning(
                    "student_ptm_list_access_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    student_exists=student_exists,
                    active_student_exists=active_student_exists,
                    parent_access_exists=parent_access_exists,
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            application_logger.info(
                "student_ptm_student_found",
                user_id=str(user.id),
                student_id=str(student.id),
                school_id=str(student.school_id),
                branch_id=(
                    str(student.branch_id)
                    if student.branch_id
                    else None
                ),
                academic_year_id=str(student.academic_year_id),
                grade_id=str(student.grade_id),
                section_id=str(student.section_id),
            )

            meetings = ParentTeacherMeeting.objects.select_related(
                "academic_year",
                "branch",
                "grade",
            ).prefetch_related(
                "meeting_sections__section",
            ).filter(
                school=student.school,
                branch=student.branch,
                academic_year=student.academic_year,
                grade=student.grade,
                meeting_sections__section=student.section,
            ).exclude(
                status=ParentTeacherMeeting.Status.DRAFT,
            ).distinct().order_by(
                "-meeting_date",
                "-start_time",
            )

            application_logger.info(
                "student_ptm_meetings_found",
                user_id=str(user.id),
                student_id=str(student.id),
                total_count=meetings.count(),
            )

            responses = ParentTeacherMeetingResponse.objects.filter(
                meeting__in=meetings,
                student=student,
            )

            response_map = {
                response.meeting_id: response
                for response in responses
            }

            application_logger.info(
                "student_ptm_responses_found",
                user_id=str(user.id),
                student_id=str(student.id),
                total_count=len(response_map),
            )

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
                "student_ptm_list_completed",
                user_id=str(user.id),
                student_id=str(student.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Parent teacher meetings fetched successfully.",
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "admission_number": student.admission_number,
                    },
                    "meetings": data,
                },
            )

        except Exception as e:

            application_logger.exception(
                "student_ptm_list_failed",
                user_id=str(user.id),
                student_id=str(student_id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch parent teacher meetings."
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
        )

        if not student_id:
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
            )

            return CustomResponse.errorResponse(
                description="Invalid response status."
            )

        student = Student.objects.select_related(
            "school",
            "academic_year",
            "grade",
            "section",
        ).filter(
            id=student_id,
            student_parents__parent__user=user,
            status=Student.Status.ACTIVE,
        ).first()

        if student is None:

            application_logger.warning(
                "student_ptm_response_failed",
                reason="student_not_found_or_access_denied",
                user_id=str(user.id),
                student_id=str(student_id),
            )

            return CustomResponse.errorResponse(
                description="Student not found."
            )

        meeting = ParentTeacherMeeting.objects.filter(
            id=meeting_id,
            school=student.school,
            academic_year=student.academic_year,
            grade=student.grade,
            meeting_sections__section=student.section,
        ).exclude(
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
            )

            return CustomResponse.errorResponse(
                description="Parent teacher meeting not found."
            )

        try:

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

        except Exception as e:

            application_logger.exception(
                "student_ptm_response_failed",
                user_id=str(user.id),
                meeting_id=str(meeting.id),
                student_id=str(student.id),
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description=str(e)
            )

        application_logger.info(
            "student_ptm_response_submitted",
            user_id=str(user.id),
            meeting_id=str(meeting.id),
            student_id=str(student.id),
            response_status=response.response_status,
            created=created,
        )

        return CustomResponse.successResponse(
            description=(
                "Response submitted successfully."
                if created
                else "Response updated successfully."
            ),
            data={
                "id": str(response.id),
                "meeting_id": str(meeting.id),
                "student_id": str(student.id),
                "response_status": response.response_status,
                "responded_at": response.responded_at,
                "remarks": response.remarks,
            },
        )
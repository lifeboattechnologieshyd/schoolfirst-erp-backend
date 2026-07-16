from datetime import timezone

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.homework.models import Assignment, AssignmentSubmission, AssignmentSubmissionAttachment
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class StudentAssignmentListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        student_id = request.query_params.get("student_id")

        application_logger.info(
            "student_assignment_list_started",
            user_id=str(user.id),
            student_id=str(student_id) if student_id else None,
        )

        try:

            if not student_id:

                return CustomResponse.errorResponse(
                    description="student_id is required."
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
                    "student_assignment_list_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    reason="student_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            assignments = Assignment.objects.select_related(
                "academic_year",
                "branch",
                "grade",
                "subject",
                "teacher",
            ).prefetch_related(
                "assignment_sections__section",
            ).filter(
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                assignment_sections__section_id=student.section_id,
            )

            if student.branch_id:

                assignments = assignments.filter(
                    branch_id=student.branch_id,
                )

            else:

                assignments = assignments.filter(
                    branch__isnull=True,
                )

            assignments = assignments.exclude(
                status=Assignment.Status.DRAFT,
            ).distinct().order_by(
                "-assigned_date",
                "-created_at",
            )

            submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments,
                student_id=student.id,
            )

            submission_map = {
                submission.assignment_id: submission
                for submission in submissions
            }

            data = []

            for assignment in assignments:

                submission = submission_map.get(
                    assignment.id,
                )

                data.append({
                    "id": str(assignment.id),
                    "title": assignment.title,
                    "description": assignment.description,
                    "assigned_date": assignment.assigned_date,
                    "due_date": assignment.due_date,
                    "total_marks": assignment.total_marks,
                    "status": assignment.status,
                    "subject": {
                        "id": str(assignment.subject.id),
                        "name": assignment.subject.name,
                    },
                    "teacher": {
                        "id": str(assignment.teacher.id),
                        "name": assignment.teacher.name,
                    },
                    "submission": {
                        "status": (
                            submission.status
                            if submission
                            else AssignmentSubmission.Status.PENDING
                        ),
                        "submitted_at": (
                            submission.submitted_at
                            if submission
                            else None
                        ),
                        "marks_obtained": (
                            submission.marks_obtained
                            if submission
                            else None
                        ),
                        "teacher_remarks": (
                            submission.teacher_remarks
                            if submission
                            else None
                        ),
                    },
                })

            application_logger.info(
                "student_assignment_list_fetched",
                user_id=str(user.id),
                student_id=str(student.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Assignments fetched successfully.",
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "admission_number": student.admission_number,
                    },
                    "assignments": data,
                },
            )

        except Exception:

            application_logger.exception(
                "student_assignment_list_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching assignments."
            )

class StudentAssignmentSubmissionAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):

        user = request.user

        student_id = request.data.get("student_id")
        attachments = request.data.get("attachments", [])

        application_logger.info(
            "student_assignment_submission_started",
            user_id=str(user.id),
            student_id=str(student_id) if student_id else None,
            assignment_id=str(assignment_id),
        )

        try:

            if not student_id:

                return CustomResponse.errorResponse(
                    description="student_id is required."
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
                    "student_assignment_submission_failed",
                    reason="student_not_found",
                    student_id=str(student_id),
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            assignment = Assignment.objects.filter(
                id=assignment_id,
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                assignment_sections__section_id=student.section_id,
                status=Assignment.Status.PUBLISHED,
            ).distinct().first()

            if assignment is None:

                application_logger.warning(
                    "student_assignment_submission_failed",
                    reason="assignment_not_found",
                    assignment_id=str(assignment_id),
                )

                return CustomResponse.errorResponse(
                    description="Assignment not found."
                )

            if not isinstance(attachments, list):

                return CustomResponse.errorResponse(
                    description="attachments must be a list."
                )

            submission_status = (
                AssignmentSubmission.Status.LATE
                if timezone.now().date() > assignment.due_date
                else AssignmentSubmission.Status.SUBMITTED
            )

            with transaction.atomic():

                submission, created = AssignmentSubmission.objects.update_or_create(
                    assignment=assignment,
                    student=student,
                    defaults={
                        "submitted_at": timezone.now(),
                        "status": submission_status,
                    },
                )

                AssignmentSubmissionAttachment.objects.filter(
                    assignment_submission=submission,
                ).delete()

                AssignmentSubmissionAttachment.objects.bulk_create(
                    [
                        AssignmentSubmissionAttachment(
                            assignment_submission=submission,
                            file_name=item.get("file_name"),
                            file_url=item.get("file_url"),
                        )
                        for item in attachments
                    ]
                )

            application_logger.info(
                "student_assignment_submission_completed",
                user_id=str(user.id),
                student_id=str(student.id),
                assignment_id=str(assignment.id),
                submission_id=str(submission.id),
                created=created,
                attachment_count=len(attachments),
            )

            return CustomResponse.successResponse(
                description="Assignment submitted successfully.",
                data={
                    "submission_id": str(submission.id),
                    "submitted_at": submission.submitted_at,
                    "status": submission.status,
                },
            )

        except Exception:

            application_logger.exception(
                "student_assignment_submission_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                assignment_id=str(assignment_id),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while submitting assignment."
            )
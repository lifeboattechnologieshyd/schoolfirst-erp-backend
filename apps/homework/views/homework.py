from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.homework.models import HomeworkSubmission, Homework, HomeworkSubmissionAttachment
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class StudentHomeworkListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        student_id = request.query_params.get("student_id")

        application_logger.info(
            "student_homework_list_started",
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
                    "student_homework_list_failed",
                    user_id=str(user.id),
                    student_id=str(student_id),
                    reason="student_not_found",
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            homeworks = Homework.objects.select_related(
                "academic_year",
                "branch",
                "grade",
                "subject",
                "teacher",
            ).prefetch_related(
                "homework_sections__section",
            ).filter(
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                homework_sections__section_id=student.section_id,
            )

            if student.branch_id:

                homeworks = homeworks.filter(
                    branch_id=student.branch_id,
                )

            else:

                homeworks = homeworks.filter(
                    branch__isnull=True,
                )

            homeworks = homeworks.exclude(
                status=Homework.Status.DRAFT,
            ).distinct().order_by(
                "-assigned_date",
                "-created_at",
            )

            submissions = HomeworkSubmission.objects.filter(
                homework__in=homeworks,
                student_id=student.id,
            )

            submission_map = {
                submission.homework_id: submission
                for submission in submissions
            }

            data = []

            for homework in homeworks:

                submission = submission_map.get(
                    homework.id,
                )

                data.append({
                    "id": str(homework.id),
                    "title": homework.title,
                    "description": homework.description,
                    "assigned_date": homework.assigned_date,
                    "due_date": homework.due_date,
                    "status": homework.status,
                    "subject": {
                        "id": str(homework.subject.id),
                        "name": homework.subject.name,
                    },
                    "teacher": {
                        "id": str(homework.teacher.id),
                        "name": homework.teacher.name,
                    },
                    "submission": {
                        "status": (
                            submission.status
                            if submission
                            else HomeworkSubmission.Status.PENDING
                        ),
                        "submitted_at": (
                            submission.submitted_at
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
                "student_homework_list_fetched",
                user_id=str(user.id),
                student_id=str(student.id),
                total_count=len(data),
            )

            return CustomResponse.successResponse(
                description="Homeworks fetched successfully.",
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "admission_number": student.admission_number,
                    },
                    "homeworks": data,
                },
            )

        except Exception:

            application_logger.exception(
                "student_homework_list_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while fetching homeworks."
            )


class StudentHomeworkSubmissionAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, homework_id):

        user = request.user

        student_id = request.data.get("student_id")
        remarks = request.data.get("remarks")
        attachments = request.data.get("attachments", [])

        application_logger.info(
            "student_homework_submission_started",
            user_id=str(user.id),
            student_id=str(student_id) if student_id else None,
            homework_id=str(homework_id),
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
                    "student_homework_submission_failed",
                    reason="student_not_found",
                    student_id=str(student_id),
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            homework = Homework.objects.filter(
                id=homework_id,
                school_id=student.school_id,
                academic_year_id=student.academic_year_id,
                grade_id=student.grade_id,
                homework_sections__section_id=student.section_id,
                status=Homework.Status.PUBLISHED,
            ).distinct().first()

            if homework is None:

                application_logger.warning(
                    "student_homework_submission_failed",
                    reason="homework_not_found",
                    homework_id=str(homework_id),
                )

                return CustomResponse.errorResponse(
                    description="Homework not found."
                )

            if not isinstance(attachments, list):

                return CustomResponse.errorResponse(
                    description="attachments must be a list."
                )

            with transaction.atomic():

                submission, created = HomeworkSubmission.objects.update_or_create(
                    homework=homework,
                    student=student,
                    defaults={
                        "submitted_at": timezone.now(),
                        "remarks": remarks,
                        "status": HomeworkSubmission.Status.SUBMITTED,
                    },
                )

                HomeworkSubmissionAttachment.objects.filter(
                    homework_submission=submission,
                ).delete()

                HomeworkSubmissionAttachment.objects.bulk_create(
                    [
                        HomeworkSubmissionAttachment(
                            homework_submission=submission,
                            file_name=item.get("file_name"),
                            file_url=item.get("file_url"),
                        )
                        for item in attachments
                    ]
                )

            application_logger.info(
                "student_homework_submission_completed",
                user_id=str(user.id),
                student_id=str(student.id),
                homework_id=str(homework.id),
                submission_id=str(submission.id),
                created=created,
                attachment_count=len(attachments),
            )

            return CustomResponse.successResponse(
                description="Homework submitted successfully.",
                data={
                    "submission_id": str(submission.id),
                    "submitted_at": submission.submitted_at,
                    "status": submission.status,
                },
            )

        except Exception:

            application_logger.exception(
                "student_homework_submission_failed",
                user_id=str(user.id),
                student_id=str(student_id) if student_id else None,
                homework_id=str(homework_id),
            )

            return CustomResponse.errorResponse(
                description="Something went wrong while submitting homework."
            )
from uuid import UUID

from django.db import transaction, IntegrityError
from django.db.models import Prefetch, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.feedback.models import FeedbackCategory, Feedback, FeedbackResponse
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class CreateFeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school = request.school

        student_id = request.data.get("student_id")
        category_id = request.data.get("category_id")
        subject = request.data.get("subject", "")
        message = request.data.get("message", "")

        application_logger.info(
            "parent_feedback_create_started",
            extra={
                "school_id": str(school.id) if school else None,
                "requested_by": str(request.user.id),
                "student_id": student_id,
                "category_id": category_id,
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        if not student_id:
            return CustomResponse.errorResponse(
                description="Student ID is required."
            )

        if not category_id:
            return CustomResponse.errorResponse(
                description="Feedback category is required."
            )

        if not isinstance(subject, str) or not subject.strip():
            return CustomResponse.errorResponse(
                description="Feedback subject is required."
            )

        if len(subject.strip()) > 255:
            return CustomResponse.errorResponse(
                description="Subject cannot exceed 255 characters."
            )

        if not isinstance(message, str) or not message.strip():
            return CustomResponse.errorResponse(
                description="Feedback message is required."
            )

        try:
            # Validate UUIDs
            try:
                student_id = UUID(str(student_id))
                category_id = UUID(str(category_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid student ID or category ID."
                )

            # Validate student belongs to this school
            student = Student.objects.filter(
                id=student_id,
                school=school,
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found."
                )



            # Validate feedback category
            category = FeedbackCategory.objects.filter(
                id=category_id,
                school=school,
                is_active=True,
            ).first()

            if not category:
                return CustomResponse.errorResponse(
                    description="Feedback category not found or inactive."
                )

            with transaction.atomic():
                feedback = Feedback.objects.create(
                    school=school,
                    parent=request.user,
                    student=student,
                    category=category,
                    subject=subject.strip(),
                    message=message.strip(),
                    status=Feedback.Status.SUBMITTED,
                )

            application_logger.info(
                "parent_feedback_created",
                extra={
                    "school_id": str(school.id),
                    "feedback_id": str(feedback.id),
                    "student_id": str(student.id),
                    "category_id": str(category.id),
                    "requested_by": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(feedback.id),
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                    },
                    "category": {
                        "id": str(category.id),
                        "name": category.name,
                    },
                    "subject": feedback.subject,
                    "message": feedback.message,
                    "status": feedback.status,
                    "created_at": feedback.created_at,
                },
                description="Feedback submitted successfully.",
            )

        except IntegrityError:
            application_logger.exception(
                "parent_feedback_create_integrity_error",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to submit feedback."
            )

        except Exception as e:
            application_logger.exception(
                "parent_feedback_create_failed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "student_id": str(student_id),
                    "category_id": str(category_id),
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to submit feedback."
            )

class MyFeedbackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        status = request.query_params.get("status")
        student_id = request.query_params.get("student_id")
        category_id = request.query_params.get("category_id")

        application_logger.info(
            "my_feedback_list_started",
            extra={
                "school_id": str(school.id) if school else None,
                "requested_by": str(request.user.id),
                "status": status,
                "student_id": student_id,
                "category_id": category_id,
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        try:
            # Validate status
            if status:
                valid_statuses = [
                    choice[0]
                    for choice in Feedback.Status.choices
                ]

                if status not in valid_statuses:
                    return CustomResponse.errorResponse(
                        description="Invalid feedback status."
                    )

            # Validate UUID filters
            if student_id:
                try:
                    student_id = UUID(str(student_id))
                except (ValueError, TypeError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid student ID."
                    )

            if category_id:
                try:
                    category_id = UUID(str(category_id))
                except (ValueError, TypeError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid category ID."
                    )

            responses_queryset = (
                FeedbackResponse.objects
                .select_related("responded_by")
                .order_by("created_at")
            )

            feedbacks = (
                Feedback.objects
                .filter(
                    school=school,
                    parent=request.user,
                )
                .select_related(
                    "student",
                    "category",
                    "parent",
                )
                .prefetch_related(
                    Prefetch(
                        "responses",
                        queryset=responses_queryset,
                    )
                )
            )

            if status:
                feedbacks = feedbacks.filter(status=status)

            if student_id:
                feedbacks = feedbacks.filter(
                    student_id=student_id
                )

            if category_id:
                feedbacks = feedbacks.filter(
                    category_id=category_id
                )

            feedbacks = feedbacks.order_by("-created_at")

            total = feedbacks.count()
            data = []

            for feedback in feedbacks:
                responses_data = []

                for response in feedback.responses.all():
                    responses_data.append({
                        "id": str(response.id),
                        "message": response.message,
                        "responded_by": {
                            "id": str(response.responded_by_id),
                            "name": (
                                getattr(response.responded_by, "name", None)
                                if response.responded_by
                                else None
                            ),
                        },
                        "created_at": response.created_at,
                    })

                data.append({
                    "id": str(feedback.id),
                    "student": (
                        {
                            "id": str(feedback.student_id),
                            "name": feedback.student.name,
                        }
                        if feedback.student
                        else None
                    ),
                    "category": {
                        "id": str(feedback.category_id),
                        "name": feedback.category.name,
                    },
                    "subject": feedback.subject,
                    "message": feedback.message,
                    "status": feedback.status,
                    "created_at": feedback.created_at,
                    "updated_at": feedback.updated_at,
                    "responses": responses_data,
                })

            application_logger.info(
                "my_feedback_list_completed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "total": total,
                },
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Feedback fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "my_feedback_list_failed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch feedback."
            )

class FeedbackCategoryLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        search = request.query_params.get("search", "").strip()

        application_logger.info(
            "feedback_category_list_started",
            extra={
                "school_id": str(school.id) if school else None,
                "requested_by": str(request.user.id),
                "search": search,
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        try:
            categories = FeedbackCategory.objects.filter(
                school=school,
                is_active=True,
            )

            if search:
                categories = categories.filter(
                    Q(name__icontains=search)
                    | Q(description__icontains=search)
                )



            categories = categories.order_by("name")

            total = categories.count()

            data = [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                }
                for category in categories
            ]

            application_logger.info(
                "feedback_category_list_completed",
                extra={
                    "school_id": str(school.id),
                    "total": total,
                },
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Feedback categories fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "feedback_category_list_failed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch feedback categories."
            )
import uuid
from datetime import date

from django.db import transaction, IntegrityError
from django.db.models import Q, Prefetch
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.feedback.models import FeedbackCategory, Feedback, FeedbackResponse
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger


class FeedbackCategoryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feedback_category.create"

    def post(self, request):
        school = request.school

        name = request.data.get("name", "").strip()
        description = request.data.get("description")
        is_active = request.data.get("is_active", True)

        application_logger.info(
            "feedback_category_create_started",
            extra={
                "school_id": str(school.id) if school else None,
                "requested_by": str(request.user.id),
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        if not name:
            return CustomResponse.errorResponse(
                description="Category name is required."
            )

        if len(name) > 100:
            return CustomResponse.errorResponse(
                description="Category name cannot exceed 100 characters."
            )

        if not isinstance(is_active, bool):
            return CustomResponse.errorResponse(
                description="is_active must be a boolean."
            )

        try:
            with transaction.atomic():
                if FeedbackCategory.objects.filter(
                    school=school,
                    name__iexact=name,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Feedback category already exists."
                    )

                category = FeedbackCategory.objects.create(
                    school=school,
                    name=name,
                    description=description,
                    is_active=is_active,
                )

            application_logger.info(
                "feedback_category_created",
                extra={
                    "school_id": str(school.id),
                    "category_id": str(category.id),
                    "requested_by": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                },
                description="Feedback category created successfully.",
            )

        except IntegrityError:
            application_logger.exception(
                "feedback_category_create_integrity_error",
                extra={"school_id": str(school.id)},
            )

            return CustomResponse.errorResponse(
                description="Feedback category already exists."
            )

        except Exception as e:
            application_logger.exception(
                "feedback_category_create_failed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to create feedback category."
            )


class FeedbackCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feedback_category.view"

    def get(self, request):
        school = request.school

        search = request.query_params.get("search", "").strip()
        is_active = request.query_params.get("is_active")

        application_logger.info(
            "feedback_category_list_started",
            extra={
                "school_id": str(school.id) if school else None,
                "requested_by": str(request.user.id),
                "search": search,
                "is_active": is_active,
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        try:
            categories = FeedbackCategory.objects.filter(
                school=school
            )

            if search:
                categories = categories.filter(
                    Q(name__icontains=search)
                    | Q(description__icontains=search)
                )

            if is_active is not None:
                if is_active.lower() not in ["true", "false"]:
                    return CustomResponse.errorResponse(
                        description="is_active must be true or false."
                    )

                categories = categories.filter(
                    is_active=is_active.lower() == "true"
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

class FeedbackCategoryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feedback_category.update"

    def put(self, request, category_id):
        school = request.school

        application_logger.info(
            "feedback_category_update_started",
            extra={
                "school_id": str(school.id) if school else None,
                "category_id": str(category_id),
                "requested_by": str(request.user.id),
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        try:
            try:
                uuid.UUID(str(category_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid feedback category ID."
                )

            category = FeedbackCategory.objects.filter(
                school=school,
                id=category_id,
            ).first()

            if not category:
                return CustomResponse.errorResponse(
                    description="Feedback category not found."
                )

            allowed_fields = {"name", "description", "is_active"}

            if not request.data:
                return CustomResponse.errorResponse(
                    description="Provide at least one field to update."
                )

            invalid_fields = set(request.data.keys()) - allowed_fields

            if invalid_fields:
                return CustomResponse.errorResponse(
                    description=(
                        f"Invalid fields: {', '.join(sorted(invalid_fields))}."
                    )
                )

            if "name" in request.data:
                name = request.data.get("name")

                if not isinstance(name, str) or not name.strip():
                    return CustomResponse.errorResponse(
                        description="Category name cannot be empty."
                    )

                name = name.strip()

                if len(name) > 100:
                    return CustomResponse.errorResponse(
                        description="Category name cannot exceed 100 characters."
                    )

                duplicate = FeedbackCategory.objects.filter(
                    school=school,
                    name__iexact=name,
                ).exclude(id=category.id).exists()

                if duplicate:
                    return CustomResponse.errorResponse(
                        description="Feedback category already exists."
                    )

                category.name = name

            if "description" in request.data:
                description = request.data.get("description")

                if description is not None and not isinstance(
                    description, str
                ):
                    return CustomResponse.errorResponse(
                        description="Description must be a string or null."
                    )

                category.description = description

            if "is_active" in request.data:
                is_active = request.data.get("is_active")

                if not isinstance(is_active, bool):
                    return CustomResponse.errorResponse(
                        description="is_active must be a boolean."
                    )

                category.is_active = is_active

            category.save()

            application_logger.info(
                "feedback_category_updated",
                extra={
                    "school_id": str(school.id),
                    "category_id": str(category.id),
                    "requested_by": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                },
                description="Feedback category updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "feedback_category_update_failed",
                extra={
                    "school_id": str(school.id),
                    "category_id": str(category_id),
                    "requested_by": str(request.user.id),
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to update feedback category."
            )

class FeedbackListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feedback.view"
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        school = request.school

        status = request.query_params.get("status")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        category_id = request.query_params.get("category_id")
        student_id = request.query_params.get("student_id")
        search = request.query_params.get("search", "").strip()

        application_logger.info(
            "feedback_list_started",
            extra={
                "school_id": str(school.id) if school else None,
                "requested_by": str(request.user.id),
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
                "category_id": category_id,
                "student_id": student_id,
                "search": search,
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

            # Validate dates
            parsed_start_date = None
            parsed_end_date = None

            try:
                if start_date:
                    parsed_start_date = date.fromisoformat(start_date)

                if end_date:
                    parsed_end_date = date.fromisoformat(end_date)

            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid date format. Use YYYY-MM-DD."
                )

            if (
                parsed_start_date
                and parsed_end_date
                and parsed_start_date > parsed_end_date
            ):
                return CustomResponse.errorResponse(
                    description="start_date cannot be after end_date."
                )

            # Validate UUID filters
            if category_id:
                try:
                    category_id = uuid.UUID(str(category_id))
                except (ValueError, TypeError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid category ID."
                    )

            if student_id:
                try:
                    student_id = uuid.UUID(str(student_id))
                except (ValueError, TypeError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid student ID."
                    )

            # Base queryset
            responses_queryset = (
                FeedbackResponse.objects
                .select_related("responded_by")
                .order_by("created_at")
            )

            feedbacks = (
                Feedback.objects
                .filter(school=school)
                .select_related(
                    "parent",
                    "student",
                    "category",
                )
                .prefetch_related(
                    Prefetch(
                        "responses",
                        queryset=responses_queryset,
                    )
                )
            )

            # Status filter
            if status:
                feedbacks = feedbacks.filter(status=status)

            # Date filters
            if parsed_start_date:
                feedbacks = feedbacks.filter(
                    created_at__date__gte=parsed_start_date
                )

            if parsed_end_date:
                feedbacks = feedbacks.filter(
                    created_at__date__lte=parsed_end_date
                )

            # Category filter
            if category_id:
                feedbacks = feedbacks.filter(
                    category_id=category_id
                )

            # Student filter
            if student_id:
                feedbacks = feedbacks.filter(
                    student_id=student_id
                )

            # Search filter
            if search:
                feedbacks = feedbacks.filter(
                    Q(subject__icontains=search)
                    | Q(message__icontains=search)
                    | Q(parent__name__icontains=search)
                    | Q(student__name__icontains=search)
                    | Q(category__name__icontains=search)
                )

            feedbacks = feedbacks.order_by("-created_at")

            # Count filtered records before pagination
            total = feedbacks.count()

            # Apply pagination
            paginator = self.pagination_class()
            paginated_feedbacks = paginator.paginate_queryset(
                feedbacks,
                request,
            )

            data = []

            for feedback in paginated_feedbacks:
                responses_data = []

                for response in feedback.responses.all():
                    responses_data.append({
                        "id": str(response.id),
                        "message": response.message,
                        "responded_by": {
                            "id": str(response.responded_by_id),
                            "name": (
                                getattr(
                                    response.responded_by,
                                    "name",
                                    None,
                                )
                                if response.responded_by
                                else None
                            ),
                        },
                        "created_at": response.created_at,
                    })

                data.append({
                    "id": str(feedback.id),
                    "parent": {
                        "id": str(feedback.parent_id),
                        "name": getattr(
                            feedback.parent,
                            "name",
                            None,
                        ),
                    },
                    "student": {
                        "id": str(feedback.student_id),
                        "name": feedback.student.name,
                        "admission_number": feedback.student.admission_number,
                    },
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
                "feedback_list_completed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "total": total,
                    "returned": len(data),
                },
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Feedback fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "feedback_list_failed",
                extra={
                    "school_id": str(school.id),
                    "requested_by": str(request.user.id),
                    "status": status,
                    "start_date": start_date,
                    "end_date": end_date,
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch feedback."
            )


class FeedbackResponseCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feedback_response.create"

    def post(self, request, feedback_id):
        school = request.school
        message = request.data.get("message", "")

        application_logger.info(
            "feedback_response_create_started",
            extra={
                "school_id": str(school.id) if school else None,
                "feedback_id": str(feedback_id),
                "requested_by": str(request.user.id),
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        if not isinstance(message, str) or not message.strip():
            return CustomResponse.errorResponse(
                description="Response message is required."
            )

        try:
            try:
                feedback_id = uuid.UUID(str(feedback_id))
            except (ValueError, TypeError, AttributeError):
                return CustomResponse.errorResponse(
                    description="Invalid feedback ID."
                )

            with transaction.atomic():
                feedback = (
                    Feedback.objects
                    .select_for_update()
                    .filter(
                        id=feedback_id,
                        school=school,
                    )
                    .first()
                )

                if not feedback:
                    return CustomResponse.errorResponse(
                        description="Feedback not found."
                    )

                if feedback.status in [
                    Feedback.Status.RESOLVED,
                    Feedback.Status.REJECTED,
                ]:
                    return CustomResponse.errorResponse(
                        description=(
                            "Cannot respond to resolved or rejected feedback."
                        )
                    )

                response = FeedbackResponse.objects.create(
                    feedback=feedback,
                    responded_by=request.user,
                    message=message.strip(),
                )

                if feedback.status == Feedback.Status.SUBMITTED:
                    feedback.status = Feedback.Status.IN_REVIEW
                    feedback.save(update_fields=["status", "updated_at"])

            application_logger.info(
                "feedback_response_created",
                extra={
                    "school_id": str(school.id),
                    "feedback_id": str(feedback.id),
                    "response_id": str(response.id),
                    "responded_by": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(response.id),
                    "feedback_id": str(feedback.id),
                    "message": response.message,
                    "responded_by": {
                        "id": str(request.user.id),
                        "name": getattr(request.user, "name", None),
                    },
                    "feedback_status": feedback.status,
                    "created_at": response.created_at,
                },
                description="Feedback response submitted successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "feedback_response_create_failed",
                extra={
                    "school_id": str(school.id) if school else None,
                    "feedback_id": str(feedback_id),
                    "requested_by": str(request.user.id),
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to submit feedback response."
            )


class FeedbackStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "feedback.update_status"

    def put(self, request, feedback_id):
        school = request.school
        status = request.data.get("status")

        application_logger.info(
            "feedback_status_update_started",
            extra={
                "school_id": str(school.id) if school else None,
                "feedback_id": str(feedback_id),
                "requested_by": str(request.user.id),
                "requested_status": status,
            },
        )

        if not school:
            return CustomResponse.errorResponse(
                description="School information is required."
            )

        if not status:
            return CustomResponse.errorResponse(
                description="Feedback status is required."
            )

        valid_statuses = [
            choice[0]
            for choice in Feedback.Status.choices
        ]

        if status not in valid_statuses:
            return CustomResponse.errorResponse(
                description="Invalid feedback status."
            )

        try:
            with transaction.atomic():
                feedback = (
                    Feedback.objects
                    .select_for_update()
                    .filter(
                        id=feedback_id,
                        school=school,
                    )
                    .first()
                )

                if not feedback:
                    return CustomResponse.errorResponse(
                        description="Feedback not found."
                    )

                current_status = feedback.status

                # Prevent updates to terminal statuses
                if current_status in [
                    Feedback.Status.RESOLVED,
                    Feedback.Status.REJECTED,
                ]:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Feedback is already {current_status.lower()} "
                            "and cannot be updated."
                        )
                    )

                # Define allowed status transitions
                allowed_transitions = {
                    Feedback.Status.SUBMITTED: [
                        Feedback.Status.IN_REVIEW,
                    ],
                    Feedback.Status.IN_REVIEW: [
                        Feedback.Status.RESOLVED,
                        Feedback.Status.REJECTED,
                    ],
                }

                allowed_statuses = allowed_transitions.get(
                    current_status,
                    [],
                )

                if status not in allowed_statuses:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Cannot change feedback status from "
                            f"{current_status} to {status}."
                        )
                    )

                feedback.status = status
                feedback.save(
                    update_fields=["status", "updated_at"]
                )

            application_logger.info(
                "feedback_status_updated",
                extra={
                    "school_id": str(school.id),
                    "feedback_id": str(feedback.id),
                    "previous_status": current_status,
                    "new_status": feedback.status,
                    "updated_by": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(feedback.id),
                    "previous_status": current_status,
                    "status": feedback.status,
                    "updated_at": feedback.updated_at,
                },
                description="Feedback status updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "feedback_status_update_failed",
                extra={
                    "school_id": str(school.id),
                    "feedback_id": str(feedback_id),
                    "requested_by": str(request.user.id),
                    "requested_status": status,
                    "error": str(e),
                },
            )

            return CustomResponse.errorResponse(
                description="Failed to update feedback status."
            )
import uuid

from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.remarks.models import Remark, RemarkCategory
from apps.school.models.school import Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.utils.logger import application_logger

class RemarkCategoryLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        try:
            categories = RemarkCategory.objects.filter(
                school=school,
                is_active=True,
            ).order_by("name")

            data = [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                }
                for category in categories
            ]

            application_logger.info(
                "app_remark_categories_fetched",
                extra={
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                    "total": len(data),
                },
            )

            return CustomResponse.successResponse(
                data=data,
                total=len(data),
                description="Remark categories fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_remark_categories_fetch_failed",
                extra={
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch remark categories."
            )


class StudentRemarkLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.school

        try:
            # Get students associated with the logged-in parent
            students = Student.objects.filter(
                Q(father=request.user)
                | Q(mother=request.user)
                | Q(guardian=request.user),
                school=school,
            ).distinct()

            # Get remarks visible to parents for their students
            remarks = Remark.objects.filter(
                school=school,
                student__in=students,
                is_visible_to_parent=True,
            ).select_related(
                "student",
                "section",
                "subject",
                "category",
                "teacher",
            ).order_by("-date", "-created_at")

            # Filters
            student_id = request.query_params.get("student_id")
            category_id = request.query_params.get("category_id")
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")

            # Validate student ID
            if student_id:
                try:
                    uuid.UUID(str(student_id))
                except (ValueError, TypeError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid student ID."
                    )

                remarks = remarks.filter(student_id=student_id)

            # Validate category ID
            if category_id:
                try:
                    uuid.UUID(str(category_id))
                except (ValueError, TypeError, AttributeError):
                    return CustomResponse.errorResponse(
                        description="Invalid category ID."
                    )

                remarks = remarks.filter(category_id=category_id)

            # Date filters
            parsed_start_date = None
            parsed_end_date = None

            if start_date:
                parsed_start_date = parse_date(start_date)

                if not parsed_start_date:
                    return CustomResponse.errorResponse(
                        description="Invalid start_date. Use YYYY-MM-DD format."
                    )

                remarks = remarks.filter(date__gte=parsed_start_date)

            if end_date:
                parsed_end_date = parse_date(end_date)

                if not parsed_end_date:
                    return CustomResponse.errorResponse(
                        description="Invalid end_date. Use YYYY-MM-DD format."
                    )

                remarks = remarks.filter(date__lte=parsed_end_date)

            if (
                parsed_start_date
                and parsed_end_date
                and parsed_start_date > parsed_end_date
            ):
                return CustomResponse.errorResponse(
                    description="start_date cannot be later than end_date."
                )

            # Total before pagination
            total = remarks.count()

            # Pagination
            paginator = CustomPageNumberPagination()
            paginated_remarks = paginator.paginate_queryset(
                remarks,
                request,
                view=self,
            )

            data = []

            for remark in paginated_remarks:
                data.append({
                    "id": str(remark.id),
                    "student": {
                        "id": str(remark.student_id),
                        "name": remark.student.name,
                    },
                    "section": {
                        "id": str(remark.section_id),
                        "name": remark.section.name,
                    },
                    "subject": {
                        "id": str(remark.subject_id),
                        "name": remark.subject.name,
                    },
                    "category": {
                        "id": str(remark.category_id),
                        "name": remark.category.name,
                    },
                    "teacher": {
                        "id": str(remark.teacher_id),
                        "name": remark.teacher.name,
                    },
                    "date": remark.date,
                    "title": remark.title,
                    "description": remark.description,
                    "context": remark.context,
                    "created_at": remark.created_at,
                })

            application_logger.info(
                "parent_student_remarks_fetched",
                extra={
                    "school_id": str(school.id),
                    "parent_id": str(request.user.id),
                    "total": total,
                },
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Student remarks fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "parent_student_remarks_fetch_failed",
                extra={
                    "school_id": str(school.id),
                    "parent_id": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch student remarks."
            )
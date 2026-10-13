import uuid
from datetime import date
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.remarks.models import RemarkCategory, Remark
from apps.school.models.school import Student, Subject, Section
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.logger import application_logger

class RemarkCategoryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "remark_category.create"

    def post(self, request):
        school = request.school

        name = request.data.get("name")
        description = request.data.get("description", "")

        if not isinstance(name, str) or not name.strip():
            return CustomResponse.errorResponse(
                description="Category name is required.",
                status_code=400,
            )

        name = name.strip()

        if len(name) > 100:
            return CustomResponse.errorResponse(
                description="Category name cannot exceed 100 characters.",
                status_code=400,
            )

        if description is not None and not isinstance(description, str):
            return CustomResponse.errorResponse(
                description="Description must be text.",
                status_code=400,
            )

        description = description.strip() if description else None

        if RemarkCategory.objects.filter(
            school=school,
            name__iexact=name,
        ).exists():
            return CustomResponse.errorResponse(
                description="A category with this name already exists.",
                status_code=400,
            )

        try:
            with transaction.atomic():
                category = RemarkCategory.objects.create(
                    school=school,
                    name=name,
                    description=description,
                )

            application_logger.info(
                "remark_category_created",
                extra={
                    "category_id": str(category.id),
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                },
                description="Remark category created successfully.",
            )

        except IntegrityError:
            application_logger.exception(
                "remark_category_create_integrity_error",
                extra={"school_id": str(school.id)},
            )

            return CustomResponse.errorResponse(
                description="A category with this name already exists.",
                status_code=400,
            )

        except Exception:
            application_logger.exception(
                "remark_category_create_failed",
                extra={"school_id": str(school.id)},
            )

            return CustomResponse.errorResponse(
                description="Unable to create remark category.",
                status_code=500,
            )


class RemarkCategoryListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "remark_category.view"

    def get(self, request):
        school = request.school

        try:
            categories = RemarkCategory.objects.filter(
                school=school
            ).order_by("name")

            search = request.query_params.get("search")
            is_active = request.query_params.get("is_active")

            if search:
                categories = categories.filter(
                    Q(name__icontains=search)
                    | Q(description__icontains=search)
                )

            if is_active is not None:
                if is_active.lower() not in ("true", "false"):
                    return CustomResponse.errorResponse(
                        description="is_active must be true or false.",
                        status_code=400,
                    )

                categories = categories.filter(
                    is_active=is_active.lower() == "true"
                )

            total = categories.count()

            data = [
                {
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                    "created_at": category.created_at,
                    "updated_at": category.updated_at,
                }
                for category in categories
            ]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Remark categories fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "remark_category_list_failed",
                extra={"school_id": str(school.id)},
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch remark categories.",
                status_code=500,
            )

class RemarkCategoryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "remark_category.update"

    def patch(self, request, category_id):
        school = request.school

        try:
            category_uuid = uuid.UUID(str(category_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid category ID.",
                status_code=400,
            )

        category = RemarkCategory.objects.filter(
            id=category_uuid,
            school=school,
        ).first()

        if not category:
            return CustomResponse.errorResponse(
                description="Remark category not found.",
                status_code=404,
            )

        allowed_fields = {"name", "description", "is_active"}
        invalid_fields = set(request.data.keys()) - allowed_fields

        if invalid_fields:
            return CustomResponse.errorResponse(
                description=f"Invalid fields: {', '.join(sorted(invalid_fields))}.",
                status_code=400,
            )

        if not request.data:
            return CustomResponse.errorResponse(
                description="At least one field is required for update.",
                status_code=400,
            )

        if "name" in request.data:
            name = request.data["name"]

            if not isinstance(name, str) or not name.strip():
                return CustomResponse.errorResponse(
                    description="Category name cannot be empty.",
                    status_code=400,
                )

            name = name.strip()

            if len(name) > 100:
                return CustomResponse.errorResponse(
                    description="Category name cannot exceed 100 characters.",
                    status_code=400,
                )

            duplicate = RemarkCategory.objects.filter(
                school=school,
                name__iexact=name,
            ).exclude(id=category.id).exists()

            if duplicate:
                return CustomResponse.errorResponse(
                    description="A category with this name already exists.",
                    status_code=400,
                )

            category.name = name

        if "description" in request.data:
            description = request.data["description"]

            if description is not None and not isinstance(description, str):
                return CustomResponse.errorResponse(
                    description="Description must be text.",
                    status_code=400,
                )

            category.description = (
                description.strip() if description else None
            )

        if "is_active" in request.data:
            is_active = request.data["is_active"]

            if not isinstance(is_active, bool):
                return CustomResponse.errorResponse(
                    description="is_active must be a boolean.",
                    status_code=400,
                )

            category.is_active = is_active

        try:
            with transaction.atomic():
                category.save()

            application_logger.info(
                "remark_category_updated",
                extra={
                    "category_id": str(category.id),
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "name": category.name,
                    "description": category.description,
                    "is_active": category.is_active,
                },
                description="Remark category updated successfully.",
            )

        except Exception:
            application_logger.exception(
                "remark_category_update_failed",
                extra={"category_id": str(category.id)},
            )

            return CustomResponse.errorResponse(
                description="Unable to update remark category.",
                status_code=500,
            )




class RemarkCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_remark.create"

    def post(self, request):
        school = request.school

        student_id = request.data.get("student_id")
        section_id = request.data.get("section_id")
        subject_id = request.data.get("subject_id")
        category_id = request.data.get("category_id")

        remark_date = request.data.get("date")
        title = request.data.get("title")
        description = request.data.get("description")
        context = request.data.get("context")

        is_visible_to_staff = request.data.get(
            "is_visible_to_staff", True
        )
        is_visible_to_parent = request.data.get(
            "is_visible_to_parent", True
        )

        # Validate required fields
        required_fields = {
            "student_id": student_id,
            "section_id": section_id,
            "subject_id": subject_id,
            "category_id": category_id,
            "title": title,
            "description": description,
        }

        for field, value in required_fields.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                return CustomResponse.errorResponse(
                    description=f"{field} is required.",
                    status_code=400,
                )

        # Validate UUIDs
        try:
            student_uuid = uuid.UUID(str(student_id))
            section_uuid = uuid.UUID(str(section_id))
            subject_uuid = uuid.UUID(str(subject_id))
            category_uuid = uuid.UUID(str(category_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid student, section, subject, or category ID.",
                status_code=400,
            )

        # Validate title
        if not isinstance(title, str) or len(title.strip()) > 255:
            return CustomResponse.errorResponse(
                description="Title must be a string with at most 255 characters.",
                status_code=400,
            )

        # Validate description
        if not isinstance(description, str) or not description.strip():
            return CustomResponse.errorResponse(
                description="Description is required.",
                status_code=400,
            )

        # Validate context
        if context is not None and not isinstance(context, str):
            return CustomResponse.errorResponse(
                description="Context must be text.",
                status_code=400,
            )

        # Validate visibility flags
        if not isinstance(is_visible_to_staff, bool):
            return CustomResponse.errorResponse(
                description="is_visible_to_staff must be a boolean.",
                status_code=400,
            )

        if not isinstance(is_visible_to_parent, bool):
            return CustomResponse.errorResponse(
                description="is_visible_to_parent must be a boolean.",
                status_code=400,
            )

        # Validate date
        if remark_date:
            try:
                remark_date = date.fromisoformat(remark_date)
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid date. Use YYYY-MM-DD format.",
                    status_code=400,
                )
        else:
            remark_date = timezone.localdate()

        try:
            # Validate student belongs to the school
            student = Student.objects.filter(
                id=student_uuid,
                school=school,
            ).first()

            if not student:
                return CustomResponse.errorResponse(
                    description="Student not found in this school.",
                    status_code=404,
                )

            # Validate section belongs to the school
            section = Section.objects.filter(
                id=section_uuid,
            ).first()

            if not section:
                return CustomResponse.errorResponse(
                    description="Section not found.",
                    status_code=404,
                )

            # Ensure the selected section matches the student's section.
            # Assumes Student has a direct ForeignKey named `section`.
            if student.section_id != section.id:
                return CustomResponse.errorResponse(
                    description="The selected section does not belong to this student.",
                    status_code=400,
                )

            # Validate subject
            subject = Subject.objects.filter(
                id=subject_uuid,
            ).first()

            if not subject:
                return CustomResponse.errorResponse(
                    description="Subject not found.",
                    status_code=404,
                )

            # Validate category belongs to the current school and is active
            category = RemarkCategory.objects.filter(
                id=category_uuid,
                school=school,
                is_active=True,
            ).first()

            if not category:
                return CustomResponse.errorResponse(
                    description="Invalid or inactive remark category.",
                    status_code=400,
                )

            with transaction.atomic():
                remark = Remark.objects.create(
                    school=school,
                    student=student,
                    section=section,
                    subject=subject,
                    category=category,
                    teacher=request.user,
                    date=remark_date,
                    title=title.strip(),
                    description=description.strip(),
                    context=context.strip() if context else None,
                    is_visible_to_staff=is_visible_to_staff,
                    is_visible_to_parent=is_visible_to_parent,
                )

            application_logger.info(
                "student_remark_created",
                extra={
                    "remark_id": str(remark.id),
                    "school_id": str(school.id),
                    "student_id": str(student.id),
                    "section_id": str(section.id),
                    "subject_id": str(subject.id),
                    "category_id": str(category.id),
                    "teacher_id": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(remark.id),
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                    },
                    "section": {
                        "id": str(section.id),
                        "name": section.name,
                    },
                    "subject": {
                        "id": str(subject.id),
                        "name": subject.name,
                    },
                    "category": {
                        "id": str(category.id),
                        "name": category.name,
                    },
                    "date": remark.date,
                    "title": remark.title,
                    "description": remark.description,
                    "context": remark.context,
                    "is_visible_to_staff": remark.is_visible_to_staff,
                    "is_visible_to_parent": remark.is_visible_to_parent,
                    "created_at": remark.created_at,
                },
                description="Student remark created successfully.",
            )

        except Exception:
            application_logger.exception(
                "student_remark_create_failed",
                extra={
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to create student remark.",
                status_code=500,
            )


class RemarkListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_remark.view"

    def get(self, request):
        school = request.school

        try:
            remarks = Remark.objects.filter(
                school=school
            ).select_related(
                "student",
                "section",
                "subject",
                "category",
                "teacher",
            ).order_by("-date", "-created_at")

            # Filters
            student_id = request.query_params.get("student_id")
            section_id = request.query_params.get("section_id")
            subject_id = request.query_params.get("subject_id")
            category_id = request.query_params.get("category_id")
            start_date = request.query_params.get("start_date")
            end_date = request.query_params.get("end_date")
            search = request.query_params.get("search")

            # Validate UUID filters
            uuid_filters = {
                "student_id": student_id,
                "section_id": section_id,
                "subject_id": subject_id,
                "category_id": category_id,
            }

            for field, value in uuid_filters.items():
                if value:
                    try:
                        uuid.UUID(str(value))
                    except (ValueError, TypeError, AttributeError):
                        return CustomResponse.errorResponse(
                            description=f"Invalid {field}."
                        )

            if student_id:
                remarks = remarks.filter(student_id=student_id)

            if section_id:
                remarks = remarks.filter(section_id=section_id)

            if subject_id:
                remarks = remarks.filter(subject_id=subject_id)

            if category_id:
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

            # Search
            if search:
                remarks = remarks.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                    | Q(context__icontains=search)
                )

            # Total records before pagination
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
                    "is_visible_to_staff": remark.is_visible_to_staff,
                    "is_visible_to_parent": remark.is_visible_to_parent,
                    "created_at": remark.created_at,
                    "updated_at": remark.updated_at,
                })

            application_logger.info(
                "student_remark_list_fetched",
                extra={
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
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
                "student_remark_list_failed",
                extra={
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch student remarks."
            )




class RemarkUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_remark.update"

    def patch(self, request, remark_id):
        school = request.school

        # Validate remark ID
        try:
            remark_uuid = uuid.UUID(str(remark_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid remark ID."
            )

        # Get remark belonging to the current school
        remark = Remark.objects.filter(
            id=remark_uuid,
            school=school,
        ).first()

        if remark is None:
            return CustomResponse.errorResponse(
                description="Student remark not found."
            )

        allowed_fields = {
            "student_id",
            "section_id",
            "subject_id",
            "category_id",
            "date",
            "title",
            "description",
            "context",
            "is_visible_to_staff",
            "is_visible_to_parent",
        }

        invalid_fields = set(request.data.keys()) - allowed_fields

        if invalid_fields:
            return CustomResponse.errorResponse(
                description=f"Invalid fields: {', '.join(sorted(invalid_fields))}."
            )

        if not request.data:
            return CustomResponse.errorResponse(
                description="At least one field is required for update."
            )

        try:
            with transaction.atomic():
                # Lock the remark while updating
                remark = Remark.objects.select_for_update().filter(
                    id=remark_uuid,
                    school=school,
                ).first()

                if remark is None:
                    return CustomResponse.errorResponse(
                        description="Student remark not found."
                    )

                # Validate student
                student = remark.student

                if "student_id" in request.data:
                    try:
                        student_uuid = uuid.UUID(
                            str(request.data["student_id"])
                        )
                    except (ValueError, TypeError, AttributeError):
                        return CustomResponse.errorResponse(
                            description="Invalid student ID."
                        )

                    student = Student.objects.filter(
                        id=student_uuid,
                        school=school,
                    ).first()

                    if student is None:
                        return CustomResponse.errorResponse(
                            description="Student not found in this school."
                        )

                # Validate section
                section = remark.section

                if "section_id" in request.data:
                    try:
                        section_uuid = uuid.UUID(
                            str(request.data["section_id"])
                        )
                    except (ValueError, TypeError, AttributeError):
                        return CustomResponse.errorResponse(
                            description="Invalid section ID."
                        )

                    section = Section.objects.filter(
                        id=section_uuid,
                    ).first()

                    if section is None:
                        return CustomResponse.errorResponse(
                            description="Section not found."
                        )

                # Assumes Student has a direct ForeignKey named section.
                if student.section_id != section.id:
                    return CustomResponse.errorResponse(
                        description="The selected section does not belong to this student."
                    )

                # Validate subject
                subject = remark.subject

                if "subject_id" in request.data:
                    try:
                        subject_uuid = uuid.UUID(
                            str(request.data["subject_id"])
                        )
                    except (ValueError, TypeError, AttributeError):
                        return CustomResponse.errorResponse(
                            description="Invalid subject ID."
                        )

                    subject = Subject.objects.filter(
                        id=subject_uuid,
                    ).first()

                    if subject is None:
                        return CustomResponse.errorResponse(
                            description="Subject not found."
                        )

                # Validate category
                category = remark.category

                if "category_id" in request.data:
                    try:
                        category_uuid = uuid.UUID(
                            str(request.data["category_id"])
                        )
                    except (ValueError, TypeError, AttributeError):
                        return CustomResponse.errorResponse(
                            description="Invalid category ID."
                        )

                    category = RemarkCategory.objects.filter(
                        id=category_uuid,
                        school=school,
                        is_active=True,
                    ).first()

                    if category is None:
                        return CustomResponse.errorResponse(
                            description="Invalid or inactive remark category."
                        )

                # Validate date
                remark_date = remark.date

                if "date" in request.data:
                    date_value = request.data["date"]

                    if not isinstance(date_value, str):
                        return CustomResponse.errorResponse(
                            description="Invalid date. Use YYYY-MM-DD format."
                        )

                    remark_date = parse_date(date_value)

                    if remark_date is None:
                        return CustomResponse.errorResponse(
                            description="Invalid date. Use YYYY-MM-DD format."
                        )

                # Validate title
                title = remark.title

                if "title" in request.data:
                    title = request.data["title"]

                    if not isinstance(title, str) or not title.strip():
                        return CustomResponse.errorResponse(
                            description="Title is required."
                        )

                    title = title.strip()

                    if len(title) > 255:
                        return CustomResponse.errorResponse(
                            description="Title cannot exceed 255 characters."
                        )

                # Validate description
                description = remark.description

                if "description" in request.data:
                    description = request.data["description"]

                    if (
                        not isinstance(description, str)
                        or not description.strip()
                    ):
                        return CustomResponse.errorResponse(
                            description="Description is required."
                        )

                    description = description.strip()

                # Validate context
                context = remark.context

                if "context" in request.data:
                    context = request.data["context"]

                    if context is not None and not isinstance(context, str):
                        return CustomResponse.errorResponse(
                            description="Context must be text."
                        )

                    context = context.strip() if context else None

                # Validate visibility flags
                is_visible_to_staff = remark.is_visible_to_staff
                is_visible_to_parent = remark.is_visible_to_parent

                if "is_visible_to_staff" in request.data:
                    is_visible_to_staff = request.data[
                        "is_visible_to_staff"
                    ]

                    if not isinstance(is_visible_to_staff, bool):
                        return CustomResponse.errorResponse(
                            description="is_visible_to_staff must be a boolean."
                        )

                if "is_visible_to_parent" in request.data:
                    is_visible_to_parent = request.data[
                        "is_visible_to_parent"
                    ]

                    if not isinstance(is_visible_to_parent, bool):
                        return CustomResponse.errorResponse(
                            description="is_visible_to_parent must be a boolean."
                        )

                # Update remark
                remark.student = student
                remark.section = section
                remark.subject = subject
                remark.category = category
                remark.date = remark_date
                remark.title = title
                remark.description = description
                remark.context = context
                remark.is_visible_to_staff = is_visible_to_staff
                remark.is_visible_to_parent = is_visible_to_parent

                remark.save()

            application_logger.info(
                "student_remark_updated",
                extra={
                    "remark_id": str(remark.id),
                    "school_id": str(school.id),
                    "student_id": str(remark.student_id),
                    "section_id": str(remark.section_id),
                    "category_id": str(remark.category_id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={
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
                    "is_visible_to_staff": remark.is_visible_to_staff,
                    "is_visible_to_parent": remark.is_visible_to_parent,
                    "created_at": remark.created_at,
                    "updated_at": remark.updated_at,
                },
                description="Student remark updated successfully.",
            )

        except Exception:
            application_logger.exception(
                "student_remark_update_failed",
                extra={
                    "remark_id": str(remark_uuid),
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to update student remark."
            )

class RemarkDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "student_remark.delete"

    def delete(self, request, remark_id):
        school = request.school

        try:
            remark_uuid = uuid.UUID(str(remark_id))
        except (ValueError, TypeError, AttributeError):
            return CustomResponse.errorResponse(
                description="Invalid remark ID."
            )

        remark = Remark.objects.filter(
            id=remark_uuid,
            school=school,
        ).first()

        if remark is None:
            return CustomResponse.errorResponse(
                description="Student remark not found."
            )

        try:
            remark.soft_delete(request.user)

            application_logger.info(
                "student_remark_soft_deleted",
                extra={
                    "remark_id": str(remark.id),
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.successResponse(
                data={"id": str(remark.id)},
                description="Student remark deleted successfully.",
            )

        except Exception:
            application_logger.exception(
                "student_remark_soft_delete_failed",
                extra={
                    "remark_id": str(remark.id),
                    "school_id": str(school.id),
                    "user_id": str(request.user.id),
                },
            )

            return CustomResponse.errorResponse(
                description="Unable to delete student remark."
            )
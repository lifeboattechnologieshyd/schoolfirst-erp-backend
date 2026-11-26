from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.curriculum.models import Curriculum, CurriculumCategory, CurriculumSubject, CurriculumLesson, \
    CurriculumLessonPage, CurriculumPageContent
from apps.vocabbee.models import Grades
from shared.mixins import CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger



import logging

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated




def get_active_record(model, record_id):
    return model.objects.filter(
        id=record_id,
        is_deleted=False
    ).first()


def validate_required_fields(data, fields):
    for field in fields:
        if data.get(field) in (None, ""):
            return f"{field.replace('_', ' ').title()} is required."

    return None


def validate_parent(model, parent_id):
    if not parent_id:
        return None

    return model.objects.filter(
        id=parent_id,
        is_deleted=False
    ).first()


def create_record(model, data):
    with transaction.atomic():
        return model.objects.create(**data)


def update_record(obj, data):
    with transaction.atomic():
        for field, value in data.items():
            setattr(obj, field, value)

        obj.save()

    return obj


def soft_delete_record(obj):
    obj.is_deleted = True
    obj.save(update_fields=["is_deleted"])


class CurriculumListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.view"

    def get(self, request):
        try:
            grade_id = request.query_params.get("grade_id")
            search = request.query_params.get("search")

            queryset = Curriculum.objects.filter(
                is_active=True,
                is_deleted=False
            ).prefetch_related("grades").order_by("serial_number")

            if grade_id:
                queryset = queryset.filter(
                    grades__id=grade_id,
                    grades__is_active=True
                ).distinct()

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(description__icontains=search)
                )

            data = []

            for obj in queryset:
                grade_data = []

                for grade in obj.grades.filter(is_active=True):
                    grade_data.append({
                        "id": str(grade.id),
                        "name": grade.name,
                        "sort_order": grade.sort_order
                    })

                data.append({
                    "id": str(obj.id),
                    "title": obj.title,
                    "description": obj.description,
                    "grades": grade_data,
                    "thumbnail_image": obj.thumbnail_image,
                    "serial_number": obj.serial_number,
                    "is_active": obj.is_active,
                    "created_at": obj.created_at,
                })

            return CustomResponse.successResponse(
                data=data,
                total=len(data),
                description="Curriculums fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculums"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch curriculums."
            )


class CurriculumCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.create"

    def post(self, request):
        try:
            data = request.data

            error = validate_required_fields(
                data, ["title", "grade_ids"]
            )
            if error:
                return CustomResponse.errorResponse(
                    description=error
                )

            grade_ids = data.get("grade_ids")

            if not isinstance(grade_ids, list) or not grade_ids:
                return CustomResponse.errorResponse(
                    description="Please provide at least one grade."
                )

            grade_ids = list(set(grade_ids))

            grades = Grades.objects.filter(
                id__in=grade_ids,
                is_active=True
            )

            if grades.count() != len(grade_ids):
                return CustomResponse.errorResponse(
                    description="One or more invalid grade IDs."
                )

            curriculum = Curriculum.objects.create(
                title=data.get("title"),
                description=data.get("description"),
                thumbnail_image=data.get("thumbnail_image"),
                serial_number=data.get("serial_number", 1),
                is_active=data.get("is_active", True)
            )

            curriculum.grades.set(grades)

            grade_data = [
                {
                    "id": str(grade.id),
                    "name": grade.name
                }
                for grade in grades
            ]

            return CustomResponse.successResponse(
                data={
                    "id": str(curriculum.id),
                    "title": curriculum.title,
                    "grades": grade_data
                },
                description="Curriculum created successfully."
            )

        except Exception:
            application_logger.exception(
                "Error creating curriculum"
            )
            return CustomResponse.errorResponse(
                description="Unable to create curriculum."
            )

class CurriculumUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.update"

    def put(self, request, curriculum_id):
        try:
            curriculum = get_active_record(
                Curriculum, curriculum_id
            )

            if not curriculum:
                return CustomResponse.errorResponse(
                    description="Curriculum not found."
                )

            data = request.data

            allowed_fields = [
                "title",
                "description",
                "thumbnail_image",
                "serial_number",
                "is_active"
            ]

            for field in allowed_fields:
                if field in data:
                    setattr(
                        curriculum,
                        field,
                        data.get(field)
                    )

            if "grade_ids" in data:

                grade_ids = data.get("grade_ids")

                if not isinstance(grade_ids, list):
                    return CustomResponse.errorResponse(
                        description="Grade IDs must be a list."
                    )

                grade_ids = list(set(grade_ids))

                grades = Grades.objects.filter(
                    id__in=grade_ids,
                    is_active=True
                )

                if grades.count() != len(grade_ids):
                    return CustomResponse.errorResponse(
                        description="One or more invalid grade IDs."
                    )

                curriculum.grades.set(grades)

            curriculum.save()

            grade_data = [
                {
                    "id": str(grade.id),
                    "name": grade.name
                }
                for grade in curriculum.grades.filter(
                    is_active=True
                )
            ]

            return CustomResponse.successResponse(
                data={
                    "id": str(curriculum.id),
                    "title": curriculum.title,
                    "grades": grade_data
                },
                description="Curriculum updated successfully."
            )

        except Exception:
            application_logger.exception(
                "Error updating curriculum"
            )
            return CustomResponse.errorResponse(
                description="Unable to update curriculum."
            )

class CurriculumDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.delete"

    def delete(self, request, curriculum_id):
        try:
            curriculum = get_active_record(
                Curriculum, curriculum_id
            )

            if not curriculum:
                return CustomResponse.errorResponse(
                    description="Curriculum not found."
                )

            soft_delete_record(curriculum)

            return CustomResponse.successResponse(
                data={},
                description="Curriculum deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "Error deleting curriculum"
            )
            return CustomResponse.errorResponse(
                description="Unable to delete curriculum."
            )



class CurriculumCategoryListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.category.view"

    def get(self, request):
        try:
            queryset = CurriculumCategory.objects.filter(
                is_deleted=False
            ).select_related("curriculum")

            curriculum_id = request.query_params.get(
                "curriculum_id"
            )
            search = request.query_params.get("search")

            if curriculum_id:
                queryset = queryset.filter(
                    curriculum_id=curriculum_id
                )

            if search:
                queryset = queryset.filter(
                    name__icontains=search
                )

            queryset = queryset.order_by("serial_number")

            data = [
                {
                    "id": str(obj.id),
                    "curriculum_id": str(obj.curriculum_id),
                    "curriculum": obj.curriculum.title,
                    "name": obj.name,
                    "description": obj.description,
                    "thumbnail_image": obj.thumbnail_image,
                    "serial_number": obj.serial_number,
                    "is_active": obj.is_active,
                }
                for obj in queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                total=queryset.count(),
                description="Categories fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculum categories"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch categories."
            )


class CurriculumCategoryCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.category.create"

    def post(self, request):
        try:
            data = request.data

            error = validate_required_fields(
                data, ["curriculum_id", "name"]
            )
            if error:
                return CustomResponse.errorResponse(
                    description=error
                )

            curriculum = validate_parent(
                Curriculum, data.get("curriculum_id")
            )

            if not curriculum:
                return CustomResponse.errorResponse(
                    description="Curriculum not found."
                )

            category = CurriculumCategory.objects.create(
                curriculum=curriculum,
                name=data.get("name"),
                description=data.get("description"),
                thumbnail_image=data.get("thumbnail_image"),
                serial_number=data.get("serial_number", 1),
                is_active=data.get("is_active", True)
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "curriculum_id": str(curriculum.id),
                    "name": category.name,
                },
                description="Category created successfully."
            )

        except Exception:
            application_logger.exception(
                "Error creating curriculum category"
            )
            return CustomResponse.errorResponse(
                description="Unable to create category."
            )



class CurriculumCategoryUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.category.update"

    def put(self, request, category_id):
        try:
            category = get_active_record(
                CurriculumCategory, category_id
            )

            if not category:
                return CustomResponse.errorResponse(
                    description="Category not found."
                )

            data = request.data

            if "curriculum_id" in data:
                curriculum = validate_parent(
                    Curriculum, data.get("curriculum_id")
                )
                if not curriculum:
                    return CustomResponse.errorResponse(
                        description="Curriculum not found."
                    )
                category.curriculum = curriculum

            for field in [
                "name",
                "description",
                "thumbnail_image",
                "serial_number",
                "is_active",
            ]:
                if field in data:
                    setattr(category, field, data.get(field))

            category.save()

            return CustomResponse.successResponse(
                data={
                    "id": str(category.id),
                    "name": category.name,
                },
                description="Category updated successfully."
            )

        except Exception:
            application_logger.exception(
                "Error updating curriculum category"
            )
            return CustomResponse.errorResponse(
                description="Unable to update category."
            )



class CurriculumCategoryDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.category.delete"

    def delete(self, request, category_id):
        try:
            category = get_active_record(
                CurriculumCategory, category_id
            )

            if not category:
                return CustomResponse.errorResponse(
                    description="Category not found."
                )

            soft_delete_record(category)

            return CustomResponse.successResponse(
                data={},
                description="Category deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "Error deleting curriculum category"
            )
            return CustomResponse.errorResponse(
                description="Unable to delete category."
            )



class CurriculumSubjectListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.subject.view"

    def get(self, request):
        try:
            queryset = CurriculumSubject.objects.filter(
                is_deleted=False
            ).select_related(
                "curriculum",
                "grade"
            )

            curriculum_id = request.query_params.get("curriculum_id")
            grade_id = request.query_params.get("grade_id")
            search = request.query_params.get("search")

            if curriculum_id:
                queryset = queryset.filter(
                    curriculum_id=curriculum_id
                )

            if grade_id:
                queryset = queryset.filter(
                    grade_id=grade_id
                )

            if search:
                queryset = queryset.filter(
                    name__icontains=search
                )

            queryset = queryset.order_by("serial_number")

            data = [
                {
                    "id": str(obj.id),
                    "curriculum_id": str(obj.curriculum_id),
                    "curriculum": obj.curriculum.title,
                    "grade_id": str(obj.grade_id),
                    "grade": obj.grade.name,
                    "name": obj.name,
                    "description": obj.description,
                    "thumbnail_image": obj.thumbnail_image,
                    "total_lessons": obj.total_lessons,
                    "serial_number": obj.serial_number,
                    "is_active": obj.is_active,
                    "created_at": obj.created_at,
                }
                for obj in queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                total=len(data),
                description="Subjects fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculum subjects"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch subjects."
            )


class CurriculumSubjectCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.subject.create"

    def post(self, request):
        try:
            data = request.data

            error = validate_required_fields(
                data,
                ["curriculum_id", "grade_id", "name"]
            )

            if error:
                return CustomResponse.errorResponse(
                    description=error
                )

            curriculum = validate_parent(
                Curriculum,
                data.get("curriculum_id")
            )

            if not curriculum:
                return CustomResponse.errorResponse(
                    description="Curriculum not found."
                )

            grade = Grades.objects.filter(
                id=data.get("grade_id"),
                is_active=True
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            if not curriculum.grades.filter(
                id=grade.id,
                is_active=True
            ).exists():
                return CustomResponse.errorResponse(
                    description="Selected grade is not assigned to this curriculum."
                )

            subject = CurriculumSubject.objects.create(
                curriculum=curriculum,
                grade=grade,
                name=data.get("name"),
                description=data.get("description"),
                thumbnail_image=data.get("thumbnail_image"),
                serial_number=data.get("serial_number", 1),
                is_active=data.get("is_active", True)
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(subject.id),
                    "curriculum_id": str(curriculum.id),
                    "grade_id": str(grade.id),
                    "grade": grade.name,
                    "name": subject.name,
                },
                description="Subject created successfully."
            )

        except Exception:
            application_logger.exception(
                "Error creating curriculum subject"
            )
            return CustomResponse.errorResponse(
                description="Unable to create subject."
            )


class CurriculumSubjectUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.subject.update"

    def put(self, request, subject_id):
        try:
            subject = get_active_record(
                CurriculumSubject,
                subject_id
            )

            if not subject:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            data = request.data

            curriculum = subject.curriculum
            grade = subject.grade

            if "curriculum_id" in data:
                curriculum = validate_parent(
                    Curriculum,
                    data.get("curriculum_id")
                )

                if not curriculum:
                    return CustomResponse.errorResponse(
                        description="Curriculum not found."
                    )

            if "grade_id" in data:
                grade = Grades.objects.filter(
                    id=data.get("grade_id"),
                    is_active=True
                ).first()

                if not grade:
                    return CustomResponse.errorResponse(
                        description="Grade not found."
                    )

            if not curriculum.grades.filter(
                id=grade.id,
                is_active=True
            ).exists():
                return CustomResponse.errorResponse(
                    description="Selected grade is not assigned to this curriculum."
                )

            subject.curriculum = curriculum
            subject.grade = grade

            for field in [
                "name",
                "description",
                "thumbnail_image",
                "serial_number",
                "is_active",
            ]:
                if field in data:
                    setattr(
                        subject,
                        field,
                        data.get(field)
                    )

            subject.save()

            return CustomResponse.successResponse(
                data={
                    "id": str(subject.id),
                    "curriculum_id": str(subject.curriculum_id),
                    "grade_id": str(subject.grade_id),
                    "grade": subject.grade.name,
                    "name": subject.name,
                },
                description="Subject updated successfully."
            )

        except Exception:
            application_logger.exception(
                "Error updating curriculum subject"
            )
            return CustomResponse.errorResponse(
                description="Unable to update subject."
            )


class CurriculumSubjectDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.subject.delete"

    def delete(self, request, subject_id):
        try:
            subject = get_active_record(
                CurriculumSubject, subject_id
            )

            if not subject:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            soft_delete_record(subject)

            return CustomResponse.successResponse(
                data={},
                description="Subject deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "Error deleting curriculum subject"
            )
            return CustomResponse.errorResponse(
                description="Unable to delete subject."
            )



class CurriculumLessonListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.lesson.view"

    def get(self, request):
        try:
            queryset = CurriculumLesson.objects.filter(
                is_deleted=False
            ).select_related(
                "subject",
                "subject__curriculum",
                "grade"
            )

            subject_id = request.query_params.get("subject_id")
            grade_id = request.query_params.get("grade_id")
            status = request.query_params.get("status")
            search = request.query_params.get("search")

            if subject_id:
                queryset = queryset.filter(
                    subject_id=subject_id
                )

            if grade_id:
                queryset = queryset.filter(
                    grade_id=grade_id
                )

            if status:
                queryset = queryset.filter(
                    status=status
                )

            if search:
                queryset = queryset.filter(
                    title__icontains=search
                )

            total = queryset.count()

            queryset = queryset.order_by("serial_number")

            data = [
                {
                    "id": str(lesson.id),
                    "subject_id": str(lesson.subject_id),
                    "subject": lesson.subject.name,
                    "grade_id": str(lesson.grade_id),
                    "grade": lesson.grade.name,
                    "curriculum_name":lesson.subject.curriculum.title,
                    "title": lesson.title,
                    "description": lesson.description,
                    "thumbnail_image": lesson.thumbnail_image,
                    "estimated_duration": lesson.estimated_duration,
                    "total_pages": lesson.total_pages,
                    "serial_number": lesson.serial_number,
                    "status": lesson.status,
                    "is_active": lesson.is_active,
                    "created_at":lesson.created_at,
                }
                for lesson in queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Lessons fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculum lessons"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch lessons."
            )


class CurriculumLessonCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.lesson.create"

    def post(self, request):
        try:
            data = request.data

            error = validate_required_fields(
                data,
                ["subject_id", "grade_id", "title"]
            )

            if error:
                return CustomResponse.errorResponse(
                    description=error
                )

            subject = validate_parent(
                CurriculumSubject,
                data.get("subject_id")
            )

            if not subject:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            grade = validate_parent(
                Grades,
                data.get("grade_id")
            )

            if not grade:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            lesson = CurriculumLesson.objects.create(
                subject=subject,
                grade=grade,
                title=data.get("title"),
                description=data.get("description"),
                thumbnail_image=data.get("thumbnail_image"),
                estimated_duration=data.get("estimated_duration", 0),
                total_pages=0,
                serial_number=data.get("serial_number", 1),
                status=data.get("status", "DRAFT"),
                is_active=data.get("is_active", True)
            )

            # Update total lessons count
            subject.total_lessons = subject.lessons.filter(
                is_deleted=False
            ).count()

            subject.save(update_fields=["total_lessons"])

            return CustomResponse.successResponse(
                data={
                    "id": str(lesson.id),
                    "subject_id": str(subject.id),
                    "subject": subject.name,
                    "grade_id": str(grade.id),
                    "grade": grade.name,
                    "title": lesson.title,
                    "description": lesson.description,
                    "thumbnail_image": lesson.thumbnail_image,
                    "estimated_duration": lesson.estimated_duration,
                    "total_pages": lesson.total_pages,
                    "serial_number": lesson.serial_number,
                    "status": lesson.status,
                    "is_active": lesson.is_active,
                    "total_lessons": subject.total_lessons,
                },
                description="Lesson created successfully."
            )

        except Exception:
            application_logger.exception(
                "Error creating curriculum lesson"
            )
            return CustomResponse.errorResponse(
                description="Unable to create lesson."
            )

class CurriculumLessonUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.lesson.update"

    def put(self, request, lesson_id):
        try:
            lesson = get_active_record(
                CurriculumLesson,
                lesson_id
            )

            if not lesson:
                return CustomResponse.errorResponse(
                    description="Lesson not found."
                )

            data = request.data

            if "subject_id" in data:
                subject = validate_parent(
                    CurriculumSubject,
                    data.get("subject_id")
                )

                if not subject:
                    return CustomResponse.errorResponse(
                        description="Subject not found."
                    )

                lesson.subject = subject

            if "grade_id" in data:
                grade = validate_parent(
                    Grades,
                    data.get("grade_id")
                )

                if not grade:
                    return CustomResponse.errorResponse(
                        description="Grade not found."
                    )

                lesson.grade = grade

            allowed_fields = [
                "title",
                "description",
                "thumbnail_image",
                "estimated_duration",
                "serial_number",
                "status",
                "is_active",
            ]

            for field in allowed_fields:
                if field in data:
                    setattr(
                        lesson,
                        field,
                        data.get(field)
                    )

            lesson.save()

            return CustomResponse.successResponse(
                data={
                    "id": str(lesson.id),
                    "subject_id": str(lesson.subject_id),
                    "subject": lesson.subject.name,
                    "grade_id": str(lesson.grade_id),
                    "grade": lesson.grade.name,
                    "title": lesson.title,
                    "description": lesson.description,
                    "thumbnail_image": lesson.thumbnail_image,
                    "estimated_duration": lesson.estimated_duration,
                    "total_pages": lesson.total_pages,
                    "serial_number": lesson.serial_number,
                    "status": lesson.status,
                    "is_active": lesson.is_active,
                },
                description="Lesson updated successfully."
            )

        except Exception:
            application_logger.exception(
                "Error updating curriculum lesson"
            )
            return CustomResponse.errorResponse(
                description="Unable to update lesson."
            )

class CurriculumLessonDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.lesson.delete"

    def delete(self, request, lesson_id):
        try:
            lesson = get_active_record(
                CurriculumLesson, lesson_id
            )

            if not lesson:
                return CustomResponse.errorResponse(
                    description="Lesson not found."
                )

            soft_delete_record(lesson)

            return CustomResponse.successResponse(
                data={},
                description="Lesson deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "Error deleting curriculum lesson"
            )
            return CustomResponse.errorResponse(
                description="Unable to delete lesson."
            )



class CurriculumLessonPageListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.page.view"

    def get(self, request, lesson_id):
        try:
            lesson = get_active_record(
                CurriculumLesson, lesson_id
            )

            if not lesson:
                return CustomResponse.errorResponse(
                    description="Lesson not found."
                )

            queryset = CurriculumLessonPage.objects.filter(
                lesson=lesson,
                is_deleted=False
            ).order_by("serial_number")

            data = [
                {
                    "id": str(obj.id),
                    "lesson_id": str(obj.lesson_id),
                    "title": obj.title,
                    "serial_number": obj.serial_number,
                    "is_active": obj.is_active,
                }
                for obj in queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                total=queryset.count(),
                description="Lesson pages fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculum lesson pages"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch lesson pages."
            )



class CurriculumLessonPageCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.page.create"

    def post(self, request, lesson_id):
        try:
            lesson = get_active_record(
                CurriculumLesson, lesson_id
            )

            if not lesson:
                return CustomResponse.errorResponse(
                    description="Lesson not found."
                )

            error = validate_required_fields(
                request.data, ["serial_number"]
            )
            if error:
                return CustomResponse.errorResponse(
                    description=error
                )

            page = CurriculumLessonPage.objects.create(
                lesson=lesson,
                title=request.data.get("title"),
                serial_number=request.data.get("serial_number"),
                is_active=request.data.get("is_active", True)
            )

            # Update total pages in lesson
            lesson.total_pages = CurriculumLessonPage.objects.filter(
                lesson=lesson,
                is_deleted=False
            ).count()
            lesson.save(update_fields=["total_pages"])

            return CustomResponse.successResponse(
                data={
                    "id": str(page.id),
                    "lesson_id": str(lesson.id),
                    "title": page.title,
                    "serial_number": page.serial_number,
                },
                description="Lesson page created successfully."
            )

        except Exception:
            application_logger.exception(
                "Error creating curriculum lesson page"
            )
            return CustomResponse.errorResponse(
                description="Unable to create lesson page."
            )



class CurriculumLessonPageUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.page.update"

    def put(self, request, page_id):
        try:
            page = get_active_record(
                CurriculumLessonPage, page_id
            )

            if not page:
                return CustomResponse.errorResponse(
                    description="Lesson page not found."
                )

            data = request.data

            if "lesson_id" in data:
                lesson = validate_parent(
                    CurriculumLesson, data.get("lesson_id")
                )
                if not lesson:
                    return CustomResponse.errorResponse(
                        description="Lesson not found."
                    )
                page.lesson = lesson

            for field in ["title", "serial_number", "is_active"]:
                if field in data:
                    setattr(page, field, data.get(field))

            page.save()

            return CustomResponse.successResponse(
                data={
                    "id": str(page.id),
                    "title": page.title,
                    "serial_number": page.serial_number,
                },
                description="Lesson page updated successfully."
            )

        except Exception:
            application_logger.exception(
                "Error updating curriculum lesson page"
            )
            return CustomResponse.errorResponse(
                description="Unable to update lesson page."
            )



class CurriculumLessonPageDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.page.delete"

    def delete(self, request, page_id):
        try:
            page = get_active_record(
                CurriculumLessonPage, page_id
            )

            if not page:
                return CustomResponse.errorResponse(
                    description="Lesson page not found."
                )

            lesson = page.lesson

            soft_delete_record(page)

            lesson.total_pages = CurriculumLessonPage.objects.filter(
                lesson=lesson,
                is_deleted=False
            ).count()
            lesson.save(update_fields=["total_pages"])

            return CustomResponse.successResponse(
                data={},
                description="Lesson page deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "Error deleting curriculum lesson page"
            )
            return CustomResponse.errorResponse(
                description="Unable to delete lesson page."
            )



class CurriculumPageContentListAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.content.view"

    def get(self, request, page_id):
        try:
            page = get_active_record(
                CurriculumLessonPage, page_id
            )

            if not page:
                return CustomResponse.errorResponse(
                    description="Lesson page not found."
                )

            queryset = CurriculumPageContent.objects.filter(
                page=page,
                is_deleted=False
            ).order_by("serial_number")

            data = [
                {
                    "id": str(obj.id),
                    "page_id": str(obj.page_id),
                    "content_type": obj.content_type,
                    "title": obj.title,
                    "content": obj.content,
                    "media_url": obj.media_url,
                    "metadata": obj.metadata,
                    "serial_number": obj.serial_number,
                    "is_active": obj.is_active,
                }
                for obj in queryset
            ]

            return CustomResponse.successResponse(
                data=data,
                total=queryset.count(),
                description="Page contents fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculum page contents"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch page contents."
            )



class CurriculumPageContentCreateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.content.create"

    def post(self, request, page_id):
        try:
            page = get_active_record(
                CurriculumLessonPage, page_id
            )

            if not page:
                return CustomResponse.errorResponse(
                    description="Lesson page not found."
                )

            data = request.data

            error = validate_required_fields(
                data, ["content_type", "serial_number"]
            )
            if error:
                return CustomResponse.errorResponse(
                    description=error
                )

            valid_types = [
                choice[0]
                for choice in CurriculumPageContent.ContentType.choices
            ]

            content_type = data.get("content_type")

            if content_type not in valid_types:
                return CustomResponse.errorResponse(
                    description="Invalid content type."
                )

            content = CurriculumPageContent.objects.create(
                page=page,
                content_type=content_type,
                title=data.get("title"),
                content=data.get("content"),
                media_url=data.get("media_url"),
                metadata=data.get("metadata", {}),
                serial_number=data.get("serial_number"),
                is_active=data.get("is_active", True)
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(content.id),
                    "page_id": str(page.id),
                    "content_type": content.content_type,
                    "serial_number": content.serial_number,
                },
                description="Page content created successfully."
            )

        except Exception:
            application_logger.exception(
                "Error creating curriculum page content"
            )
            return CustomResponse.errorResponse(
                description="Unable to create page content."
            )



class CurriculumPageContentUpdateAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.content.update"

    def put(self, request, content_id):
        try:
            content = get_active_record(
                CurriculumPageContent, content_id
            )

            if not content:
                return CustomResponse.errorResponse(
                    description="Page content not found."
                )

            data = request.data

            if "page_id" in data:
                page = validate_parent(
                    CurriculumLessonPage, data.get("page_id")
                )

                if not page:
                    return CustomResponse.errorResponse(
                        description="Lesson page not found."
                    )

                content.page = page

            if "content_type" in data:
                valid_types = [
                    choice[0]
                    for choice in CurriculumPageContent.ContentType.choices
                ]

                if data.get("content_type") not in valid_types:
                    return CustomResponse.errorResponse(
                        description="Invalid content type."
                    )

            allowed_fields = [
                "content_type",
                "title",
                "content",
                "media_url",
                "metadata",
                "serial_number",
                "is_active",
            ]

            for field in allowed_fields:
                if field in data:
                    setattr(content, field, data.get(field))

            content.save()

            return CustomResponse.successResponse(
                data={
                    "id": str(content.id),
                    "content_type": content.content_type,
                    "serial_number": content.serial_number,
                },
                description="Page content updated successfully."
            )

        except Exception:
            application_logger.exception(
                "Error updating curriculum page content"
            )
            return CustomResponse.errorResponse(
                description="Unable to update page content."
            )



class CurriculumPageContentDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "curriculum.content.delete"

    def delete(self, request, content_id):
        try:
            content = get_active_record(
                CurriculumPageContent, content_id
            )

            if not content:
                return CustomResponse.errorResponse(
                    description="Page content not found."
                )

            soft_delete_record(content)

            return CustomResponse.successResponse(
                data={},
                description="Page content deleted successfully."
            )

        except Exception:
            application_logger.exception(
                "Error deleting curriculum page content"
            )
            return CustomResponse.errorResponse(
                description="Unable to delete page content."
            )

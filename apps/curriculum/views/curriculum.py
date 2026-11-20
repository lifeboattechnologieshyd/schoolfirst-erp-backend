from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.curriculum.models import Curriculum, CurriculumCategory, CurriculumSubject, CurriculumLesson
from apps.vocabbee.models import Grades
from shared.mixins import CustomResponse


class CurriculumListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        grade_id = request.query_params.get("grade_id")

        if not grade_id:
            return CustomResponse.errorResponse(
                description="Grade ID is required."
            )

        if not Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).exists():
            return CustomResponse.errorResponse(
                description="Invalid grade ID."
            )

        curriculums = Curriculum.objects.filter(
            grade_id=grade_id,
            is_active=True,
            is_deleted=False
        ).order_by("serial_number")

        data = []

        for curriculum in curriculums:
            data.append({
                "id": curriculum.id,
                "title": curriculum.title,
                "description": curriculum.description,
                "grade_id": curriculum.grade_id,
                "grade_name": curriculum.grade.name,
                "thumbnail_image": curriculum.thumbnail_image,
                "serial_number": curriculum.serial_number
            })

        return CustomResponse.successResponse(
            data=data,
            description="Curriculums fetched successfully."
        )

class CurriculumCategoryListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, curriculum_id):

        curriculum = Curriculum.objects.filter(
            id=curriculum_id,
            is_active=True,
            is_deleted=False
        ).first()

        if not curriculum:
            return CustomResponse.errorResponse(
                description="Curriculum not found."
            )

        categories = CurriculumCategory.objects.filter(
            curriculum_id=curriculum_id,
            is_active=True,
            is_deleted=False
        ).order_by("serial_number")

        data = []

        for category in categories:
            data.append({
                "id": category.id,
                "curriculum_id": category.curriculum_id,
                "name": category.name,
                "description": category.description,
                "thumbnail_image": category.thumbnail_image,
                "serial_number": category.serial_number
            })

        return CustomResponse.successResponse(
            data=data,
            description="Categories fetched successfully."
        )

class CurriculumSubjectListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, category_id):

        category = CurriculumCategory.objects.filter(
            id=category_id,
            is_active=True,
            is_deleted=False,
            curriculum__is_active=True,
            curriculum__is_deleted=False
        ).first()

        if not category:
            return CustomResponse.errorResponse(
                description="Category not found."
            )

        subjects = CurriculumSubject.objects.filter(
            category_id=category_id,
            is_active=True,
            is_deleted=False
        ).order_by("serial_number")

        data = []

        for subject in subjects:
            data.append({
                "id": subject.id,
                "category_id": subject.category_id,
                "name": subject.name,
                "description": subject.description,
                "thumbnail_image": subject.thumbnail_image,
                "total_lessons": subject.total_lessons,
                "serial_number": subject.serial_number
            })

        return CustomResponse.successResponse(
            data=data,
            description="Subjects fetched successfully."
        )

class CurriculumLessonListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, subject_id):

        subject = CurriculumSubject.objects.filter(
            id=subject_id,
            is_active=True,
            is_deleted=False,
            category__is_active=True,
            category__is_deleted=False,
            category__curriculum__is_active=True,
            category__curriculum__is_deleted=False
        ).first()

        if not subject:
            return CustomResponse.errorResponse(
                description="Subject not found."
            )

        lessons = CurriculumLesson.objects.filter(
            subject_id=subject_id,
            status="PUBLISHED",
            is_active=True,
            is_deleted=False
        ).order_by("serial_number")

        data = []

        for lesson in lessons:
            data.append({
                "id": lesson.id,
                "subject_id": lesson.subject_id,
                "title": lesson.title,
                "description": lesson.description,
                "thumbnail_image": lesson.thumbnail_image,
                "estimated_duration": lesson.estimated_duration,
                "total_pages": lesson.total_pages,
                "serial_number": lesson.serial_number
            })

        return CustomResponse.successResponse(
            data=data,
            description="Lessons fetched successfully."
        )

class CurriculumLessonDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):

        lesson = CurriculumLesson.objects.filter(
            id=lesson_id,
            status="PUBLISHED",
            is_active=True,
            is_deleted=False,
            subject__is_active=True,
            subject__is_deleted=False,
            subject__category__is_active=True,
            subject__category__is_deleted=False,
            subject__category__curriculum__is_active=True,
            subject__category__curriculum__is_deleted=False
        ).prefetch_related(
            "pages__contents"
        ).first()

        if not lesson:
            return CustomResponse.errorResponse(
                description="Lesson not found."
            )

        pages_data = []

        pages = lesson.pages.filter(
            is_active=True,
            is_deleted=False
        ).order_by("serial_number")

        for page in pages:

            contents_data = []

            contents = page.contents.filter(
                is_active=True,
                is_deleted=False
            ).order_by("serial_number")

            for content in contents:
                contents_data.append({
                    "id": content.id,
                    "content_type": content.content_type,
                    "title": content.title,
                    "content": content.content,
                    "media_url": content.media_url,
                    "metadata": content.metadata,
                    "serial_number": content.serial_number
                })

            pages_data.append({
                "id": page.id,
                "title": page.title,
                "serial_number": page.serial_number,
                "contents": contents_data
            })

        data = {
            "id": lesson.id,
            "subject_id": lesson.subject_id,
            "title": lesson.title,
            "description": lesson.description,
            "thumbnail_image": lesson.thumbnail_image,
            "estimated_duration": lesson.estimated_duration,
            "total_pages": lesson.total_pages,
            "pages": pages_data
        }

        return CustomResponse.successResponse(
            data=data,
            description="Lesson details fetched successfully."
        )
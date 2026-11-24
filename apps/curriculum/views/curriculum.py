from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.curriculum.models import Curriculum, CurriculumCategory, CurriculumSubject, CurriculumLesson
from apps.vocabbee.models import Grades
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


class CurriculumListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            grade_id = request.query_params.get("grade_id")

            if not grade_id:
                return CustomResponse.errorResponse(
                    description="Grade ID is required."
                )

            grade = Grades.objects.filter(
                id=grade_id,
                is_active=True
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Invalid grade ID."
                )

            curriculums = Curriculum.objects.filter(
                grades__id=grade_id,
                is_active=True,
                is_deleted=False
            ).prefetch_related(
                "grades"
            ).distinct().order_by(
                "serial_number"
            )

            data = []

            for curriculum in curriculums:

                grades_data = [
                    {
                        "id": str(grade.id),
                        "name": grade.name
                    }
                    for grade in curriculum.grades.filter(
                        is_active=True
                    )
                ]

                data.append({
                    "id": str(curriculum.id),
                    "title": curriculum.title,
                    "description": curriculum.description,
                    "grades": grades_data,
                    "thumbnail_image": curriculum.thumbnail_image,
                    "serial_number": curriculum.serial_number
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

    def get(self, request, curriculum_id):
        try:
            grade_id = request.query_params.get("grade_id")

            if not grade_id:
                return CustomResponse.errorResponse(
                    description="Grade ID is required."
                )

            curriculum = Curriculum.objects.filter(
                id=curriculum_id,
                is_active=True,
                is_deleted=False
            ).first()

            if not curriculum:
                return CustomResponse.errorResponse(
                    description="Curriculum not found."
                )

            grade = Grades.objects.filter(
                id=grade_id,
                is_active=True
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Invalid grade ID."
                )

            subjects = CurriculumSubject.objects.filter(
                curriculum_id=curriculum_id,
                grade_id=grade_id,
                curriculum__is_active=True,
                curriculum__is_deleted=False,
                grade__is_active=True,
                is_active=True,
                is_deleted=False
            ).select_related(
                "curriculum",
                "grade"
            ).order_by(
                "serial_number"
            )

            data = []

            for subject in subjects:
                data.append({
                    "id": str(subject.id),
                    "curriculum_id": str(subject.curriculum_id),
                    "grade_id": str(subject.grade_id),
                    "grade_name": subject.grade.name,
                    "name": subject.name,
                    "description": subject.description,
                    "thumbnail_image": subject.thumbnail_image,
                    "total_lessons": subject.total_lessons,
                    "serial_number": subject.serial_number
                })

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


class CurriculumLessonListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, subject_id):
        try:
            grade_id = request.query_params.get("grade_id")

            if not grade_id:
                return CustomResponse.errorResponse(
                    description="Grade ID is required."
                )

            subject = CurriculumSubject.objects.filter(
                id=subject_id,
                is_active=True,
                is_deleted=False,
                curriculum__is_active=True,
                curriculum__is_deleted=False
            ).first()

            if not subject:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            grade = Grades.objects.filter(
                id=grade_id,
                is_active=True
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Invalid grade ID."
                )

            lessons = CurriculumLesson.objects.filter(
                subject_id=subject_id,
                grade_id=grade_id,
                status=CurriculumLesson.Status.PUBLISHED,
                is_active=True,
                is_deleted=False,
                grade__is_active=True
            ).select_related(
                "subject",
                "grade"
            ).order_by(
                "serial_number"
            )

            data = []

            for lesson in lessons:
                data.append({
                    "id": str(lesson.id),
                    "subject_id": str(lesson.subject_id),
                    "subject_name": lesson.subject.name,
                    "grade_id": str(lesson.grade_id),
                    "grade_name": lesson.grade.name,
                    "title": lesson.title,
                    "description": lesson.description,
                    "thumbnail_image": lesson.thumbnail_image,
                    "estimated_duration": lesson.estimated_duration,
                    "total_pages": lesson.total_pages,
                    "serial_number": lesson.serial_number
                })

            return CustomResponse.successResponse(
                data=data,
                total=len(data),
                description="Lessons fetched successfully."
            )

        except Exception:
            application_logger.exception(
                "Error fetching curriculum lessons"
            )
            return CustomResponse.errorResponse(
                description="Unable to fetch lessons."
            )


class CurriculumLessonDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        try:

            lesson = CurriculumLesson.objects.filter(
                id=lesson_id,
                status=CurriculumLesson.Status.PUBLISHED,
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
        except Exception as e:
            application_logger.exception(
                "Error fetching curriculum lessons"
            )
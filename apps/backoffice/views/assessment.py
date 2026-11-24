import io
import uuid
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.assessment.models import (
    Assessment,
    AssessmentLesson,
    AssessmentQuestion,
    AssessmentQuestionImport,
    AssessmentQuestionMapping,
    AssessmentQuestionOption,
)
from apps.curriculum.models import Curriculum, CurriculumLesson, CurriculumSubject
from apps.vocabbee.models import Grades
from shared.mixins import CustomPageNumberPagination, CustomResponse
from shared.permissions import HasPermission
from shared.utils.logger import application_logger
from shared.utils.s3 import save_to_s3


# =====================================================================
#  CONSTANTS
# =====================================================================
OPTION_LABELS = ["A", "B", "C", "D"]

TITLE_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 120
HINT_MAX_LENGTH = 80
OPTION_MAX_LENGTH = 500
TIME_LIMIT_MAX_MINUTES = 600

COVER_IMAGE_MAX_SIZE = 2 * 1024 * 1024  # 2 MB
COVER_IMAGE_EXTENSIONS = ("png", "jpg", "jpeg")

IMPORT_FILE_MAX_SIZE = 5 * 1024 * 1024  # 5 MB
IMPORT_MAX_ROWS = 1000
IMPORT_FILE_EXTENSIONS = ("csv", "xlsx")
IMPORT_REQUIRED_COLUMNS = [
    "question",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct",
    "level",
]
IMPORT_OPTIONAL_COLUMNS = [
    "hint",
    "explanation",
]


# =====================================================================
#  HELPERS
# =====================================================================
def parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def get_file_extension(file_name):
    if not file_name or "." not in file_name:
        return ""

    return file_name.rsplit(".", 1)[1].lower()


def get_active_grade(grade_id):
    return Grades.objects.filter(
        id=grade_id,
        is_active=True,
        is_deleted=False,
    ).first()


def get_active_curriculum(curriculum_id):
    return Curriculum.objects.filter(
        id=curriculum_id,
        is_active=True,
        is_deleted=False,
    ).first()


def get_active_subject(subject_id):
    return CurriculumSubject.objects.filter(
        id=subject_id,
        is_active=True,
        is_deleted=False,
    ).first()


def get_active_lesson(lesson_id):
    return CurriculumLesson.objects.filter(
        id=lesson_id,
        is_active=True,
        is_deleted=False,
    ).first()


def parse_time_limit(value):
    """
    Returns (time_limit, error).
    None / "" means "No limit".
    """
    if value in (None, ""):
        return None, None

    try:
        time_limit = int(value)
    except (ValueError, TypeError):
        return None, "Time limit must be a number of minutes."

    if time_limit <= 0 or time_limit > TIME_LIMIT_MAX_MINUTES:
        return None, f"Time limit must be between 1 and {TIME_LIMIT_MAX_MINUTES} minutes."

    return time_limit, None


def parse_marks(value):
    """
    Returns (marks, error).
    """
    if value in (None, ""):
        return Decimal("1"), None

    try:
        marks = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None, "Marks must be a number."

    if marks <= 0 or marks > Decimal("100"):
        return None, "Marks must be greater than 0 and at most 100."

    return marks, None


def parse_level(value):
    """
    Accepts BASIC / Basic / basic.
    """
    if not isinstance(value, str) or not value.strip():
        return None

    level = value.strip().upper()

    if level not in AssessmentQuestion.Level.values:
        return None

    return level


def resolve_cover_image(request):
    """
    Accepts either an uploaded file (multipart "cover_image")
    or an already uploaded URL string.

    Returns (cover_image_url, error).
    """
    cover_file = request.FILES.get("cover_image")

    if cover_file:
        extension = get_file_extension(cover_file.name)

        if extension not in COVER_IMAGE_EXTENSIONS:
            return None, "Cover image must be PNG or JPG."

        if cover_file.size > COVER_IMAGE_MAX_SIZE:
            return None, "Cover image cannot exceed 2 MB."

        return save_to_s3("assessments/covers", cover_file), None

    cover_image = request.data.get("cover_image")

    if cover_image in (None, ""):
        return None, None

    if not isinstance(cover_image, str) or len(cover_image) > 500:
        return None, "Invalid cover image."

    return cover_image.strip(), None


def validate_options(options):
    """
    Options must be exactly 4 (A-D).
    At most one option can be correct.
    A question can be saved without a correct answer
    (shown as "No correct answer"), but it cannot be published.

    Returns (cleaned_options, error).
    """
    if not isinstance(options, list) or len(options) != len(OPTION_LABELS):
        return None, "Exactly 4 options (A, B, C, D) are required."

    cleaned = {}

    for option in options:
        if not isinstance(option, dict):
            return None, "Each option must be an object."

        label = option.get("label")
        option_text = option.get("option_text")
        is_correct = option.get("is_correct", False)

        if not isinstance(label, str) or label.strip().upper() not in OPTION_LABELS:
            return None, "Option label must be A, B, C or D."

        label = label.strip().upper()

        if label in cleaned:
            return None, f"Option {label} is repeated."

        if not isinstance(option_text, str) or not option_text.strip():
            return None, f"Option {label} text is required."

        if len(option_text.strip()) > OPTION_MAX_LENGTH:
            return None, f"Option {label} cannot exceed {OPTION_MAX_LENGTH} characters."

        if not isinstance(is_correct, bool):
            return None, f"Option {label} is_correct must be a boolean."

        cleaned[label] = {
            "label": label,
            "option_text": option_text.strip(),
            "is_correct": is_correct,
        }

    correct_count = sum(1 for option in cleaned.values() if option["is_correct"])

    if correct_count > 1:
        return None, "Only one option can be marked as correct."

    return [cleaned[label] for label in OPTION_LABELS], None


def save_question_options(question, options):
    """
    Creates or updates the 4 options of a question by label.
    Must be called inside transaction.atomic().
    """
    existing_options = {
        option.label: option
        for option in AssessmentQuestionOption.objects.filter(
            question=question,
        )
    }

    for serial_number, option_data in enumerate(options, start=1):
        option = existing_options.get(option_data["label"])

        if option is None:
            AssessmentQuestionOption.objects.create(
                question=question,
                label=option_data["label"],
                option_text=option_data["option_text"],
                is_correct=option_data["is_correct"],
                serial_number=serial_number,
            )
            continue

        option.option_text = option_data["option_text"]
        option.is_correct = option_data["is_correct"]
        option.serial_number = serial_number
        option.save()


def refresh_assessment_totals(assessment):
    """
    Recalculates total_questions and total_marks.
    """
    mappings = AssessmentQuestionMapping.objects.filter(
        assessment=assessment,
        question__is_deleted=False,
    )

    totals = mappings.aggregate(
        total_questions=Count("id"),
        total_marks=Sum("question__marks"),
    )

    assessment.total_questions = totals["total_questions"] or 0
    assessment.total_marks = totals["total_marks"] or Decimal("0")
    assessment.save(
        update_fields=[
            "total_questions",
            "total_marks",
            "updated_at",
            "updated_by",
        ]
    )


def question_has_correct_answer(question):
    return any(option.is_correct for option in question.options.all())


def get_correct_label(question):
    for option in question.options.all():
        if option.is_correct:
            return option.label

    return None


def build_question_data(question):
    """
    Expects question with select_related("grade", "subject", "lesson")
    and prefetch_related("options").
    """
    options = [
        {
            "id": str(option.id),
            "label": option.label,
            "option_text": option.option_text,
            "is_correct": option.is_correct,
        }
        for option in question.options.all()
    ]

    return {
        "id": str(question.id),
        "question": question.question,
        "question_type": question.question_type,
        "level": question.level,
        "marks": question.marks,
        "hint": question.hint,
        "explanation": question.explanation,
        "image": question.image,
        "is_active": question.is_active,
        "grade": {
            "id": str(question.grade_id),
            "name": question.grade.name,
        },
        "subject": {
            "id": str(question.subject_id),
            "name": question.subject.name,
        },
        "lesson": {
            "id": str(question.lesson_id),
            "title": question.lesson.title,
        } if question.lesson_id else None,
        "options": options,
        "correct_option": get_correct_label(question),
        "has_correct_answer": question_has_correct_answer(question),
        "created_at": question.created_at,
        "updated_at": question.updated_at,
    }


def build_assessment_summary(assessment):
    """
    Expects assessment with select_related("curriculum", "grade", "subject").
    """
    return {
        "id": str(assessment.id),
        "title": assessment.title,
        "description": assessment.description,
        "cover_image": assessment.cover_image,
        "time_limit": assessment.time_limit,
        "total_questions": assessment.total_questions,
        "total_marks": assessment.total_marks,
        "status": assessment.status,
        "curriculum": {
            "id": str(assessment.curriculum_id),
            "title": assessment.curriculum.title,
        },
        "grade": {
            "id": str(assessment.grade_id),
            "name": assessment.grade.name,
        },
        "subject": {
            "id": str(assessment.subject_id),
            "name": assessment.subject.name,
        },
        "published_at": assessment.published_at,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
    }


def get_assessment_checklist(assessment, mappings):
    """
    Step 3 checklist + Step 4 review.
    mappings: list of AssessmentQuestionMapping with question + options prefetched.
    """
    lessons_count = AssessmentLesson.objects.filter(
        assessment=assessment,
    ).count()

    questions_without_correct = []
    questions_without_hint = 0
    difficulty_mix = {level: 0 for level in AssessmentQuestion.Level.values}

    for index, mapping in enumerate(mappings, start=1):
        question = mapping.question

        if not question_has_correct_answer(question):
            questions_without_correct.append(index)

        if not question.hint:
            questions_without_hint += 1

        difficulty_mix[question.level] = difficulty_mix.get(question.level, 0) + 1

    errors = []
    warnings = []

    if lessons_count == 0:
        errors.append("Select at least one lesson.")

    if not mappings:
        errors.append("Add at least one question.")

    for serial_number in questions_without_correct:
        errors.append(f"Question {serial_number} has no correct answer.")

    if questions_without_hint:
        warnings.append(f"{questions_without_hint} questions have no hint.")

    return {
        "lessons_count": lessons_count,
        "questions_count": len(mappings),
        "questions_without_correct_answer": questions_without_correct,
        "questions_without_hint": questions_without_hint,
        "difficulty_mix": difficulty_mix,
        "errors": errors,
        "warnings": warnings,
        "can_publish": not errors,
    }


def get_editable_assessment(assessment_id):
    """
    Returns (assessment, error_response).
    Only DRAFT assessments can be edited.
    """
    assessment_uuid = parse_uuid(assessment_id)

    if assessment_uuid is None:
        return None, CustomResponse.errorResponse(
            description="Invalid assessment ID."
        )

    assessment = Assessment.objects.filter(
        id=assessment_uuid,
    ).select_related(
        "curriculum",
        "grade",
        "subject",
    ).first()

    if assessment is None:
        return None, CustomResponse.errorResponse(
            description="Assessment not found.",
            status=status.HTTP_404_NOT_FOUND,
        )

    if assessment.status != Assessment.Status.DRAFT:
        return None, CustomResponse.errorResponse(
            description="Only draft assessments can be edited. Move it back to draft first."
        )

    return assessment, None


# =====================================================================
#  STEP 1 - CREATE ASSESSMENT (DETAILS)
# =====================================================================
class AssessmentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.create"

    def post(self, request):
        curriculum_id = request.data.get("curriculum_id")
        grade_id = request.data.get("grade_id")
        subject_id = request.data.get("subject_id")
        title = request.data.get("title")
        description = request.data.get("description")

        # -----------------------------------------
        # Required fields
        # -----------------------------------------
        required_fields = {
            "curriculum_id": curriculum_id,
            "grade_id": grade_id,
            "subject_id": subject_id,
            "title": title,
        }

        for field, value in required_fields.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        curriculum_uuid = parse_uuid(curriculum_id)
        grade_uuid = parse_uuid(grade_id)
        subject_uuid = parse_uuid(subject_id)

        if not curriculum_uuid or not grade_uuid or not subject_uuid:
            return CustomResponse.errorResponse(
                description="Invalid program, grade, or subject ID."
            )

        # -----------------------------------------
        # Title / description
        # -----------------------------------------
        if not isinstance(title, str) or len(title.strip()) > TITLE_MAX_LENGTH:
            return CustomResponse.errorResponse(
                description=f"Title must be text with at most {TITLE_MAX_LENGTH} characters."
            )

        title = title.strip()

        if description is not None and not isinstance(description, str):
            return CustomResponse.errorResponse(
                description="Description must be text."
            )

        description = description.strip() if description else None

        if description and len(description) > DESCRIPTION_MAX_LENGTH:
            return CustomResponse.errorResponse(
                description=f"Description cannot exceed {DESCRIPTION_MAX_LENGTH} characters."
            )

        # -----------------------------------------
        # Time limit
        # -----------------------------------------
        time_limit, error = parse_time_limit(request.data.get("time_limit"))

        if error:
            return CustomResponse.errorResponse(description=error)

        try:
            # -----------------------------------------
            # Program / grade / subject
            # -----------------------------------------
            curriculum = get_active_curriculum(curriculum_uuid)

            if curriculum is None:
                return CustomResponse.errorResponse(
                    description="Program not found."
                )

            grade = get_active_grade(grade_uuid)

            if grade is None:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            subject = get_active_subject(subject_uuid)

            if subject is None:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            if subject.curriculum_id != curriculum.id:
                return CustomResponse.errorResponse(
                    description="The selected subject does not belong to this program."
                )

            if subject.grade_id != grade.id:
                return CustomResponse.errorResponse(
                    description="The selected subject does not belong to this grade."
                )

            # -----------------------------------------
            # Duplicate title
            # -----------------------------------------
            if Assessment.objects.filter(
                grade=grade,
                subject=subject,
                title__iexact=title,
            ).exists():
                return CustomResponse.errorResponse(
                    description=f"A test with this title already exists for {grade.name} {subject.name}."
                )

            # -----------------------------------------
            # Cover image
            # -----------------------------------------
            cover_image, error = resolve_cover_image(request)

            if error:
                return CustomResponse.errorResponse(description=error)

            with transaction.atomic():
                assessment = Assessment.objects.create(
                    curriculum=curriculum,
                    grade=grade,
                    subject=subject,
                    title=title,
                    description=description,
                    cover_image=cover_image,
                    time_limit=time_limit,
                    status=Assessment.Status.DRAFT,
                )

            application_logger.info(
                "assessment_created",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=build_assessment_summary(assessment),
                description="Assessment saved as draft.",
            )

        except Exception:
            application_logger.exception(
                "assessment_create_failed",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to create assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  LIBRARY - LIST ASSESSMENTS
# =====================================================================
class AssessmentListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.view"

    def get(self, request):
        try:
            assessments = Assessment.objects.select_related(
                "curriculum",
                "grade",
                "subject",
            ).annotate(
                lessons_count=Count(
                    "assessment_lessons",
                    filter=Q(assessment_lessons__is_deleted=False),
                    distinct=True,
                ),
            ).order_by(
                "-created_at",
            )

            # -----------------------------------------
            # Filters
            # -----------------------------------------
            uuid_filters = {
                "curriculum_id": request.query_params.get("curriculum_id"),
                "grade_id": request.query_params.get("grade_id"),
                "subject_id": request.query_params.get("subject_id"),
            }

            for field, value in uuid_filters.items():
                if not value:
                    continue

                if parse_uuid(value) is None:
                    return CustomResponse.errorResponse(
                        description=f"Invalid {field}."
                    )

                assessments = assessments.filter(**{field: value})

            status_filter = request.query_params.get("status")

            if status_filter:
                status_filter = status_filter.strip().upper()

                if status_filter not in Assessment.Status.values:
                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                assessments = assessments.filter(status=status_filter)

            search = request.query_params.get("search")

            if search and search.strip():
                search = search.strip()
                assessments = assessments.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                )

            # -----------------------------------------
            # Status counts (Library tabs)
            # -----------------------------------------
            status_counts = {value: 0 for value in Assessment.Status.values}

            for row in Assessment.objects.values("status").annotate(count=Count("id")):
                status_counts[row["status"]] = row["count"]

            # -----------------------------------------
            # Pagination
            # -----------------------------------------
            total = assessments.count()

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                assessments,
                request,
                view=self,
            )

            data = []

            for assessment in page:
                item = build_assessment_summary(assessment)
                item["lessons_count"] = assessment.lessons_count
                data.append(item)

            application_logger.info(
                "assessment_list_fetched",
                user_id=str(request.user.id),
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                status_counts=status_counts,
                description="Assessments fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_list_failed",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch assessments.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  DETAIL / STEP 4 REVIEW
# =====================================================================
class AssessmentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.view"

    def get(self, request, assessment_id):
        assessment_uuid = parse_uuid(assessment_id)

        if assessment_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid assessment ID."
            )

        try:
            assessment = Assessment.objects.filter(
                id=assessment_uuid,
            ).select_related(
                "curriculum",
                "grade",
                "subject",
            ).first()

            if assessment is None:
                return CustomResponse.errorResponse(
                    description="Assessment not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            # -----------------------------------------
            # Lessons
            # -----------------------------------------
            assessment_lessons = AssessmentLesson.objects.filter(
                assessment=assessment,
            ).select_related(
                "lesson",
            ).order_by(
                "lesson__serial_number",
            )

            lesson_ids = [item.lesson_id for item in assessment_lessons]

            questions_available = AssessmentQuestion.objects.filter(
                lesson_id__in=lesson_ids,
                is_active=True,
            ).count() if lesson_ids else 0

            lessons = [
                {
                    "id": str(item.lesson_id),
                    "title": item.lesson.title,
                    "serial_number": item.lesson.serial_number,
                }
                for item in assessment_lessons
            ]

            # -----------------------------------------
            # Questions
            # -----------------------------------------
            mappings = list(
                AssessmentQuestionMapping.objects.filter(
                    assessment=assessment,
                    question__is_deleted=False,
                ).select_related(
                    "question",
                    "question__grade",
                    "question__subject",
                    "question__lesson",
                ).prefetch_related(
                    "question__options",
                ).order_by(
                    "serial_number",
                    "created_at",
                )
            )

            questions = []

            for index, mapping in enumerate(mappings, start=1):
                question_data = build_question_data(mapping.question)
                question_data["mapping_id"] = str(mapping.id)
                question_data["serial_number"] = index
                questions.append(question_data)

            data = build_assessment_summary(assessment)
            data["lessons"] = lessons
            data["questions_available"] = questions_available
            data["questions"] = questions
            data["checklist"] = get_assessment_checklist(assessment, mappings)

            application_logger.info(
                "assessment_detail_fetched",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=data,
                description="Assessment fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_detail_failed",
                assessment_id=str(assessment_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 1 - UPDATE ASSESSMENT (DETAILS)
# =====================================================================
class AssessmentUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.update"

    def put(self, request, assessment_id):
        assessment, error_response = get_editable_assessment(assessment_id)

        if error_response:
            return error_response

        allowed_fields = {
            "curriculum_id",
            "grade_id",
            "subject_id",
            "title",
            "description",
            "cover_image",
            "time_limit",
        }

        request_fields = set(request.data.keys()) | set(request.FILES.keys())
        invalid_fields = request_fields - allowed_fields

        if invalid_fields:
            return CustomResponse.errorResponse(
                description=f"Invalid fields: {', '.join(sorted(invalid_fields))}."
            )

        if not request_fields:
            return CustomResponse.errorResponse(
                description="At least one field is required for update."
            )

        try:
            # -----------------------------------------
            # Program / grade / subject
            # -----------------------------------------
            curriculum = assessment.curriculum
            grade = assessment.grade
            subject = assessment.subject

            if "curriculum_id" in request.data:
                curriculum_uuid = parse_uuid(request.data.get("curriculum_id"))
                curriculum = get_active_curriculum(curriculum_uuid) if curriculum_uuid else None

                if curriculum is None:
                    return CustomResponse.errorResponse(
                        description="Program not found."
                    )

            if "grade_id" in request.data:
                grade_uuid = parse_uuid(request.data.get("grade_id"))
                grade = get_active_grade(grade_uuid) if grade_uuid else None

                if grade is None:
                    return CustomResponse.errorResponse(
                        description="Grade not found."
                    )

            if "subject_id" in request.data:
                subject_uuid = parse_uuid(request.data.get("subject_id"))
                subject = get_active_subject(subject_uuid) if subject_uuid else None

                if subject is None:
                    return CustomResponse.errorResponse(
                        description="Subject not found."
                    )

            if subject.curriculum_id != curriculum.id:
                return CustomResponse.errorResponse(
                    description="The selected subject does not belong to this program."
                )

            if subject.grade_id != grade.id:
                return CustomResponse.errorResponse(
                    description="The selected subject does not belong to this grade."
                )

            subject_changed = subject.id != assessment.subject_id

            # -----------------------------------------
            # Title
            # -----------------------------------------
            title = assessment.title

            if "title" in request.data:
                title = request.data.get("title")

                if not isinstance(title, str) or not title.strip():
                    return CustomResponse.errorResponse(
                        description="Title is required."
                    )

                title = title.strip()

                if len(title) > TITLE_MAX_LENGTH:
                    return CustomResponse.errorResponse(
                        description=f"Title cannot exceed {TITLE_MAX_LENGTH} characters."
                    )

            if Assessment.objects.filter(
                grade=grade,
                subject=subject,
                title__iexact=title,
            ).exclude(
                id=assessment.id,
            ).exists():
                return CustomResponse.errorResponse(
                    description=f"A test with this title already exists for {grade.name} {subject.name}."
                )

            # -----------------------------------------
            # Description
            # -----------------------------------------
            description = assessment.description

            if "description" in request.data:
                description = request.data.get("description")

                if description is not None and not isinstance(description, str):
                    return CustomResponse.errorResponse(
                        description="Description must be text."
                    )

                description = description.strip() if description else None

                if description and len(description) > DESCRIPTION_MAX_LENGTH:
                    return CustomResponse.errorResponse(
                        description=f"Description cannot exceed {DESCRIPTION_MAX_LENGTH} characters."
                    )

            # -----------------------------------------
            # Time limit
            # -----------------------------------------
            time_limit = assessment.time_limit

            if "time_limit" in request.data:
                time_limit, error = parse_time_limit(request.data.get("time_limit"))

                if error:
                    return CustomResponse.errorResponse(description=error)

            # -----------------------------------------
            # Cover image
            # -----------------------------------------
            cover_image = assessment.cover_image

            if "cover_image" in request.data or "cover_image" in request.FILES:
                cover_image, error = resolve_cover_image(request)

                if error:
                    return CustomResponse.errorResponse(description=error)

            with transaction.atomic():
                assessment.curriculum = curriculum
                assessment.grade = grade
                assessment.subject = subject
                assessment.title = title
                assessment.description = description
                assessment.time_limit = time_limit
                assessment.cover_image = cover_image
                assessment.save()

                # Lessons and questions belong to the old subject,
                # so clear them when the subject changes.
                if subject_changed:
                    for item in AssessmentLesson.objects.filter(assessment=assessment):
                        item.soft_delete(request.user)

                    for item in AssessmentQuestionMapping.objects.filter(assessment=assessment):
                        item.soft_delete(request.user)

                    refresh_assessment_totals(assessment)

            application_logger.info(
                "assessment_updated",
                assessment_id=str(assessment.id),
                subject_changed=subject_changed,
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=build_assessment_summary(assessment),
                description="Assessment updated successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_update_failed",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to update assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  DELETE ASSESSMENT
# =====================================================================
class AssessmentDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.delete"

    def delete(self, request, assessment_id):
        assessment_uuid = parse_uuid(assessment_id)

        if assessment_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid assessment ID."
            )

        assessment = Assessment.objects.filter(
            id=assessment_uuid,
        ).first()

        if assessment is None:
            return CustomResponse.errorResponse(
                description="Assessment not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        if assessment.status == Assessment.Status.PUBLISHED:
            return CustomResponse.errorResponse(
                description="Published assessments cannot be deleted. Archive it instead."
            )

        try:
            with transaction.atomic():
                for item in AssessmentLesson.objects.filter(assessment=assessment):
                    item.soft_delete(request.user)

                for item in AssessmentQuestionMapping.objects.filter(assessment=assessment):
                    item.soft_delete(request.user)

                assessment.soft_delete(request.user)

            application_logger.info(
                "assessment_soft_deleted",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={"id": str(assessment.id)},
                description="Assessment deleted successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_soft_delete_failed",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to delete assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 2 - LESSONS LIST (with questions in bank)
# =====================================================================
class AssessmentLessonListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.view"

    def get(self, request):
        subject_id = request.query_params.get("subject_id")

        if not subject_id:
            return CustomResponse.errorResponse(
                description="subject_id is required."
            )

        subject_uuid = parse_uuid(subject_id)

        if subject_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid subject_id."
            )

        try:
            subject = get_active_subject(subject_uuid)

            if subject is None:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            lessons = CurriculumLesson.objects.filter(
                subject=subject,
                is_active=True,
                is_deleted=False,
            ).annotate(
                questions_in_bank=Count(
                    "assessment_questions",
                    filter=Q(
                        assessment_questions__is_deleted=False,
                        assessment_questions__is_active=True,
                    ),
                ),
            ).order_by(
                "serial_number",
            )

            status_filter = request.query_params.get("status")

            if status_filter:
                status_filter = status_filter.strip().upper()

                if status_filter not in CurriculumLesson.Status.values:
                    return CustomResponse.errorResponse(
                        description="Invalid status."
                    )

                lessons = lessons.filter(status=status_filter)

            search = request.query_params.get("search")

            if search and search.strip():
                lessons = lessons.filter(title__icontains=search.strip())

            total = lessons.count()

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                lessons,
                request,
                view=self,
            )

            data = [
                {
                    "id": str(lesson.id),
                    "title": lesson.title,
                    "serial_number": lesson.serial_number,
                    "status": lesson.status,
                    "questions_in_bank": lesson.questions_in_bank,
                }
                for lesson in page
            ]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Lessons fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_lesson_list_failed",
                subject_id=str(subject_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch lessons.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 2 - SAVE SELECTED LESSONS
# =====================================================================
class AssessmentLessonUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.update"

    def put(self, request, assessment_id):
        assessment, error_response = get_editable_assessment(assessment_id)

        if error_response:
            return error_response

        lesson_ids = request.data.get("lesson_ids")

        if not isinstance(lesson_ids, list) or not lesson_ids:
            return CustomResponse.errorResponse(
                description="Select at least one lesson to continue."
            )

        lesson_uuids = []

        for lesson_id in lesson_ids:
            lesson_uuid = parse_uuid(lesson_id)

            if lesson_uuid is None:
                return CustomResponse.errorResponse(
                    description="Invalid lesson ID."
                )

            lesson_uuids.append(lesson_uuid)

        lesson_uuids = list(set(lesson_uuids))

        try:
            lessons = list(
                CurriculumLesson.objects.filter(
                    id__in=lesson_uuids,
                    subject=assessment.subject,
                    is_active=True,
                    is_deleted=False,
                )
            )

            if len(lessons) != len(lesson_uuids):
                return CustomResponse.errorResponse(
                    description="One or more lessons are invalid or do not belong to this subject."
                )

            with transaction.atomic():
                existing = {
                    item.lesson_id: item
                    for item in AssessmentLesson.objects.select_for_update().filter(
                        assessment=assessment,
                    )
                }

                selected_ids = {lesson.id for lesson in lessons}

                # Remove unselected lessons
                for lesson_id, item in existing.items():
                    if lesson_id not in selected_ids:
                        item.soft_delete(request.user)

                # Add new lessons
                for lesson in lessons:
                    if lesson.id not in existing:
                        AssessmentLesson.objects.create(
                            assessment=assessment,
                            lesson=lesson,
                        )

            questions_available = AssessmentQuestion.objects.filter(
                lesson_id__in=selected_ids,
                is_active=True,
            ).count()

            application_logger.info(
                "assessment_lessons_updated",
                assessment_id=str(assessment.id),
                lessons_count=len(lessons),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(assessment.id),
                    "lessons_selected": len(lessons),
                    "questions_available": questions_available,
                    "lessons": [
                        {
                            "id": str(lesson.id),
                            "title": lesson.title,
                        }
                        for lesson in sorted(lessons, key=lambda item: item.serial_number)
                    ],
                },
                description="Lessons saved successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_lessons_update_failed",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to save lessons.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 3 - ADD QUESTIONS FROM BANK
# =====================================================================
class AssessmentQuestionAddAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.update"

    def post(self, request, assessment_id):
        assessment, error_response = get_editable_assessment(assessment_id)

        if error_response:
            return error_response

        question_ids = request.data.get("question_ids")

        if not isinstance(question_ids, list) or not question_ids:
            return CustomResponse.errorResponse(
                description="Select at least one question."
            )

        question_uuids = []

        for question_id in question_ids:
            question_uuid = parse_uuid(question_id)

            if question_uuid is None:
                return CustomResponse.errorResponse(
                    description="Invalid question ID."
                )

            if question_uuid not in question_uuids:
                question_uuids.append(question_uuid)

        try:
            lesson_ids = list(
                AssessmentLesson.objects.filter(
                    assessment=assessment,
                ).values_list("lesson_id", flat=True)
            )

            if not lesson_ids:
                return CustomResponse.errorResponse(
                    description="Select lessons before adding questions."
                )

            questions = {
                question.id: question
                for question in AssessmentQuestion.objects.filter(
                    id__in=question_uuids,
                    lesson_id__in=lesson_ids,
                    is_active=True,
                )
            }

            if len(questions) != len(question_uuids):
                return CustomResponse.errorResponse(
                    description="One or more questions are invalid or not part of the selected lessons."
                )

            with transaction.atomic():
                # Lock the assessment while changing questions
                Assessment.objects.select_for_update().filter(
                    id=assessment.id,
                ).first()

                existing_ids = set(
                    AssessmentQuestionMapping.objects.filter(
                        assessment=assessment,
                    ).values_list("question_id", flat=True)
                )

                last_serial = AssessmentQuestionMapping.objects.filter(
                    assessment=assessment,
                ).count()

                added = 0

                # Keep the order the admin selected them in
                for question_uuid in question_uuids:
                    if question_uuid in existing_ids:
                        continue

                    last_serial += 1
                    added += 1

                    AssessmentQuestionMapping.objects.create(
                        assessment=assessment,
                        question=questions[question_uuid],
                        serial_number=last_serial,
                    )

                refresh_assessment_totals(assessment)

            application_logger.info(
                "assessment_questions_added",
                assessment_id=str(assessment.id),
                added=added,
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(assessment.id),
                    "added": added,
                    "skipped": len(question_uuids) - added,
                    "total_questions": assessment.total_questions,
                    "total_marks": assessment.total_marks,
                },
                description=f"{added} questions added.",
            )

        except Exception:
            application_logger.exception(
                "assessment_questions_add_failed",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to add questions.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 3 - REMOVE QUESTION FROM ASSESSMENT
# =====================================================================
class AssessmentQuestionRemoveAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.update"

    def delete(self, request, assessment_id, question_id):
        assessment, error_response = get_editable_assessment(assessment_id)

        if error_response:
            return error_response

        question_uuid = parse_uuid(question_id)

        if question_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid question ID."
            )

        try:
            with transaction.atomic():
                mapping = AssessmentQuestionMapping.objects.select_for_update().filter(
                    assessment=assessment,
                    question_id=question_uuid,
                ).first()

                if mapping is None:
                    return CustomResponse.errorResponse(
                        description="Question is not part of this assessment.",
                        status=status.HTTP_404_NOT_FOUND,
                    )

                mapping.soft_delete(request.user)

                # Re-number remaining questions 1..n
                remaining = AssessmentQuestionMapping.objects.filter(
                    assessment=assessment,
                ).order_by(
                    "serial_number",
                    "created_at",
                )

                for serial_number, item in enumerate(remaining, start=1):
                    if item.serial_number != serial_number:
                        item.serial_number = serial_number
                        item.save(update_fields=["serial_number", "updated_at", "updated_by"])

                refresh_assessment_totals(assessment)

            application_logger.info(
                "assessment_question_removed",
                assessment_id=str(assessment.id),
                question_id=str(question_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(assessment.id),
                    "total_questions": assessment.total_questions,
                    "total_marks": assessment.total_marks,
                },
                description="Question removed from assessment.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_remove_failed",
                assessment_id=str(assessment.id),
                question_id=str(question_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to remove question.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 3 - REORDER QUESTIONS (drag handles)
# =====================================================================
class AssessmentQuestionReorderAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.update"

    def put(self, request, assessment_id):
        assessment, error_response = get_editable_assessment(assessment_id)

        if error_response:
            return error_response

        question_ids = request.data.get("question_ids")

        if not isinstance(question_ids, list) or not question_ids:
            return CustomResponse.errorResponse(
                description="question_ids must be a list in the new order."
            )

        question_uuids = [parse_uuid(question_id) for question_id in question_ids]

        if None in question_uuids:
            return CustomResponse.errorResponse(
                description="Invalid question ID."
            )

        if len(set(question_uuids)) != len(question_uuids):
            return CustomResponse.errorResponse(
                description="Duplicate question IDs are not allowed."
            )

        try:
            with transaction.atomic():
                mappings = {
                    mapping.question_id: mapping
                    for mapping in AssessmentQuestionMapping.objects.select_for_update().filter(
                        assessment=assessment,
                    )
                }

                if set(mappings.keys()) != set(question_uuids):
                    return CustomResponse.errorResponse(
                        description="question_ids must contain every question in this assessment exactly once."
                    )

                for serial_number, question_uuid in enumerate(question_uuids, start=1):
                    mapping = mappings[question_uuid]

                    if mapping.serial_number != serial_number:
                        mapping.serial_number = serial_number
                        mapping.save(update_fields=["serial_number", "updated_at", "updated_by"])

            application_logger.info(
                "assessment_questions_reordered",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={"id": str(assessment.id)},
                description="Questions reordered successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_questions_reorder_failed",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to reorder questions.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STEP 4 - PUBLISH
# =====================================================================
class AssessmentPublishAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.publish"

    def post(self, request, assessment_id):
        assessment, error_response = get_editable_assessment(assessment_id)

        if error_response:
            return error_response

        try:
            mappings = list(
                AssessmentQuestionMapping.objects.filter(
                    assessment=assessment,
                    question__is_deleted=False,
                ).select_related(
                    "question",
                ).prefetch_related(
                    "question__options",
                ).order_by(
                    "serial_number",
                )
            )

            checklist = get_assessment_checklist(assessment, mappings)

            if not checklist["can_publish"]:
                return CustomResponse.errorResponse(
                    data=checklist,
                    description=checklist["errors"][0],
                )

            with transaction.atomic():
                refresh_assessment_totals(assessment)

                assessment.status = Assessment.Status.PUBLISHED
                assessment.published_at = timezone.now()
                assessment.save(
                    update_fields=[
                        "status",
                        "published_at",
                        "updated_at",
                        "updated_by",
                    ]
                )

            application_logger.info(
                "assessment_published",
                assessment_id=str(assessment.id),
                total_questions=assessment.total_questions,
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=build_assessment_summary(assessment),
                description="Assessment published successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_publish_failed",
                assessment_id=str(assessment.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to publish assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  STATUS CHANGE - ARCHIVE / MOVE TO DRAFT
# =====================================================================
class AssessmentStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.publish"

    ALLOWED_TRANSITIONS = {
        Assessment.Status.PUBLISHED: [Assessment.Status.ARCHIVED, Assessment.Status.DRAFT],
        Assessment.Status.ARCHIVED: [Assessment.Status.DRAFT],
        Assessment.Status.DRAFT: [Assessment.Status.ARCHIVED],
    }

    def put(self, request, assessment_id):
        assessment_uuid = parse_uuid(assessment_id)

        if assessment_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid assessment ID."
            )

        new_status = request.data.get("status")

        if not isinstance(new_status, str) or new_status.strip().upper() not in (
            Assessment.Status.ARCHIVED,
            Assessment.Status.DRAFT,
        ):
            return CustomResponse.errorResponse(
                description="Status must be ARCHIVED or DRAFT. Use the publish API to publish."
            )

        new_status = new_status.strip().upper()

        try:
            with transaction.atomic():
                assessment = Assessment.objects.select_for_update().filter(
                    id=assessment_uuid,
                ).first()

                if assessment is None:
                    return CustomResponse.errorResponse(
                        description="Assessment not found.",
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if new_status not in self.ALLOWED_TRANSITIONS.get(assessment.status, []):
                    return CustomResponse.errorResponse(
                        description=f"Cannot change status from {assessment.status} to {new_status}."
                    )

                assessment.status = new_status
                assessment.save(
                    update_fields=[
                        "status",
                        "updated_at",
                        "updated_by",
                    ]
                )

            application_logger.info(
                "assessment_status_updated",
                assessment_id=str(assessment.id),
                status=new_status,
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(assessment.id),
                    "status": assessment.status,
                },
                description="Assessment status updated successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_status_update_failed",
                assessment_id=str(assessment_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to update assessment status.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  QUESTION BANK - CREATE QUESTION
#  Pass assessment_id to also add it to a draft assessment
#  ("New question" button in Step 3)
# =====================================================================
class AssessmentQuestionBankCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.create"

    def post(self, request):
        grade_id = request.data.get("grade_id")
        subject_id = request.data.get("subject_id")
        lesson_id = request.data.get("lesson_id")
        assessment_id = request.data.get("assessment_id")
        question_text = request.data.get("question")
        hint = request.data.get("hint")
        explanation = request.data.get("explanation")
        image = request.data.get("image")

        # -----------------------------------------
        # Required fields
        # -----------------------------------------
        required_fields = {
            "grade_id": grade_id,
            "subject_id": subject_id,
            "question": question_text,
            "level": request.data.get("level"),
            "options": request.data.get("options"),
        }

        for field, value in required_fields.items():
            if value is None or (isinstance(value, str) and not value.strip()):
                return CustomResponse.errorResponse(
                    description=f"{field} is required."
                )

        grade_uuid = parse_uuid(grade_id)
        subject_uuid = parse_uuid(subject_id)

        if not grade_uuid or not subject_uuid:
            return CustomResponse.errorResponse(
                description="Invalid grade or subject ID."
            )

        lesson_uuid = None

        if lesson_id not in (None, ""):
            lesson_uuid = parse_uuid(lesson_id)

            if lesson_uuid is None:
                return CustomResponse.errorResponse(
                    description="Invalid lesson ID."
                )

        if not isinstance(question_text, str) or not question_text.strip():
            return CustomResponse.errorResponse(
                description="Question is required."
            )

        level = parse_level(request.data.get("level"))

        if level is None:
            return CustomResponse.errorResponse(
                description="Level must be Basic, Intermediate or Advanced."
            )

        marks, error = parse_marks(request.data.get("marks"))

        if error:
            return CustomResponse.errorResponse(description=error)

        if hint is not None and not isinstance(hint, str):
            return CustomResponse.errorResponse(
                description="Hint must be text."
            )

        hint = hint.strip() if hint else None

        if hint and len(hint) > HINT_MAX_LENGTH:
            return CustomResponse.errorResponse(
                description=f"Hint cannot exceed {HINT_MAX_LENGTH} characters."
            )

        if explanation is not None and not isinstance(explanation, str):
            return CustomResponse.errorResponse(
                description="Explanation must be text."
            )

        explanation = explanation.strip() if explanation else None

        if image is not None and (not isinstance(image, str) or len(image) > 500):
            return CustomResponse.errorResponse(
                description="Invalid image."
            )

        options, error = validate_options(request.data.get("options"))

        if error:
            return CustomResponse.errorResponse(description=error)

        try:
            # -----------------------------------------
            # Grade / subject / lesson
            # -----------------------------------------
            grade = get_active_grade(grade_uuid)

            if grade is None:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            subject = get_active_subject(subject_uuid)

            if subject is None:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            if subject.grade_id != grade.id:
                return CustomResponse.errorResponse(
                    description="The selected subject does not belong to this grade."
                )

            lesson = None

            if lesson_uuid:
                lesson = get_active_lesson(lesson_uuid)

                if lesson is None or lesson.subject_id != subject.id:
                    return CustomResponse.errorResponse(
                        description="Lesson not found for this subject."
                    )

            # -----------------------------------------
            # Optional - add to draft assessment
            # -----------------------------------------
            assessment = None

            if assessment_id not in (None, ""):
                assessment, error_response = get_editable_assessment(assessment_id)

                if error_response:
                    return error_response

                if assessment.subject_id != subject.id:
                    return CustomResponse.errorResponse(
                        description="Question subject does not match the assessment subject."
                    )

                if lesson is None:
                    return CustomResponse.errorResponse(
                        description="Lesson is required when adding a question to an assessment."
                    )

                if not AssessmentLesson.objects.filter(
                    assessment=assessment,
                    lesson=lesson,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="Lesson is not selected in this assessment."
                    )

            with transaction.atomic():
                question = AssessmentQuestion.objects.create(
                    grade=grade,
                    subject=subject,
                    lesson=lesson,
                    question=question_text.strip(),
                    level=level,
                    marks=marks,
                    hint=hint,
                    explanation=explanation,
                    image=image.strip() if image else None,
                )

                save_question_options(question, options)

                if assessment:
                    last_serial = AssessmentQuestionMapping.objects.filter(
                        assessment=assessment,
                    ).count()

                    AssessmentQuestionMapping.objects.create(
                        assessment=assessment,
                        question=question,
                        serial_number=last_serial + 1,
                    )

                    refresh_assessment_totals(assessment)

            question = AssessmentQuestion.objects.select_related(
                "grade",
                "subject",
                "lesson",
            ).prefetch_related(
                "options",
            ).get(
                id=question.id,
            )

            application_logger.info(
                "assessment_question_created",
                question_id=str(question.id),
                assessment_id=str(assessment.id) if assessment else None,
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=build_question_data(question),
                description="Question created successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_create_failed",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to create question.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  QUESTION BANK - LIST
#  Also used by "Add from bank" drawer:
#  ?assessment_id=<id> hides questions already in that test
# =====================================================================
class AssessmentQuestionBankListAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.view"

    def get(self, request):
        try:
            questions = AssessmentQuestion.objects.select_related(
                "grade",
                "subject",
                "lesson",
            ).prefetch_related(
                "options",
            ).annotate(
                used_in_count=Count(
                    "assessment_mappings",
                    filter=Q(
                        assessment_mappings__is_deleted=False,
                        assessment_mappings__assessment__is_deleted=False,
                    ),
                    distinct=True,
                ),
            ).order_by(
                "-created_at",
            )

            # -----------------------------------------
            # UUID filters
            # -----------------------------------------
            uuid_filters = {
                "grade_id": request.query_params.get("grade_id"),
                "subject_id": request.query_params.get("subject_id"),
                "lesson_id": request.query_params.get("lesson_id"),
            }

            for field, value in uuid_filters.items():
                if not value:
                    continue

                if parse_uuid(value) is None:
                    return CustomResponse.errorResponse(
                        description=f"Invalid {field}."
                    )

                questions = questions.filter(**{field: value})

            # Comma separated lesson IDs (selected lessons in Step 2)
            lesson_ids = request.query_params.get("lesson_ids")

            if lesson_ids:
                lesson_uuids = [parse_uuid(value) for value in lesson_ids.split(",") if value.strip()]

                if None in lesson_uuids:
                    return CustomResponse.errorResponse(
                        description="Invalid lesson_ids."
                    )

                questions = questions.filter(lesson_id__in=lesson_uuids)

            # -----------------------------------------
            # Add from bank - hide questions already in test
            # -----------------------------------------
            assessment_id = request.query_params.get("assessment_id")

            if assessment_id:
                assessment_uuid = parse_uuid(assessment_id)

                if assessment_uuid is None:
                    return CustomResponse.errorResponse(
                        description="Invalid assessment_id."
                    )

                assessment_lesson_ids = AssessmentLesson.objects.filter(
                    assessment_id=assessment_uuid,
                ).values_list("lesson_id", flat=True)

                existing_question_ids = AssessmentQuestionMapping.objects.filter(
                    assessment_id=assessment_uuid,
                ).values_list("question_id", flat=True)

                questions = questions.filter(
                    lesson_id__in=assessment_lesson_ids,
                    is_active=True,
                ).exclude(
                    id__in=existing_question_ids,
                )

            # -----------------------------------------
            # Level / active / correct answer / search
            # -----------------------------------------
            level = request.query_params.get("level")

            if level:
                level = parse_level(level)

                if level is None:
                    return CustomResponse.errorResponse(
                        description="Level must be Basic, Intermediate or Advanced."
                    )

                questions = questions.filter(level=level)

            is_active = request.query_params.get("is_active")

            if is_active is not None:
                if is_active.lower() not in ("true", "false"):
                    return CustomResponse.errorResponse(
                        description="is_active must be true or false."
                    )

                questions = questions.filter(is_active=is_active.lower() == "true")

            has_correct_answer = request.query_params.get("has_correct_answer")

            if has_correct_answer is not None:
                if has_correct_answer.lower() not in ("true", "false"):
                    return CustomResponse.errorResponse(
                        description="has_correct_answer must be true or false."
                    )

                correct_question_ids = AssessmentQuestionOption.objects.filter(
                    is_correct=True,
                ).values_list("question_id", flat=True)

                if has_correct_answer.lower() == "true":
                    questions = questions.filter(id__in=correct_question_ids)
                else:
                    questions = questions.exclude(id__in=correct_question_ids)

            search = request.query_params.get("search")

            if search and search.strip():
                questions = questions.filter(question__icontains=search.strip())

            # -----------------------------------------
            # Pagination
            # -----------------------------------------
            total = questions.count()

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                questions,
                request,
                view=self,
            )

            data = []

            for question in page:
                item = build_question_data(question)
                item["used_in_count"] = question.used_in_count
                data.append(item)

            application_logger.info(
                "assessment_question_list_fetched",
                user_id=str(request.user.id),
                total=total,
            )

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Questions fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_list_failed",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch questions.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  QUESTION BANK - DETAIL (Question editor)
# =====================================================================
class AssessmentQuestionBankDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.view"

    def get(self, request, question_id):
        question_uuid = parse_uuid(question_id)

        if question_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid question ID."
            )

        try:
            question = AssessmentQuestion.objects.filter(
                id=question_uuid,
            ).select_related(
                "grade",
                "subject",
                "lesson",
            ).prefetch_related(
                "options",
            ).first()

            if question is None:
                return CustomResponse.errorResponse(
                    description="Question not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            used_in = AssessmentQuestionMapping.objects.filter(
                question=question,
                assessment__is_deleted=False,
            ).select_related(
                "assessment",
            )

            data = build_question_data(question)
            data["used_in"] = [
                {
                    "id": str(mapping.assessment_id),
                    "title": mapping.assessment.title,
                    "status": mapping.assessment.status,
                }
                for mapping in used_in
            ]

            return CustomResponse.successResponse(
                data=data,
                description="Question fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_detail_failed",
                question_id=str(question_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch question.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  QUESTION BANK - UPDATE (Question editor)
# =====================================================================
class AssessmentQuestionBankUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.update"

    def put(self, request, question_id):
        question_uuid = parse_uuid(question_id)

        if question_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid question ID."
            )

        allowed_fields = {
            "lesson_id",
            "question",
            "level",
            "marks",
            "hint",
            "explanation",
            "image",
            "is_active",
            "options",
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
                question = AssessmentQuestion.objects.select_for_update().filter(
                    id=question_uuid,
                ).first()

                if question is None:
                    return CustomResponse.errorResponse(
                        description="Question not found.",
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Questions inside a published test are locked,
                # so students' results stay consistent.
                if AssessmentQuestionMapping.objects.filter(
                    question=question,
                    assessment__status=Assessment.Status.PUBLISHED,
                    assessment__is_deleted=False,
                ).exists():
                    return CustomResponse.errorResponse(
                        description="This question is used in a published assessment and cannot be edited."
                    )

                # -----------------------------------------
                # Lesson
                # -----------------------------------------
                if "lesson_id" in request.data:
                    lesson_id = request.data.get("lesson_id")

                    if lesson_id in (None, ""):
                        question.lesson = None
                    else:
                        lesson_uuid = parse_uuid(lesson_id)
                        lesson = get_active_lesson(lesson_uuid) if lesson_uuid else None

                        if lesson is None or lesson.subject_id != question.subject_id:
                            return CustomResponse.errorResponse(
                                description="Lesson not found for this subject."
                            )

                        question.lesson = lesson

                # -----------------------------------------
                # Question text
                # -----------------------------------------
                if "question" in request.data:
                    question_text = request.data.get("question")

                    if not isinstance(question_text, str) or not question_text.strip():
                        return CustomResponse.errorResponse(
                            description="Question is required."
                        )

                    question.question = question_text.strip()

                # -----------------------------------------
                # Level / marks
                # -----------------------------------------
                if "level" in request.data:
                    level = parse_level(request.data.get("level"))

                    if level is None:
                        return CustomResponse.errorResponse(
                            description="Level must be Basic, Intermediate or Advanced."
                        )

                    question.level = level

                marks_changed = False

                if "marks" in request.data:
                    marks, error = parse_marks(request.data.get("marks"))

                    if error:
                        return CustomResponse.errorResponse(description=error)

                    marks_changed = marks != question.marks
                    question.marks = marks

                # -----------------------------------------
                # Hint / explanation / image
                # -----------------------------------------
                if "hint" in request.data:
                    hint = request.data.get("hint")

                    if hint is not None and not isinstance(hint, str):
                        return CustomResponse.errorResponse(
                            description="Hint must be text."
                        )

                    hint = hint.strip() if hint else None

                    if hint and len(hint) > HINT_MAX_LENGTH:
                        return CustomResponse.errorResponse(
                            description=f"Hint cannot exceed {HINT_MAX_LENGTH} characters."
                        )

                    question.hint = hint

                if "explanation" in request.data:
                    explanation = request.data.get("explanation")

                    if explanation is not None and not isinstance(explanation, str):
                        return CustomResponse.errorResponse(
                            description="Explanation must be text."
                        )

                    question.explanation = explanation.strip() if explanation else None

                if "image" in request.data:
                    image = request.data.get("image")

                    if image is not None and (not isinstance(image, str) or len(image) > 500):
                        return CustomResponse.errorResponse(
                            description="Invalid image."
                        )

                    question.image = image.strip() if image else None

                if "is_active" in request.data:
                    is_active = request.data.get("is_active")

                    if not isinstance(is_active, bool):
                        return CustomResponse.errorResponse(
                            description="is_active must be a boolean."
                        )

                    question.is_active = is_active

                # -----------------------------------------
                # Options
                # -----------------------------------------
                options = None

                if "options" in request.data:
                    options, error = validate_options(request.data.get("options"))

                    if error:
                        return CustomResponse.errorResponse(description=error)

                question.save()

                if options is not None:
                    save_question_options(question, options)

                # Keep draft assessment totals in sync
                if marks_changed:
                    draft_assessments = Assessment.objects.filter(
                        question_mappings__question=question,
                        question_mappings__is_deleted=False,
                        status=Assessment.Status.DRAFT,
                    ).distinct()

                    for assessment in draft_assessments:
                        refresh_assessment_totals(assessment)

            question = AssessmentQuestion.objects.select_related(
                "grade",
                "subject",
                "lesson",
            ).prefetch_related(
                "options",
            ).get(
                id=question.id,
            )

            application_logger.info(
                "assessment_question_updated",
                question_id=str(question.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=build_question_data(question),
                description="Question updated successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_update_failed",
                question_id=str(question_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to update question.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  QUESTION BANK - DELETE
# =====================================================================
class AssessmentQuestionBankDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.delete"

    def delete(self, request, question_id):
        question_uuid = parse_uuid(question_id)

        if question_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid question ID."
            )

        question = AssessmentQuestion.objects.filter(
            id=question_uuid,
        ).first()

        if question is None:
            return CustomResponse.errorResponse(
                description="Question not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        if AssessmentQuestionMapping.objects.filter(
            question=question,
            assessment__status=Assessment.Status.PUBLISHED,
            assessment__is_deleted=False,
        ).exists():
            return CustomResponse.errorResponse(
                description="This question is used in a published assessment and cannot be deleted."
            )

        try:
            with transaction.atomic():
                affected_assessments = list(
                    Assessment.objects.filter(
                        question_mappings__question=question,
                        question_mappings__is_deleted=False,
                    ).distinct()
                )

                for mapping in AssessmentQuestionMapping.objects.filter(question=question):
                    mapping.soft_delete(request.user)

                for option in AssessmentQuestionOption.objects.filter(question=question):
                    option.soft_delete(request.user)

                question.soft_delete(request.user)

                for assessment in affected_assessments:
                    refresh_assessment_totals(assessment)

            application_logger.info(
                "assessment_question_soft_deleted",
                question_id=str(question.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={"id": str(question.id)},
                description="Question deleted successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_soft_delete_failed",
                question_id=str(question.id),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to delete question.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  BULK UPLOAD - DOWNLOAD CSV TEMPLATE
# =====================================================================
class AssessmentQuestionImportTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.import"

    def get(self, request):
        columns = IMPORT_REQUIRED_COLUMNS + IMPORT_OPTIONAL_COLUMNS

        sample = pd.DataFrame(
            [
                {
                    "question": "Which part of the plant absorbs water?",
                    "option_a": "Leaf",
                    "option_b": "Root",
                    "option_c": "Flower",
                    "option_d": "Fruit",
                    "correct": "B",
                    "level": "Basic",
                    "hint": "It grows under the soil.",
                    "explanation": "Roots absorb water and minerals from the soil.",
                }
            ],
            columns=columns,
        )

        response = HttpResponse(
            sample.to_csv(index=False),
            content_type="text/csv",
        )
        response["Content-Disposition"] = 'attachment; filename="assessment_questions_template.csv"'

        return response


# =====================================================================
#  BULK UPLOAD - STEP 1 + 2 (UPLOAD & VALIDATE)
# =====================================================================
class AssessmentQuestionImportValidateAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.import"

    def post(self, request):
        grade_id = request.data.get("grade_id")
        subject_id = request.data.get("subject_id")
        lesson_id = request.data.get("lesson_id")
        upload_file = request.FILES.get("file")

        # -----------------------------------------
        # Target
        # -----------------------------------------
        if not grade_id or not subject_id:
            return CustomResponse.errorResponse(
                description="Grade and subject are required."
            )

        grade_uuid = parse_uuid(grade_id)
        subject_uuid = parse_uuid(subject_id)

        if not grade_uuid or not subject_uuid:
            return CustomResponse.errorResponse(
                description="Invalid grade or subject ID."
            )

        lesson_uuid = None

        if lesson_id not in (None, ""):
            lesson_uuid = parse_uuid(lesson_id)

            if lesson_uuid is None:
                return CustomResponse.errorResponse(
                    description="Invalid lesson ID."
                )

        # -----------------------------------------
        # File
        # -----------------------------------------
        if upload_file is None:
            return CustomResponse.errorResponse(
                description="Please upload a CSV or XLSX file."
            )

        extension = get_file_extension(upload_file.name)

        if extension not in IMPORT_FILE_EXTENSIONS:
            return CustomResponse.errorResponse(
                description="Only CSV or XLSX files are allowed."
            )

        if upload_file.size > IMPORT_FILE_MAX_SIZE:
            return CustomResponse.errorResponse(
                description="File cannot exceed 5 MB."
            )

        try:
            grade = get_active_grade(grade_uuid)

            if grade is None:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            subject = get_active_subject(subject_uuid)

            if subject is None or subject.grade_id != grade.id:
                return CustomResponse.errorResponse(
                    description="Subject not found for this grade."
                )

            lesson = None

            if lesson_uuid:
                lesson = get_active_lesson(lesson_uuid)

                if lesson is None or lesson.subject_id != subject.id:
                    return CustomResponse.errorResponse(
                        description="Lesson not found for this subject."
                    )

            # -----------------------------------------
            # Read file
            # -----------------------------------------
            file_bytes = upload_file.read()

            try:
                if extension == "csv":
                    dataframe = pd.read_csv(
                        io.BytesIO(file_bytes),
                        dtype=str,
                        keep_default_na=False,
                    )
                else:
                    dataframe = pd.read_excel(
                        io.BytesIO(file_bytes),
                        dtype=str,
                        keep_default_na=False,
                        engine="openpyxl",
                    )
            except Exception:
                return CustomResponse.errorResponse(
                    description="Unable to read the file. Please use the CSV template."
                )

            dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]

            missing_columns = [
                column
                for column in IMPORT_REQUIRED_COLUMNS
                if column not in dataframe.columns
            ]

            if missing_columns:
                return CustomResponse.errorResponse(
                    description=f"Missing columns: {', '.join(missing_columns)}."
                )

            if dataframe.empty:
                return CustomResponse.errorResponse(
                    description="The file has no rows."
                )

            if len(dataframe) > IMPORT_MAX_ROWS:
                return CustomResponse.errorResponse(
                    description=f"The file cannot have more than {IMPORT_MAX_ROWS} rows."
                )

            # -----------------------------------------
            # Validate rows
            # -----------------------------------------
            existing_questions = set(
                question.strip().lower()
                for question in AssessmentQuestion.objects.filter(
                    grade=grade,
                    subject=subject,
                ).values_list("question", flat=True)
            )

            seen_questions = set()
            parsed_rows = []
            errors = []

            for index, row in dataframe.iterrows():
                row_number = index + 2  # header is row 1
                row_errors = []

                question_text = str(row.get("question", "")).strip()
                correct = str(row.get("correct", "")).strip().upper()
                level = parse_level(str(row.get("level", "")))
                hint = str(row.get("hint", "")).strip() if "hint" in dataframe.columns else ""
                explanation = (
                    str(row.get("explanation", "")).strip()
                    if "explanation" in dataframe.columns
                    else ""
                )

                options = {
                    label: str(row.get(f"option_{label.lower()}", "")).strip()
                    for label in OPTION_LABELS
                }

                if not question_text:
                    row_errors.append({"field": "question", "message": "Question is required."})
                elif question_text.lower() in existing_questions:
                    row_errors.append({"field": "question", "message": "Question already exists in the bank."})
                elif question_text.lower() in seen_questions:
                    row_errors.append({"field": "question", "message": "Question is repeated in this file."})

                for label, option_text in options.items():
                    if not option_text:
                        row_errors.append({
                            "field": f"option_{label.lower()}",
                            "message": f"Option {label} is required.",
                        })
                    elif len(option_text) > OPTION_MAX_LENGTH:
                        row_errors.append({
                            "field": f"option_{label.lower()}",
                            "message": f"Option {label} cannot exceed {OPTION_MAX_LENGTH} characters.",
                        })

                if correct not in OPTION_LABELS:
                    row_errors.append({"field": "correct", "message": "Correct must be A, B, C or D."})

                if level is None:
                    row_errors.append({
                        "field": "level",
                        "message": "Level must be Basic, Intermediate or Advanced.",
                    })

                if len(hint) > HINT_MAX_LENGTH:
                    row_errors.append({
                        "field": "hint",
                        "message": f"Hint cannot exceed {HINT_MAX_LENGTH} characters.",
                    })

                if row_errors:
                    for row_error in row_errors:
                        errors.append({"row": row_number, **row_error})
                    continue

                seen_questions.add(question_text.lower())

                parsed_rows.append({
                    "row": row_number,
                    "question": question_text,
                    "options": options,
                    "correct": correct,
                    "level": level,
                    "hint": hint or None,
                    "explanation": explanation or None,
                })

            total_rows = len(dataframe)
            error_row_numbers = {error["row"] for error in errors}

            # -----------------------------------------
            # Save file + import record
            # -----------------------------------------
            upload_file.seek(0)
            file_url = save_to_s3("assessments/imports", upload_file)

            with transaction.atomic():
                question_import = AssessmentQuestionImport.objects.create(
                    grade=grade,
                    subject=subject,
                    lesson=lesson,
                    file_name=upload_file.name,
                    file_url=file_url,
                    total_rows=total_rows,
                    valid_rows=len(parsed_rows),
                    error_rows=len(error_row_numbers),
                    errors=errors,
                    parsed_rows=parsed_rows,
                    status=AssessmentQuestionImport.Status.VALIDATED,
                )

            application_logger.info(
                "assessment_question_import_validated",
                import_id=str(question_import.id),
                total_rows=total_rows,
                valid_rows=len(parsed_rows),
                error_rows=len(error_row_numbers),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(question_import.id),
                    "file_name": question_import.file_name,
                    "total_rows": total_rows,
                    "valid_rows": len(parsed_rows),
                    "error_rows": len(error_row_numbers),
                    "errors": errors,
                    "preview": parsed_rows[:20],
                    "status": question_import.status,
                },
                description="File validated successfully.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_import_validate_failed",
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to validate file.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  BULK UPLOAD - STEP 3 (IMPORT VALID ROWS)
# =====================================================================
class AssessmentQuestionImportAPIView(APIView):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permission = "assessment.question.import"

    def post(self, request, import_id):
        import_uuid = parse_uuid(import_id)

        if import_uuid is None:
            return CustomResponse.errorResponse(
                description="Invalid import ID."
            )

        try:
            with transaction.atomic():
                question_import = AssessmentQuestionImport.objects.select_for_update().filter(
                    id=import_uuid,
                ).first()

                if question_import is None:
                    return CustomResponse.errorResponse(
                        description="Import not found.",
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if question_import.status != AssessmentQuestionImport.Status.VALIDATED:
                    return CustomResponse.errorResponse(
                        description="This file has already been imported or is not validated."
                    )

                if not question_import.parsed_rows:
                    return CustomResponse.errorResponse(
                        description="There are no valid rows to import."
                    )

                user_id = str(request.user.id)
                questions = []
                options = []

                for row in question_import.parsed_rows:
                    question = AssessmentQuestion(
                        grade_id=question_import.grade_id,
                        subject_id=question_import.subject_id,
                        lesson_id=question_import.lesson_id,
                        question=row["question"],
                        level=row["level"],
                        marks=Decimal("1"),
                        hint=row.get("hint"),
                        explanation=row.get("explanation"),
                        created_by=user_id,
                        updated_by=user_id,
                    )
                    questions.append(question)

                    for serial_number, label in enumerate(OPTION_LABELS, start=1):
                        options.append(
                            AssessmentQuestionOption(
                                question=question,
                                label=label,
                                option_text=row["options"][label],
                                is_correct=row["correct"] == label,
                                serial_number=serial_number,
                                created_by=user_id,
                                updated_by=user_id,
                            )
                        )

                # bulk_create skips AuditModel.save(),
                # so created_by / updated_by are set above.
                AssessmentQuestion.objects.bulk_create(questions)
                AssessmentQuestionOption.objects.bulk_create(options)

                question_import.imported_rows = len(questions)
                question_import.status = AssessmentQuestionImport.Status.IMPORTED
                question_import.imported_at = timezone.now()
                question_import.parsed_rows = []
                question_import.save()

            application_logger.info(
                "assessment_question_import_completed",
                import_id=str(question_import.id),
                imported_rows=question_import.imported_rows,
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(question_import.id),
                    "imported_rows": question_import.imported_rows,
                    "skipped_rows": question_import.error_rows,
                    "status": question_import.status,
                },
                description=f"{question_import.imported_rows} questions imported.",
            )

        except Exception:
            application_logger.exception(
                "assessment_question_import_failed",
                import_id=str(import_uuid),
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to import questions.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
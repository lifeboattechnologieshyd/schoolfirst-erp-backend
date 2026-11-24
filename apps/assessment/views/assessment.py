import random
import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.assessment.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentLesson,
    AssessmentQuestion,
    AssessmentQuestionMapping,
    AssessmentQuestionOption,
)
from apps.curriculum.models import Curriculum, CurriculumLesson, CurriculumSubject
from apps.vocabbee.models import Grades
from shared.mixins import CustomResponse
from shared.utils.logger import application_logger


# =====================================================================
#  CONSTANTS
# =====================================================================
DEFAULT_GENERATED_QUESTIONS = 15
MAX_GENERATED_QUESTIONS = 50

LEVEL_ORDER = [
    AssessmentQuestion.Level.BASIC,
    AssessmentQuestion.Level.INTERMEDIATE,
    AssessmentQuestion.Level.ADVANCED,
]


# =====================================================================
#  HELPERS
# =====================================================================
def parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def get_parent_kid(request, kid_id):
    """
    Same check as vocabbee: the kid must belong to the logged-in parent.
    """
    kid_uuid = parse_uuid(kid_id)

    if kid_uuid is None:
        return None

    return request.user.kids.filter(
        id=kid_uuid,
        is_active=True,
    ).select_related(
        "grade",
    ).first()


def questions_with_correct_answer():
    """
    Only questions that have a correct option can be served to kids.
    """
    correct_question_ids = AssessmentQuestionOption.objects.filter(
        is_correct=True,
    ).values_list("question_id", flat=True)

    return AssessmentQuestion.objects.filter(
        id__in=correct_question_ids,
        is_active=True,
    )


def select_balanced_questions(question_ids_by_level, number_of_questions):
    """
    Picks questions spread evenly across Basic / Intermediate / Advanced.
    If a level does not have enough, the rest is filled from other levels.
    Returned in Basic -> Intermediate -> Advanced order (easy first).
    """
    pools = {
        level: random.sample(ids, len(ids))
        for level, ids in question_ids_by_level.items()
    }

    total_available = sum(len(ids) for ids in pools.values())
    number_of_questions = min(number_of_questions, total_available)

    base_quota = number_of_questions // len(LEVEL_ORDER)
    remainder = number_of_questions % len(LEVEL_ORDER)

    selected = {level: [] for level in LEVEL_ORDER}

    for index, level in enumerate(LEVEL_ORDER):
        quota = base_quota + (1 if index < remainder else 0)
        selected[level] = pools.get(level, [])[:quota]

    # Fill any shortfall from the levels that still have questions
    shortfall = number_of_questions - sum(len(ids) for ids in selected.values())

    while shortfall > 0:
        filled = False

        for level in LEVEL_ORDER:
            pool = pools.get(level, [])

            if shortfall and len(selected[level]) < len(pool):
                selected[level].append(pool[len(selected[level])])
                shortfall -= 1
                filled = True

        if not filled:
            break

    ordered_ids = []

    for level in LEVEL_ORDER:
        ordered_ids.extend(selected[level])

    return ordered_ids


def get_assessment_mappings(assessment):
    return list(
        AssessmentQuestionMapping.objects.filter(
            assessment=assessment,
            question__is_deleted=False,
        ).select_related(
            "question",
        ).prefetch_related(
            "question__options",
        ).order_by(
            "serial_number",
            "created_at",
        )
    )


def build_assessment_card(assessment):
    """
    A4 Assessment details card.
    """
    return {
        "id": str(assessment.id),
        "title": assessment.title,
        "description": assessment.description,
        "cover_image": assessment.cover_image,
        "time_limit": assessment.time_limit,
        "total_questions": assessment.total_questions,
        "total_marks": assessment.total_marks,
        "is_auto_generated": assessment.is_auto_generated,
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
    }


def build_attempt_payload(attempt):
    """
    A6 Quiz. Correct answers and explanations are NOT sent;
    the answer is checked on submit.
    """
    assessment = attempt.assessment

    questions = []

    for serial_number, mapping in enumerate(get_assessment_mappings(assessment), start=1):
        question = mapping.question

        questions.append({
            "id": str(question.id),
            "serial_number": serial_number,
            "question": question.question,
            "level": question.level,
            "marks": question.marks,
            "hint": question.hint,
            "image": question.image,
            "options": [
                {
                    "id": str(option.id),
                    "label": option.label,
                    "option_text": option.option_text,
                }
                for option in question.options.all()
            ],
        })

    data = build_assessment_card(assessment)
    data["attempt_id"] = str(attempt.id)
    data["attempt_status"] = attempt.status
    data["started_at"] = attempt.started_at
    data["total_questions"] = len(questions)
    data["questions"] = questions

    return data


def find_reusable_generated_assessment(kid, curriculum, grade, subject, lesson_ids, target_questions):
    """
    Same idea as the old GenerateAssessmentAPIView:
    reuse a generated test with exactly the same lessons
    that this kid has not completed yet.
    """
    lesson_count = len(lesson_ids)

    candidate_ids = Assessment.objects.filter(
        is_auto_generated=True,
        status=Assessment.Status.PUBLISHED,
        curriculum=curriculum,
        grade=grade,
        subject=subject,
        total_questions=target_questions,
    ).annotate(
        lessons_count=Count(
            "assessment_lessons",
            filter=Q(assessment_lessons__is_deleted=False),
            distinct=True,
        ),
    ).filter(
        lessons_count=lesson_count,
    ).values_list("id", flat=True)

    matching_ids = AssessmentLesson.objects.filter(
        assessment_id__in=list(candidate_ids),
        lesson_id__in=lesson_ids,
    ).values(
        "assessment_id",
    ).annotate(
        matched=Count("lesson_id", distinct=True),
    ).filter(
        matched=lesson_count,
    ).values_list("assessment_id", flat=True)

    completed_ids = AssessmentAttempt.objects.filter(
        kid=kid,
        status=AssessmentAttempt.Status.COMPLETED,
    ).values_list("assessment_id", flat=True)

    return Assessment.objects.filter(
        id__in=list(matching_ids),
    ).exclude(
        id__in=completed_ids,
    ).select_related(
        "curriculum",
        "grade",
        "subject",
    ).order_by(
        "-created_at",
    ).first()


def get_or_start_attempt(kid, assessment):
    """
    Resumes the kid's in-progress attempt, or starts a new one.
    Returns (attempt, resumed).
    """
    attempt = AssessmentAttempt.objects.filter(
        kid=kid,
        assessment=assessment,
        status=AssessmentAttempt.Status.IN_PROGRESS,
    ).select_related(
        "assessment",
        "assessment__curriculum",
        "assessment__grade",
        "assessment__subject",
    ).first()

    if attempt:
        return attempt, True

    attempt = AssessmentAttempt.objects.create(
        assessment=assessment,
        kid=kid,
        status=AssessmentAttempt.Status.IN_PROGRESS,
        total_questions=assessment.total_questions,
        total_marks=assessment.total_marks,
        started_at=timezone.now(),
    )

    return attempt, False


# =====================================================================
#  A5 - GENERATE TEST FROM SELECTED LESSONS
#  Payload: kid_id, curriculum_id, grade_id, subject_id, lesson_ids
#  Reuses a matching generated test the kid has not completed,
#  otherwise creates a new test + question mappings from the bank.
# =====================================================================
class GenerateAssessmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        kid_id = request.data.get("kid_id")
        curriculum_id = request.data.get("curriculum_id")
        grade_id = request.data.get("grade_id")
        subject_id = request.data.get("subject_id")
        lesson_ids = request.data.get("lesson_ids")
        number_of_questions = request.data.get("number_of_questions", DEFAULT_GENERATED_QUESTIONS)

        application_logger.info(
            "app_assessment_generate_called",
            kid_id=str(kid_id),
            curriculum_id=str(curriculum_id),
            grade_id=str(grade_id),
            subject_id=str(subject_id),
            lesson_ids=lesson_ids,
            requested_by=str(request.user.id),
        )

        # -----------------------------------------
        # Required fields
        # -----------------------------------------
        if not kid_id or not curriculum_id or not grade_id or not subject_id:
            return CustomResponse.errorResponse(
                description="kid_id, curriculum_id, grade_id, subject_id and lesson_ids are required."
            )

        if not isinstance(lesson_ids, list) or not lesson_ids:
            return CustomResponse.errorResponse(
                description="Select at least one lesson."
            )

        lesson_uuids = []

        for lesson_id in lesson_ids:
            lesson_uuid = parse_uuid(lesson_id)

            if lesson_uuid is None:
                return CustomResponse.errorResponse(
                    description="Invalid lesson ID."
                )

            if lesson_uuid not in lesson_uuids:
                lesson_uuids.append(lesson_uuid)

        try:
            number_of_questions = int(number_of_questions)
        except (ValueError, TypeError):
            return CustomResponse.errorResponse(
                description="number_of_questions must be a number."
            )

        if number_of_questions < 1 or number_of_questions > MAX_GENERATED_QUESTIONS:
            return CustomResponse.errorResponse(
                description=f"number_of_questions must be between 1 and {MAX_GENERATED_QUESTIONS}."
            )

        curriculum_uuid = parse_uuid(curriculum_id)
        grade_uuid = parse_uuid(grade_id)
        subject_uuid = parse_uuid(subject_id)

        if not curriculum_uuid or not grade_uuid or not subject_uuid:
            return CustomResponse.errorResponse(
                description="Invalid curriculum, grade, or subject ID."
            )

        kid = get_parent_kid(request, kid_id)

        if kid is None:
            return CustomResponse.errorResponse(
                description="Invalid kid."
            )

        try:
            # -----------------------------------------
            # Curriculum / grade / subject / lessons
            # -----------------------------------------
            curriculum = Curriculum.objects.filter(
                id=curriculum_uuid,
                is_active=True,
                is_deleted=False,
            ).first()

            if curriculum is None:
                return CustomResponse.errorResponse(
                    description="Curriculum not found."
                )

            grade = Grades.objects.filter(
                id=grade_uuid,
                is_active=True,
                is_deleted=False,
            ).first()

            if grade is None:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            subject = CurriculumSubject.objects.filter(
                id=subject_uuid,
                is_active=True,
                is_deleted=False,
            ).first()

            if subject is None:
                return CustomResponse.errorResponse(
                    description="Subject not found."
                )

            if subject.curriculum_id != curriculum.id or subject.grade_id != grade.id:
                return CustomResponse.errorResponse(
                    description="The selected subject does not belong to this curriculum and grade."
                )

            lessons = list(
                CurriculumLesson.objects.filter(
                    id__in=lesson_uuids,
                    subject=subject,
                    is_active=True,
                    is_deleted=False,
                ).order_by(
                    "serial_number",
                )
            )

            if len(lessons) != len(lesson_uuids):
                return CustomResponse.errorResponse(
                    description="One or more lessons are invalid or do not belong to this subject."
                )

            # -----------------------------------------
            # Questions available in the bank
            # -----------------------------------------
            question_ids_by_level = {level: [] for level in LEVEL_ORDER}

            for question_id, level in questions_with_correct_answer().filter(
                grade=grade,
                subject=subject,
                lesson_id__in=lesson_uuids,
            ).values_list("id", "level"):
                question_ids_by_level.setdefault(level, []).append(question_id)

            available_count = sum(len(ids) for ids in question_ids_by_level.values())

            if available_count == 0:
                return CustomResponse.errorResponse(
                    description="No questions are available for the selected lessons yet."
                )

            target_questions = min(number_of_questions, available_count)

            with transaction.atomic():

                # -----------------------------------------
                # Reuse a matching generated test
                # -----------------------------------------
                assessment = find_reusable_generated_assessment(
                    kid=kid,
                    curriculum=curriculum,
                    grade=grade,
                    subject=subject,
                    lesson_ids=lesson_uuids,
                    target_questions=target_questions,
                )

                created = False

                # -----------------------------------------
                # Or create a new one
                # -----------------------------------------
                if assessment is None:
                    selected_ids = select_balanced_questions(
                        question_ids_by_level,
                        target_questions,
                    )

                    questions = AssessmentQuestion.objects.in_bulk(selected_ids)
                    total_marks = sum(
                        (questions[question_id].marks for question_id in selected_ids),
                        Decimal("0"),
                    )

                    assessment = Assessment.objects.create(
                        curriculum=curriculum,
                        grade=grade,
                        subject=subject,
                        title=f"{subject.name} Test",
                        description=f"{subject.name} Test for {grade.name}"[:120],
                        time_limit=None,
                        total_questions=len(selected_ids),
                        total_marks=total_marks,
                        status=Assessment.Status.PUBLISHED,
                        published_at=timezone.now(),
                        is_auto_generated=True,
                    )

                    for lesson in lessons:
                        AssessmentLesson.objects.create(
                            assessment=assessment,
                            lesson=lesson,
                        )

                    for serial_number, question_id in enumerate(selected_ids, start=1):
                        AssessmentQuestionMapping.objects.create(
                            assessment=assessment,
                            question=questions[question_id],
                            serial_number=serial_number,
                        )

                    created = True

                attempt, resumed = get_or_start_attempt(kid, assessment)

            application_logger.info(
                "app_assessment_generated",
                assessment_id=str(assessment.id),
                attempt_id=str(attempt.id),
                kid_id=str(kid.id),
                created=created,
                resumed=resumed,
                total_questions=assessment.total_questions,
                available_questions=available_count,
                requested_by=str(request.user.id),
            )

            data = build_attempt_payload(attempt)
            data["resumed"] = resumed
            data["lessons"] = [
                {
                    "id": str(lesson.id),
                    "title": lesson.title,
                }
                for lesson in lessons
            ]

            return CustomResponse.successResponse(
                data=data,
                description="Assessment generated successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_assessment_generate_failed",
                kid_id=str(kid.id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to generate assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
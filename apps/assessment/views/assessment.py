import random
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from shared.helpers.family_zone import get_family_zone_grade, get_kid, parse_uuid
from apps.assessment.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentAttemptAnswer,
    AssessmentLesson,
    AssessmentQuestion,
    AssessmentQuestionMapping,
    AssessmentQuestionOption,
)
from apps.curriculum.models import Curriculum, CurriculumLesson, CurriculumSubject
from apps.school.models.school import Student
from apps.vocabbee.models import Grades
from shared.mixins import CustomPageNumberPagination, CustomResponse
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





def get_kid_attempt(kid, attempt_id, for_update=False):
    """
    The attempt must belong to the kid (student) sent by the app.
    """
    attempt_uuid = parse_uuid(attempt_id)

    if attempt_uuid is None:
        return None

    attempts = AssessmentAttempt.objects.filter(
        id=attempt_uuid,
        kid=kid,
    )

    if for_update:
        attempts = attempts.select_for_update()

    return attempts.select_related(
        "kid",
        "assessment",
        "assessment__grade",
        "assessment__subject",
        "assessment__curriculum",
    ).first()


def to_percentage(obtained, total):
    if not total:
        return Decimal("0.00")

    return (
        Decimal(obtained) * Decimal("100") / Decimal(total)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_stars(percentage):
    """
    0-5 stars. 80% -> 4 stars (A8 Assessment result).
    """
    return int(
        (Decimal(percentage) / Decimal("20")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


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


def build_attempt_result(attempt):
    """
    A8 Assessment result + A9 Past assessments row.
    """
    assessment = attempt.assessment

    return {
        "attempt_id": str(attempt.id),
        "status": attempt.status,
        "assessment": {
            "id": str(assessment.id),
            "title": assessment.title,
            "description": assessment.description,
            "cover_image": assessment.cover_image,
            "is_auto_generated": assessment.is_auto_generated,
        },
        "grade": {
            "id": str(assessment.grade_id),
            "name": assessment.grade.name,
        },
        "subject": {
            "id": str(assessment.subject_id),
            "name": assessment.subject.name,
        },
        "total_questions": attempt.total_questions,
        "total_marks": attempt.total_marks,
        "marks_obtained": attempt.marks_obtained,
        "correct_count": attempt.correct_count,
        "wrong_count": attempt.wrong_count,
        "skipped_count": attempt.skipped_count,
        "hints_used": attempt.hints_used,
        "percentage": attempt.percentage,
        "accuracy": attempt.percentage,
        "stars": get_stars(attempt.percentage) if attempt.status == AssessmentAttempt.Status.COMPLETED else 0,
        "time_taken_seconds": attempt.time_taken_seconds,
        "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at,
    }


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
#  Payload: kid_id, curriculum_id, subject_id, lesson_ids, grade_id (optional, defaults to student's mapped grade)
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
            subject_id=str(subject_id),
            lesson_ids=lesson_ids,
            requested_by=str(request.user.id),
        )

        # -----------------------------------------
        # Required fields
        # -----------------------------------------
        required_fields = {
            "kid_id": kid_id,
            "curriculum_id": curriculum_id,
            "subject_id": subject_id,
            "lesson_ids": lesson_ids,
        }

        missing_fields = [
            field
            for field, value in required_fields.items()
            if value is None
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, list) and not value)
        ]

        if missing_fields:
            return CustomResponse.errorResponse(
                description=(
                    f"{missing_fields[0]} is required."
                    if len(missing_fields) == 1
                    else f"{', '.join(missing_fields)} are required."
                ),
                data={
                    "missing_fields": missing_fields
                },
            )

        if not isinstance(lesson_ids, list):
            return CustomResponse.errorResponse(
                description="lesson_ids must be a list."
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
        grade_uuid = parse_uuid(grade_id) if grade_id else None
        subject_uuid = parse_uuid(subject_id)

        if not curriculum_uuid or not subject_uuid or (grade_id and not grade_uuid):
            return CustomResponse.errorResponse(
                description="Invalid curriculum, grade, or subject ID."
            )

        kid = get_kid(kid_id, request.user)

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

            if grade_uuid:
                grade = Grades.objects.filter(
                    id=grade_uuid,
                    is_active=True,
                    is_deleted=False,
                ).first()
            else:
                grade = get_family_zone_grade(kid)

            if grade is None:
                return CustomResponse.errorResponse(
                    description=(
                        "Grade not found."
                        if grade_uuid
                        else "Grade is not mapped for Family Zone. Please contact school admin."
                    )
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


# =====================================================================
#  A6 / A8 - SUBMIT ANSWERS + RESULT
#  Payload: kid_id, attempt_id, answers, time_taken_seconds (optional)
#  answers: [{"question_id", "option_id" (null = skipped), "hint_used"}]
#  Questions not sent are counted as skipped.
# =====================================================================
class SubmitAssessmentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        kid_id = request.data.get("kid_id")
        attempt_id = request.data.get("attempt_id")
        answers = request.data.get("answers")
        time_taken_seconds = request.data.get("time_taken_seconds")

        # -----------------------------------------
        # Required fields
        # (answers can be an empty list = everything skipped)
        # -----------------------------------------
        required_fields = {
            "kid_id": kid_id,
            "attempt_id": attempt_id,
            "answers": answers,
        }

        missing_fields = [
            field
            for field, value in required_fields.items()
            if value is None
            or (isinstance(value, str) and not value.strip())
        ]

        if missing_fields:
            return CustomResponse.errorResponse(
                description=(
                    f"{missing_fields[0]} is required."
                    if len(missing_fields) == 1
                    else f"{', '.join(missing_fields)} are required."
                ),
                data={
                    "missing_fields": missing_fields
                },
            )

        if parse_uuid(attempt_id) is None:
            return CustomResponse.errorResponse(
                description="Invalid attempt_id."
            )

        if not isinstance(answers, list):
            return CustomResponse.errorResponse(
                description="answers must be a list."
            )

        if time_taken_seconds not in (None, ""):
            try:
                time_taken_seconds = int(time_taken_seconds)

                if time_taken_seconds < 0:
                    raise ValueError
            except (ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="time_taken_seconds must be a positive number."
                )
        else:
            time_taken_seconds = None

        # -----------------------------------------
        # Validate answer payload shape
        # -----------------------------------------
        submitted = {}

        for answer in answers:
            if not isinstance(answer, dict):
                return CustomResponse.errorResponse(
                    description="Each answer must be an object."
                )

            question_uuid = parse_uuid(answer.get("question_id"))

            if question_uuid is None:
                return CustomResponse.errorResponse(
                    description="Invalid question_id in answers."
                )

            if question_uuid in submitted:
                return CustomResponse.errorResponse(
                    description="A question is answered more than once."
                )

            option_id = answer.get("option_id")
            option_uuid = None

            if option_id not in (None, ""):
                option_uuid = parse_uuid(option_id)

                if option_uuid is None:
                    return CustomResponse.errorResponse(
                        description="Invalid option_id in answers."
                    )

            hint_used = answer.get("hint_used", False)

            if not isinstance(hint_used, bool):
                return CustomResponse.errorResponse(
                    description="hint_used must be a boolean."
                )

            submitted[question_uuid] = {
                "option_id": option_uuid,
                "hint_used": hint_used,
            }

        kid = get_kid(kid_id, request.user)

        if kid is None:
            return CustomResponse.errorResponse(
                description="Invalid kid."
            )

        try:
            with transaction.atomic():
                attempt = get_kid_attempt(kid, attempt_id, for_update=True)

                if attempt is None:
                    return CustomResponse.errorResponse(
                        description="Attempt not found.",
                        status=status.HTTP_404_NOT_FOUND,
                    )

                if attempt.status == AssessmentAttempt.Status.COMPLETED:
                    return CustomResponse.errorResponse(
                        description="This assessment has already been submitted."
                    )

                mappings = get_assessment_mappings(attempt.assessment)
                question_ids = {mapping.question_id for mapping in mappings}

                unknown = set(submitted.keys()) - question_ids

                if unknown:
                    return CustomResponse.errorResponse(
                        description="Some answers are for questions that are not in this assessment."
                    )

                # -----------------------------------------
                # Check answers + snapshot
                # -----------------------------------------
                correct_count = 0
                wrong_count = 0
                skipped_count = 0
                hints_used = 0
                marks_obtained = Decimal("0")
                total_marks = Decimal("0")
                answer_rows = []

                for serial_number, mapping in enumerate(mappings, start=1):
                    question = mapping.question
                    options = list(question.options.all())
                    options_by_id = {option.id: option for option in options}
                    correct_option = next((option for option in options if option.is_correct), None)

                    answer = submitted.get(question.id, {"option_id": None, "hint_used": False})
                    selected_option = None

                    if answer["option_id"]:
                        selected_option = options_by_id.get(answer["option_id"])

                        if selected_option is None:
                            return CustomResponse.errorResponse(
                                description=f"Selected option does not belong to question {serial_number}."
                            )

                    is_skipped = selected_option is None
                    is_correct = bool(
                        selected_option
                        and correct_option
                        and selected_option.id == correct_option.id
                    )
                    marks_awarded = question.marks if is_correct else Decimal("0")

                    total_marks += question.marks
                    marks_obtained += marks_awarded

                    if is_skipped:
                        skipped_count += 1
                    elif is_correct:
                        correct_count += 1
                    else:
                        wrong_count += 1

                    if answer["hint_used"]:
                        hints_used += 1

                    answer_rows.append(dict(
                        attempt=attempt,
                        question=question,
                        selected_option=selected_option,
                        serial_number=serial_number,
                        is_correct=is_correct,
                        is_skipped=is_skipped,
                        hint_used=answer["hint_used"],
                        marks_awarded=marks_awarded,
                        question_text=question.question,
                        level=question.level,
                        marks=question.marks,
                        options=[
                            {
                                "label": option.label,
                                "option_text": option.option_text,
                            }
                            for option in options
                        ],
                        selected_label=selected_option.label if selected_option else None,
                        correct_label=correct_option.label if correct_option else None,
                        hint=question.hint,
                        explanation=question.explanation,
                    ))

                # Write only after every answer is valid,
                # so an error above never leaves partial answers.
                for row in answer_rows:
                    AssessmentAttemptAnswer.objects.create(**row)

                # -----------------------------------------
                # Save result
                # -----------------------------------------
                attempt.status = AssessmentAttempt.Status.COMPLETED
                attempt.total_questions = len(mappings)
                attempt.total_marks = total_marks
                attempt.correct_count = correct_count
                attempt.wrong_count = wrong_count
                attempt.skipped_count = skipped_count
                attempt.hints_used = hints_used
                attempt.marks_obtained = marks_obtained
                attempt.percentage = to_percentage(marks_obtained, total_marks)
                attempt.submitted_at = timezone.now()
                attempt.time_taken_seconds = (
                    time_taken_seconds
                    if time_taken_seconds is not None
                    else int((attempt.submitted_at - attempt.started_at).total_seconds())
                )
                attempt.save()

            application_logger.info(
                "app_assessment_submitted",
                attempt_id=str(attempt.id),
                assessment_id=str(attempt.assessment_id),
                kid_id=str(kid.id),
                correct_count=correct_count,
                total_questions=attempt.total_questions,
                requested_by=str(request.user.id),
            )

            return CustomResponse.successResponse(
                data=build_attempt_result(attempt),
                description="Assessment submitted successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_assessment_submit_failed",
                attempt_id=str(attempt_id),
                kid_id=str(kid.id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to submit assessment.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  A9 - PAST ASSESSMENTS
# =====================================================================
class AssessmentAttemptLISTAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        kid_id = request.query_params.get("kid_id")

        if not kid_id:
            return CustomResponse.errorResponse(
                description="kid_id is required.",
                data={
                    "missing_fields": ["kid_id"]
                },
            )

        kid = get_kid(kid_id, request.user)

        if kid is None:
            return CustomResponse.errorResponse(
                description="Invalid kid."
            )

        try:
            attempts = AssessmentAttempt.objects.filter(
                kid=kid,
                status=AssessmentAttempt.Status.COMPLETED,
            ).select_related(
                "assessment",
                "assessment__grade",
                "assessment__subject",
            ).order_by(
                "-submitted_at",
            )

            for field, lookup in {
                "grade_id": "assessment__grade_id",
                "subject_id": "assessment__subject_id",
                "assessment_id": "assessment_id",
            }.items():
                value = request.query_params.get(field)

                if not value:
                    continue

                if parse_uuid(value) is None:
                    return CustomResponse.errorResponse(
                        description=f"Invalid {field}."
                    )

                attempts = attempts.filter(**{lookup: value})

            status_filter = request.query_params.get("status")

            if status_filter:
                status_filter = status_filter.strip().upper()

                if status_filter not in AssessmentAttempt.Status.values:
                    return CustomResponse.errorResponse(
                        description="Status must be COMPLETED."
                    )

                attempts = attempts.filter(status=status_filter)

            total = attempts.count()

            paginator = CustomPageNumberPagination()

            page = paginator.paginate_queryset(
                attempts,
                request,
                view=self,
            )

            data = [build_attempt_result(attempt) for attempt in page]

            return CustomResponse.successResponse(
                data=data,
                total=total,
                description="Past assessments fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_assessment_attempt_list_failed",
                kid_id=str(kid.id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch past assessments.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =====================================================================
#  A10 - ANSWER REVIEW
# =====================================================================
class AssessmentAttemptDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attempt_id):
        kid_id = request.query_params.get("kid_id")

        if not kid_id:
            return CustomResponse.errorResponse(
                description="kid_id is required.",
                data={
                    "missing_fields": ["kid_id"]
                },
            )

        kid = get_kid(kid_id, request.user)

        if kid is None:
            return CustomResponse.errorResponse(
                description="Invalid kid."
            )

        try:
            attempt = get_kid_attempt(kid, attempt_id)

            if attempt is None:
                return CustomResponse.errorResponse(
                    description="Attempt not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

            if attempt.status != AssessmentAttempt.Status.COMPLETED:
                return CustomResponse.errorResponse(
                    description="Submit the assessment to see the answers."
                )

            answers = AssessmentAttemptAnswer.objects.filter(
                attempt=attempt,
            ).order_by(
                "serial_number",
            )

            data = build_attempt_result(attempt)
            data["answers"] = [
                {
                    "question_id": str(answer.question_id),
                    "serial_number": answer.serial_number,
                    "question": answer.question_text,
                    "level": answer.level,
                    "marks": answer.marks,
                    "marks_awarded": answer.marks_awarded,
                    "options": answer.options,
                    "selected_option": answer.selected_label,
                    "correct_option": answer.correct_label,
                    "is_correct": answer.is_correct,
                    "is_skipped": answer.is_skipped,
                    "hint_used": answer.hint_used,
                    "hint": answer.hint,
                    "explanation": answer.explanation,
                }
                for answer in answers
            ]

            return CustomResponse.successResponse(
                data=data,
                description="Answers fetched successfully.",
            )

        except Exception:
            application_logger.exception(
                "app_assessment_attempt_detail_failed",
                attempt_id=str(attempt_id),
                requested_by=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description="Unable to fetch answers.",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
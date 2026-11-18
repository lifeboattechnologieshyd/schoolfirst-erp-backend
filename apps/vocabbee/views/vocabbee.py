from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.vocabbee.models import PracticeAttempts, PracticeAttemptAnswers, KidWordProgress, Words, \
    DailyChallengeAttempts, Kids, DailyChallengeAttemptAnswers, DailyChallengeWords, Grades
from shared.mixins import CustomResponse
from shared.utils.vocabbee import get_practice_words


class StartPractice(APIView):

    def post(self, request):
        kid_id = request.data.get("kid_id")
        no_of_questions = request.data.get("no_of_questions", 10)
        subjects = request.data.get("subjects", [])
        if not kid_id:
            return CustomResponse().errorResponse(
                data={},
                description="Kid ID is required"
            )
        kid = request.user.kids.filter(
            id=kid_id,
            is_active=True
        ).select_related(
            "grade"
        ).first()

        if not kid:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid kid"
            )

        attempt = PracticeAttempts.objects.create(
            kid=kid,
            started_at=timezone.now(),
            total_questions=no_of_questions
        )
        response = get_practice_words(kid, no_of_questions)
        return CustomResponse().successResponse(
            data={
                "attempt_id": str(attempt.id),
                "total_questions": len(response),
                "words": response
            },
            description="Practice started successfully"
        )

class SubmitPracticeAnswer(APIView):

    @transaction.atomic
    def post(self, request):

        attempt_id = request.data.get(
            "attempt_id"
        )

        word_id = request.data.get(
            "word_id"
        )

        typed_answer = request.data.get(
            "typed_answer",
            ""
        ).strip()

        time_taken_seconds = request.data.get(
            "time_taken_seconds",
            0
        )
        # is_last_question = request.data.get(
        #     "is_last_question",
        #     False
        # )

        attempt = PracticeAttempts.objects.select_related(
            "kid"
        ).filter(
            id=attempt_id
        ).first()

        if not attempt:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid attempt"
            )

        word = Words.objects.filter(
            id=word_id,
            is_active=True
        ).first()

        if not word:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid word"
            )

        is_correct = (
            typed_answer.lower().strip()
            ==
            word.word.lower().strip()
        )

        PracticeAttemptAnswers.objects.create(
            attempt=attempt,
            word=word,
            typed_answer=typed_answer,
            is_correct=is_correct,
            time_taken_seconds=time_taken_seconds
        )

        progress, _ = KidWordProgress.objects.get_or_create(
            kid=attempt.kid,
            word=word,
            defaults={
                "times_seen": 0,
                "times_correct": 0
            }
        )

        progress.times_seen += 1

        if is_correct:
            progress.times_correct += 1

        progress.last_attempted_at = timezone.now()
        progress.save()
        attempt.total_questions += 1
        if is_correct:
            attempt.correct_answers += 1
            # score logic can evolve later
            attempt.score += 1
        else:
            attempt.wrong_answers += 1

        attempt.save()

        response = {
            "is_correct": is_correct,
            "correct_word": word.word
        }
        # if is_last_question:
        #     next_words = get_practice_words(attempt.kid)
        #     response["next_words"] = next_words
        return CustomResponse().successResponse(
            data=response,
            description="Answer submitted successfully"
        )


class SkipPracticeQuestion(APIView):

    @transaction.atomic
    def post(self, request):

        attempt_id = request.data.get(
            "attempt_id"
        )

        word_id = request.data.get(
            "word_id"
        )

        time_taken_seconds = request.data.get(
            "time_taken_seconds",
            60
        )

        is_last_question = request.data.get(
            "is_last_question",
            False
        )

        attempt = PracticeAttempts.objects.select_related(
            "kid"
        ).filter(
            id=attempt_id
        ).first()

        if not attempt:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid attempt"
            )

        word = Words.objects.filter(
            id=word_id,
            is_active=True
        ).first()

        if not word:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid word"
            )

        PracticeAttemptAnswers.objects.create(
            attempt=attempt,
            word=word,
            is_skipped=True,
            time_taken_seconds=time_taken_seconds
        )

        progress, _ = KidWordProgress.objects.get_or_create(
            kid=attempt.kid,
            word=word,
            defaults={
                "times_seen": 0,
                "times_correct": 0
            }
        )

        progress.times_seen += 1
        progress.last_attempted_at = timezone.now()
        progress.save()
        attempt.total_questions += 1
        attempt.skipped_answers += 1
        attempt.save()
        response = {
            "is_skipped": True,
            "correct_word": word.word
        }
        if is_last_question:
            next_words = get_practice_words(attempt.kid)
            response["next_words"] = next_words
        return CustomResponse().successResponse(
            data=response,
            description="Question skipped successfully"
        )

class EndPractice(APIView):

    def post(self, request):

        attempt_id = request.data.get(
            "attempt_id"
        )

        if not attempt_id:
            return CustomResponse().errorResponse(
                data={},
                description="Attempt ID is required"
            )

        attempt = PracticeAttempts.objects.select_related(
            "kid"
        ).filter(
            id=attempt_id
        ).first()

        if not attempt:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid attempt"
            )

        if attempt.completed_at:

            return CustomResponse().successResponse(
                data={
                    "attempt_id": str(attempt.id),
                    "score": attempt.score,
                    "total_questions":
                        attempt.total_questions,
                    "correct_answers":
                        attempt.correct_answers,
                    "wrong_answers":
                        attempt.wrong_answers,
                    "skipped_answers":
                        attempt.skipped_answers,
                    "started_at":
                        attempt.started_at,
                    "completed_at":
                        attempt.completed_at
                },
                description="Practice already completed"
            )

        attempt.completed_at = timezone.now()

        attempt.save(
            update_fields=[
                "completed_at",
                "updated_at"
            ]
        )

        return CustomResponse().successResponse(
            data={
                "attempt_id": str(attempt.id),

                "score": attempt.score,

                "total_questions":
                    attempt.total_questions,

                "correct_answers":
                    attempt.correct_answers,

                "wrong_answers":
                    attempt.wrong_answers,

                "skipped_answers":
                    attempt.skipped_answers,

                "started_at":
                    attempt.started_at,

                "completed_at":
                    attempt.completed_at
            },
            description="Practice completed successfully"
        )


class PracticeStats(APIView):

    def get(self, request):

        kid_id = request.GET.get(
            "kid_id"
        )

        if not kid_id:
            return CustomResponse().errorResponse(
                data={},
                description="Kid ID is required"
            )

        kid = request.user.kids.filter(
            id=kid_id,
            is_active=True
        ).select_related(
            "grade"
        ).first()

        if not kid:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid kid"
            )

        total_words_in_grade = Words.objects.filter(
            grade=kid.grade,
            is_active=True
        ).count()

        progress_queryset = KidWordProgress.objects.filter(
            kid=kid
        )

        attempted_words = progress_queryset.count()

        mastered_words = progress_queryset.filter(
            times_correct__gt=0
        ).count()

        weak_words = progress_queryset.filter(
            times_seen__gt=0,
            times_correct=0
        ).count()

        unseen_words = max(
            total_words_in_grade - attempted_words,
            0
        )

        completion_percentage = 0

        if total_words_in_grade:

            completion_percentage = round(
                (
                    attempted_words /
                    total_words_in_grade
                ) * 100,
                2
            )

        return CustomResponse().successResponse(
            data={
                "total_words_in_grade":
                    total_words_in_grade,

                "attempted_words":
                    attempted_words,

                "mastered_words":
                    mastered_words,

                "weak_words":
                    weak_words,

                "unseen_words":
                    unseen_words,

                "completion_percentage":
                    completion_percentage
            },
            description="Practice stats fetched successfully"
        )

class PracticeHistoryAPIView(APIView):

    def get(self, request):
        kid_id = request.GET.get(
            "kid_id"
        )
        kid = request.user.kids.filter(
            id=kid_id,
            is_active=True
        ).first()
        if not kid:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid kid"
            )
        practice_attempts = PracticeAttempts.objects.filter(
            kid=kid
        ).values(
            "id",
            "total_questions",
            "correct_answers",
            "wrong_answers",
            "skipped_answers",
            "score",
            "started_at",
            "completed_at"
        ).order_by("-started_at")
        return CustomResponse().successResponse(
                data=list(practice_attempts),
                description="Success"
            )

class HomeStats(APIView):


    def get(self, request):
        total_words = Words.objects.count()
        kid_id = request.GET.get(
            "kid_id"
        )
        kid = request.user.kids.filter(
            id=kid_id,
            is_active=True
        ).first()
        if not kid:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid kid"
            )
        mastered_words = KidWordProgress.objects.filter(
            kid=kid,
            is_mastered=True
        ).count()
        return CustomResponse().successResponse(
            data={
                "total_words": total_words,
                "mastered_words":mastered_words
            },
            description="Success"
        )

class DailyChallengesAPIView(APIView):

    permission_classes = [AllowAny]
    def get(self, request):
        kid = Kids.objects.get(
            id=request.GET.get("kid_id")
        )
        page = int(request.GET.get("page",1))
        challenge_dates = DailyChallengeWords.objects.filter(
            grade=kid.grade,
            is_active=True
        ).values_list(
            "challenge_date",
            flat=True
        ).distinct().order_by(
            "-challenge_date"
        )
        start_index = (page - 1) * 30
        end_index = (start_index + 30)
        challenge_dates = challenge_dates[start_index:end_index]
        today = timezone.localdate()
        results = []
        attempts = {
            attempt.challenge_date: attempt
            for attempt in DailyChallengeAttempts.objects.filter(
                kid=kid,
                challenge_date__in=challenge_dates
            )
        }
        for challenge_date in challenge_dates:
            attempt = attempts.get(
                challenge_date
            )
            if attempt:
                if attempt.status == "COMPLETED":
                    challenge_status = "COMPLETED"
                else:
                    challenge_status = "IN_PROGRESS"
            else:
                if challenge_date < today:
                    challenge_status = "MISSED"
                else:
                    challenge_status = "NOT_STARTED"
            results.append(
                {
                    "date": challenge_date,
                    "is_today": challenge_date == today,
                    "status": challenge_status
                }
            )
        return CustomResponse.successResponse(data=results,
                                                  description="")

class DailyChallengeWordsAPIView(APIView):

    def post(self, request):
        kid_id = request.data.get("kid_id")
        challenge_date = request.data.get("challenge_date")
        if not kid_id:
            return CustomResponse.errorResponse(
                description="kid_id is required"
            )
        if not challenge_date:
            return CustomResponse.errorResponse(
                description="challenge_date is required"
            )
        try:
            kid = Kids.objects.select_related(
                "grade"
            ).get(
                id=kid_id
            )
        except Kids.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Kid not found"
            )
        attempt, created = DailyChallengeAttempts.objects.get_or_create(
            kid=kid,
            challenge_date=challenge_date,
            defaults={
                "grade": kid.grade,
                "status": "IN_PROGRESS"
            }
        )
        attempted_word_ids = DailyChallengeAttemptAnswers.objects.filter(
            challenge_attempt=attempt
        ).values_list(
            "word_id",
            flat=True
        )

        challenge_words = (
            DailyChallengeWords.objects
            .filter(
                challenge_date=challenge_date,
                grade=kid.grade,
                is_active=True,
            )
            .exclude(
                word_id__in=attempted_word_ids
            )
            .select_related(
                "word",
                "word__audio"
            )
            .order_by(
                "order"
            )
        )
        words = []
        for challenge_word in challenge_words:
            word = challenge_word.word
            try:
                audio = word.audio
            except WordAudios.DoesNotExist:
                audio = None
            words.append(
                {
                    "id": str(word.id),
                    "word": word.word,
                    "subject": word.subject,
                    "concept": word.concept,
                    "hint": word.hint,
                    "difficulty": word.difficulty,
                    "meaning": word.meaning,
                    "part_of_speech": word.part_of_speech,
                    "origin": word.origin,
                    "usage": word.usage,
                    "audios": {
                        "pronunciation_audio_url": (
                            audio.pronunciation_audio_url
                            if audio else None
                        ),
                        "meaning_audio_url": (
                            audio.meaning_audio_url
                            if audio else None
                        ),
                        "part_of_speech_audio_url": (
                            audio.part_of_speech_audio_url
                            if audio else None
                        ),
                        "origin_audio_url": (
                            audio.origin_audio_url
                            if audio else None
                        ),
                        "usage_audio_url": (
                            audio.usage_audio_url
                            if audio else None
                        )
                    }
                }
            )
        total_words = 10
        attempted_words = len(
            attempted_word_ids
        )
        remaining_words = len(
            words
        )
        return CustomResponse.successResponse(
            data={
                "attempt_id": str(attempt.id),
                "challenge_date": challenge_date,
                "status": attempt.status,
                "total_words": total_words,
                "attempted_words": attempted_words,
                "remaining_words": remaining_words,
                "words": words
            },
            description="Daily challenge words fetched successfully"
        )


class DailyChallengeSubmitAPIView(APIView):

    @transaction.atomic
    def post(self, request):
        attempt_id = request.data.get("attempt_id")
        word_id = request.data.get("word_id")
        typed_answer = request.data.get("typed_answer")
        if not attempt_id:
            return CustomResponse.errorResponse(
                description="attempt_id is required"
            )
        if not word_id:
            return CustomResponse.errorResponse(
                description="word_id is required"
            )
        if not typed_answer:
            return CustomResponse.errorResponse(
                description="typed_answer is required"
            )
        try:
            attempt = (
                DailyChallengeAttempts.objects
                .select_for_update()
                .select_related(
                    "kid",
                    "grade"
                )
                .get(id=attempt_id)
            )
        except DailyChallengeAttempts.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Attempt not found"
            )
        try:
            word = Words.objects.get(
                id=word_id
            )
        except Words.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Word not found"
            )
        already_answered = (
            DailyChallengeAttemptAnswers.objects.filter(
                challenge_attempt=attempt,
                word=word
            ).exists()
        )
        if already_answered:
            return CustomResponse.errorResponse(
                description="Word already submitted"
            )
        normalized_answer = typed_answer.strip().lower()
        correct_word = word.word.strip().lower()
        is_correct = normalized_answer == correct_word
        DailyChallengeAttemptAnswers.objects.create(
            challenge_attempt=attempt,
            word=word,
            typed_answer=typed_answer,
            is_correct=is_correct
        )
        # -----------------------------------
        # Update Daily Challenge Attempt
        # -----------------------------------
        attempt.attempted_words += 1
        if is_correct:
            attempt.correct_words += 1
        challenge_completed = False
        percentage = None
        if attempt.attempted_words >= attempt.total_words:
            challenge_completed = True
            percentage = round((attempt.correct_words /attempt.total_words) * 100,
                2
            ) if attempt.total_words else 0
            attempt.status = "COMPLETED"
            attempt.completed_at = timezone.now()
        attempt.save()
        # -----------------------------------
        # Update Kid Progress
        # -----------------------------------
        progress, _ = (
            KidWordProgress.objects.get_or_create(
                kid=attempt.kid,
                word=word
            )
        )
        progress.times_seen += 1
        if is_correct:
            progress.times_correct += 1
        progress.last_attempted_at = timezone.now()
        progress.save()
        return CustomResponse.successResponse(
            data={
                "is_correct": is_correct,
                "correct_word": word.word,
                "typed_answer": typed_answer,
                "attempted_words": attempt.attempted_words,
                "correct_words": attempt.correct_words,
                "remaining_words": attempt.total_words - attempt.attempted_words,
                "total_words": attempt.total_words,
                "challenge_completed": challenge_completed,
                "percentage": percentage
            },
            description="Answer submitted successfully"
        )

class DailyChallengeResultAPIView(APIView):
    def get(self, request):
        attempt_id = request.GET.get(
            "attempt_id"
        )
        try:
            attempt = (
                DailyChallengeAttempts.objects
                .get(
                    id=attempt_id
                )
            )
        except DailyChallengeAttempts.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Attempt not found"
            )
        wrong_answers = (
            DailyChallengeAttemptAnswers.objects
            .filter(
                challenge_attempt=attempt,
                is_correct=False
            )
            .select_related(
                "word"
            )
        )
        wrong_words = []
        for answer in wrong_answers:
            wrong_words.append({
                "word": answer.word.word,
                "typed_answer": answer.typed_answer
            })
        accuracy = round((attempt.correct_words / attempt.total_words) * 100,
            2
        ) if attempt.total_words else 0
        return CustomResponse.successResponse(
            data={
                "challenge_date": attempt.challenge_date,
                "score": attempt.correct_words,
                "total_words": attempt.total_words,
                "accuracy": accuracy,
                "wrong_words": wrong_words
            },
            description="Result fetched successfully"
        )

class DailyChallengeStatsAPIView(APIView):

    def get(self, request):
        kid_id = request.GET.get("kid_id")
        try:
            kid = Kids.objects.get(
                id=kid_id
            )
        except Kids.DoesNotExist:
            return CustomResponse.errorResponse(
                description="Kid not found"
            )
        attempts = (
            DailyChallengeAttempts.objects
            .filter(
                kid=kid,
                status="COMPLETED"
            )
            .order_by(
                "challenge_date"
            )
        )
        completed_challenges = attempts.count()
        total_words_attempted = (
            attempts.aggregate(
                total=Sum("attempted_words")
            )["total"] or 0
        )
        total_words_correct = (
            attempts.aggregate(
                total=Sum("correct_words")
            )["total"] or 0
        )
        average_accuracy = round(
            (
                total_words_correct /
                total_words_attempted
            ) * 100,
            2
        ) if total_words_attempted else 0
        dates = list(
            attempts.values_list(
                "challenge_date",
                flat=True
            )
        )
        current_streak = 0
        best_streak = 0
        running_streak = 0
        previous_date = None
        for challenge_date in dates:
            if (
                previous_date and
                (challenge_date - previous_date).days == 1
            ):
                running_streak += 1
            else:
                running_streak = 1
            best_streak = max(
                best_streak,
                running_streak
            )
            previous_date = challenge_date
        today = timezone.localdate()
        streak_date = today

        while DailyChallengeAttempts.objects.filter(
            kid=kid,
            challenge_date=streak_date,
            status="COMPLETED"
        ).exists():
            current_streak += 1
            streak_date -= timedelta(days=1)

        return CustomResponse.successResponse(
            data={
                "completed_challenges": completed_challenges,
                "current_streak": current_streak,
                "best_streak": best_streak,
                "average_accuracy": average_accuracy,
                "total_words_attempted": total_words_attempted,
                "total_words_correct": total_words_correct
            },
            description="Stats fetched successfully"
        )

class DailyChallengeHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        kid_id = request.query_params.get("kid_id")
        attempts = (
            DailyChallengeAttempts.objects
            .filter(
                kid_id=kid_id,
            )
            .order_by("-challenge_date")
        )
        data = [
            {
                "attempt_id": str(attempt.id),
                "attempted_date": attempt.challenge_date,
                "words_attempted": attempt.attempted_words,
                "correct_words": attempt.correct_words,
                "status": attempt.status,
            }
            for attempt in attempts
        ]
        return CustomResponse().successResponse(data=data)

class GradesList(APIView):
    def get(self, request):
        grades = Grades.objects.filter(
                is_active=True
            ).order_by(
                "sort_order"
            )
        data = []
        for grade in grades:
            data.append({
                "id": str(grade.id),
                "name": grade.name
            })
        return CustomResponse().successResponse(
            data=data,
            description="Grades fetched successfully"
        )


class AddKid(APIView):

    def post(self, request):

        name = request.data.get("name")
        grade_id = request.data.get("grade_id")
        profile_image = request.data.get("profile_image")

        if not name:
            return CustomResponse().errorResponse(
                data={},
                description="Kid name is required"
            )

        if not grade_id:
            return CustomResponse().errorResponse(
                data={},
                description="Grade is required"
            )
        grade = Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).first()
        if not grade:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid grade"
            )
        kid = Kids.objects.create(
            parent=request.user,
            grade=grade,
            name=name,
            profile_image=profile_image
        )
        return CustomResponse().successResponse(
            data={
                "kid_id": str(kid.id)
            },
            description="Kid added successfully"
        )

    def get(self, request):
        kids = request.user.kids.filter(
            is_active=True
        ).select_related(
            "grade"
        )

        response = []
        for kid in kids:
            response.append({
                "kid_id": str(kid.id),
                "name": kid.name,
                "profile_image": kid.profile_image,
                "grade": {
                    "id": str(kid.grade.id),
                    "name": kid.grade.name
                }
            })
        return CustomResponse().successResponse(
            data=response,
            description="Kids fetched successfully"
        )
    def put(self, request):

        kid_id = request.data.get("kid_id")

        if not kid_id:
            return CustomResponse().errorResponse(
                data={},
                description="Kid ID is required"
            )

        kid = request.user.kids.filter(
            id=kid_id,
            is_active=True
        ).first()

        if not kid:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid kid"
            )

        name = request.data.get("name")
        grade_id = request.data.get("grade_id")
        profile_image = request.data.get("profile_image")

        if not name:
            return CustomResponse().errorResponse(
                data={},
                description="Kid name is required"
            )

        grade = Grades.objects.filter(
            id=grade_id,
            is_active=True
        ).first()

        if not grade:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid grade"
            )

        kid.name = name.strip()
        kid.grade = grade

        if profile_image is not None:
            kid.profile_image = profile_image

        kid.save()

        return CustomResponse().successResponse(
            data={},
            description="Kid updated successfully"
        )

    def delete(self, request):

        kid_id = request.data.get("kid_id")

        if not kid_id:
            return CustomResponse().errorResponse(
                data={},
                description="Kid ID is required"
            )

        kid = request.user.kids.filter(
            id=kid_id,
            is_active=True
        ).first()

        if not kid:
            return CustomResponse().errorResponse(
                data={},
                description="Invalid kid"
            )

        kid.is_active = False
        kid.save()
        return CustomResponse().successResponse(
            data={},
            description="Kid deleted successfully"
        )
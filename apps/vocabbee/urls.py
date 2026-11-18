from django.urls import path

from apps.backoffice.views.school import SubjectListAPIView
from apps.vocabbee.views.vocabbee import StartPractice, SubmitPracticeAnswer, SkipPracticeQuestion, EndPractice, \
    PracticeHistoryAPIView, PracticeStats, DailyChallengesAPIView, DailyChallengeWordsAPIView, \
    DailyChallengeSubmitAPIView, DailyChallengeResultAPIView, DailyChallengeStatsAPIView, DailyChallengeHistoryAPIView

urlpatterns = [
    path("practice/start", StartPractice.as_view()),
    path("practice/submit-answer", SubmitPracticeAnswer.as_view()),
    path("practice/skip-answer", SkipPracticeQuestion.as_view()),
    path("practice/end", EndPractice.as_view()),
    path("practice/attempts", PracticeHistoryAPIView.as_view()),
    path("practice/stats", PracticeStats.as_view()),

    path("subjects", SubjectListAPIView.as_view()),

    ####################################
    ## Daily Challenges
    ####################################
    path("daily-challenges", DailyChallengesAPIView.as_view()),
    path("daily-challenges/words", DailyChallengeWordsAPIView.as_view()),
    path("daily-challenges/submit", DailyChallengeSubmitAPIView.as_view()),
    path("daily-challenges/results", DailyChallengeResultAPIView.as_view()),
    path("daily-challenges/stats", DailyChallengeStatsAPIView.as_view()),
    path("daily-challenges/history", DailyChallengeHistoryAPIView.as_view()),
]
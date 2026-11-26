from django.urls import path

from apps.assessment.views.assessment import GenerateAssessmentAPIView, SubmitAssessmentAPIView, \
    AssessmentAttemptLISTAPIView, AssessmentAttemptDetailAPIView

urlpatterns = [

    path("generate", GenerateAssessmentAPIView.as_view()),

    path("submit", SubmitAssessmentAPIView.as_view()),

    path("attempts", AssessmentAttemptLISTAPIView.as_view()),

    path("attempts/<uuid:attempt_id>", AssessmentAttemptDetailAPIView.as_view()),

]
from django.urls import path

from apps.assessment.views.assessment import GenerateAssessmentAPIView

urlpatterns = [

    path("generate", GenerateAssessmentAPIView.as_view()),

]
from django.urls import path

from apps.ptm.views.ptm import StudentPTMListAPIView, StudentPTMResponseAPIView, StudentCompletedPTMAPIView

urlpatterns = [
    path("parent-teacher-meetings",StudentPTMListAPIView.as_view()),
    path("parent-response/<uuid:meeting_id>",StudentPTMResponseAPIView.as_view()),
    path("completed-meetings",StudentCompletedPTMAPIView.as_view()),
]
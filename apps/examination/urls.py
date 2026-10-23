from django.urls import path

from apps.examination.views.examination import ExaminationLISTAPIView, UpcomingExaminationAPIView, \
    ExaminationDetailAPIView, ExaminationResultLISTAPIView, HallTicketDetailAPIView, ReportCardDetailAPIView, \
    ExaminationResultDetailAPIView, ExaminationAttendanceAPIView

urlpatterns = [
    path("exam", ExaminationLISTAPIView.as_view()),
    path("exam/detail", ExaminationDetailAPIView.as_view()),
    path("upcoming/exams",UpcomingExaminationAPIView.as_view()),
    path("hall-ticket", HallTicketDetailAPIView.as_view()),
    path("exam/attendance", ExaminationAttendanceAPIView.as_view()),
    path("results",ExaminationResultLISTAPIView.as_view()),
    path("results/detail", ExaminationResultDetailAPIView.as_view()),
    path("reportcard", ReportCardDetailAPIView.as_view()),
]
from django.urls import path

from apps.timetable.views.timetable import TimetableAPIView, TimetableTermLISTAPIView

urlpatterns = [
    path("timetable", TimetableAPIView.as_view()),
    path("term",TimetableTermLISTAPIView.as_view()),
]
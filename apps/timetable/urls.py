from django.urls import path

from apps.timetable.views.timetable import TimetableAPIView

urlpatterns = [
    path("timetable", TimetableAPIView.as_view()),
]
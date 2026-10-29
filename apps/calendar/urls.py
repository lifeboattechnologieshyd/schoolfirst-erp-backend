from django.urls import path

from apps.calendar.views.events import CalendarEventListAPIView, AcademicCalendarListAPIView

urlpatterns = [
    path("calendar",AcademicCalendarListAPIView.as_view()),
    path('event', CalendarEventListAPIView.as_view()),
]
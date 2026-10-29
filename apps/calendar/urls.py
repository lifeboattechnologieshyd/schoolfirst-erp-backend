from django.urls import path

from apps.calendar.views.events import CalendarEventListAPIView, AcademicCalendarDetailAPIView

urlpatterns = [
    path("calendar",AcademicCalendarDetailAPIView.as_view()),
    path('event', CalendarEventListAPIView.as_view()),
]
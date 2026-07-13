from django.urls import path

from apps.calendar.views.events import CalendarEventListAPIView

urlpatterns = [
    path('event', CalendarEventListAPIView.as_view()),
]
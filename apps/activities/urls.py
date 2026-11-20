from django.urls import path

from apps.activities.view.activities import ActivityAPIView

urlpatterns = [
    path("daily-activity",ActivityAPIView.as_view()),
]
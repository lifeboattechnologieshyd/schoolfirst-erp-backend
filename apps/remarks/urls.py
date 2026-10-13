from django.urls import path

from apps.remarks.views.remarks import StudentRemarkLISTAPIView

urlpatterns = [
    path("remarks",StudentRemarkLISTAPIView.as_view()),
]
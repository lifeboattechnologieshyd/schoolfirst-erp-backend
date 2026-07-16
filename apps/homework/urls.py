from django.urls import path

from apps.homework.views.assignment import StudentAssignmentListAPIView, StudentAssignmentSubmissionAPIView
from apps.homework.views.homework import StudentHomeworkListAPIView, StudentHomeworkSubmissionAPIView





urlpatterns = [

    path("student",StudentHomeworkListAPIView.as_view(),),

    path("submission",StudentHomeworkSubmissionAPIView.as_view(),),

    path("assignment/student", StudentAssignmentListAPIView.as_view(), ),

    path("assignment/submission", StudentAssignmentSubmissionAPIView.as_view(), ),
]
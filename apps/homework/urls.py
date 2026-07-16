from django.urls import path

from apps.homework.views.assignment import StudentAssignmentListAPIView, StudentAssignmentSubmissionAPIView
from apps.homework.views.homework import StudentHomeworkListAPIView, StudentHomeworkSubmissionAPIView





urlpatterns = [

    path("student",StudentHomeworkListAPIView.as_view(),),

    path("submission/<uuid:homework_id>",StudentHomeworkSubmissionAPIView.as_view(),),

    path("assignment/student", StudentAssignmentListAPIView.as_view(), ),

    path("assignment/submission/<uuid:assignment_id>", StudentAssignmentSubmissionAPIView.as_view(), ),
]
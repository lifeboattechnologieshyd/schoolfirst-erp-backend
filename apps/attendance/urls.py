from django.urls import path

from apps.attendance.views.attendance import StudentAttendanceAPIView, StudentLeaveRequestAPIView, \
    StudentLeaveLISTAPIView

urlpatterns = [
    path('apply/leave', StudentLeaveRequestAPIView.as_view()),
    path("leaves",StudentLeaveLISTAPIView.as_view()),
    path("attendance", StudentAttendanceAPIView.as_view()),
]
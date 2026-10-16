from django.urls import path

from apps.attendance.views.attendance import StudentAttendanceAPIView, StudentLeaveRequestAPIView

urlpatterns = [
    path('apply/leave', StudentLeaveRequestAPIView.as_view()),
    path("attendance", StudentAttendanceAPIView.as_view()),
]
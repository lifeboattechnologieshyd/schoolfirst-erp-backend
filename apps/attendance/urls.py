from django.urls import path

from apps.attendance.views.attendance import StudentAttendanceAPIView, StudentLeaveRequestAPIView, \
    StudentLeaveLISTAPIView, StudentAttendanceLateNoteAPIView

urlpatterns = [
    path('apply/leave', StudentLeaveRequestAPIView.as_view()),
    path("leaves",StudentLeaveLISTAPIView.as_view()),
    path("attendance", StudentAttendanceAPIView.as_view()),
    path("late-note",StudentAttendanceLateNoteAPIView.as_view()),
]
from django.urls import path

from apps.core.views.auth import LogoutAPIView, FileUploadView, ADMINSendOTPAPIView, ADMINVerifyOTPAPIView, \
    VerifyOTPAPIView, SendOTPAPIView, StudentProfileAPIView

urlpatterns = [

    path("admin/send-otp", ADMINSendOTPAPIView.as_view(), name="send-otp"),

    path("admin/verify-otp", ADMINVerifyOTPAPIView.as_view(), name="verify-otp"),

    path("logout", LogoutAPIView.as_view(), name="logout"),

    path("file/upload",FileUploadView.as_view(),name="file-upload"),

    path("send-otp",SendOTPAPIView.as_view(),name="send-otp"),

    path("verify-otp",VerifyOTPAPIView.as_view(),name="verify-otp"),

    path("profile/<uuid:student_id>",StudentProfileAPIView.as_view(),name="student-profile"),

]
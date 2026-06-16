from django.urls import path

from apps.core.views.auth import LogoutAPIView, FileUploadView, ADMINSendOTPAPIView, ADMINVerifyOTPAPIView

urlpatterns = [

    path("admin/send-otp", ADMINSendOTPAPIView.as_view(), name="send-otp"),

    path("admin/verify-otp", ADMINVerifyOTPAPIView.as_view(), name="verify-otp"),

    path("logout", LogoutAPIView.as_view(), name="logout"),

    path("file/upload",FileUploadView.as_view(),name="file-upload"),

]
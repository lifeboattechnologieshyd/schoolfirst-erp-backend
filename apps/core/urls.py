from django.urls import path

from apps.core.views.auth import SendOTPAPIView, VerifyOTPAPIView

urlpatterns = [

    path("send-otp", SendOTPAPIView.as_view(), name="send-otp"),

    path("verify-otp", VerifyOTPAPIView.as_view(), name="verify-otp"),

]
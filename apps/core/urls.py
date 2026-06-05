from django.urls import path

from apps.core.views.auth import SendOTPAPIView, VerifyOTPAPIView, LogoutAPIView

urlpatterns = [

    path("admin/send-otp", SendOTPAPIView.as_view(), name="send-otp"),

    path("admin/verify-otp", VerifyOTPAPIView.as_view(), name="verify-otp"),

    path("logout", LogoutAPIView.as_view(), name="logout"),

]
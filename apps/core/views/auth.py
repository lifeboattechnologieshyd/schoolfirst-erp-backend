import secrets

from datetime import timedelta

from django.utils import timezone

from rest_framework.permissions import AllowAny

from rest_framework.response import Response

from rest_framework import status

from rest_framework.views import APIView

from apps.core.models import UserOTP


def normalize_email(value):

    if value is None:

        return None

    value = str(value).strip().lower()

    return value or None

def normalize_mobile(value):

    if value is None:

        return None

    value = str(value).strip()

    return value or None

def generate_otp():

    return f"{secrets.randbelow(1000000):06d}"

class SendOTPAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = normalize_email(request.data.get("email"))

        mobile = normalize_mobile(request.data.get("mobile"))

        channel = request.data.get("channel", "both")

        if not email and not mobile:

            return Response(

                {"message": "email or mobile is required"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        if channel not in ["email", "mobile", "both"]:

            return Response(

                {"message": "channel must be email, mobile, or both"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        otp = generate_otp()

        expires_at = timezone.now() + timedelta(minutes=5)

        if channel in ["email", "both"] and email:

            UserOTP.objects.create(

                user_id=None,

                email=email,

                mobile=None,

                otp=otp,

                expires_at=expires_at,

                is_used=False,

            )

            # send email here

        if channel in ["mobile", "both"] and mobile:

            UserOTP.objects.create(

                user_id=None,

                email=None,

                mobile=int(mobile),

                otp=otp,

                expires_at=expires_at,

                is_used=False,

            )

            # send sms here

        return Response(

            {

                "message": "OTP sent successfully",

                "otp": otp if getattr(__import__("django.conf").conf.settings, "DEBUG", False) else None,

            },

            status=status.HTTP_200_OK,

        )

class VerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        email = normalize_email(request.data.get("email"))

        mobile = normalize_mobile(request.data.get("mobile"))

        otp = str(request.data.get("otp", "")).strip()

        if not otp:

            return Response(

                {"message": "otp is required"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        if not email and not mobile:

            return Response(

                {"message": "email or mobile is required"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        otp_qs = UserOTP.objects.filter(

            otp=otp,

            is_used=False,

            expires_at__gt=timezone.now(),

        )

        if email:

            otp_obj = otp_qs.filter(email=email).order_by("-created_at").first()

        else:

            otp_obj = otp_qs.filter(mobile=int(mobile)).order_by("-created_at").first()

        if not otp_obj:

            return Response(

                {"message": "Invalid or expired OTP"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        otp_obj.is_used = True

        otp_obj.save(update_fields=["is_used"])

        return Response(

            {"message": "OTP verified successfully"},

            status=status.HTTP_200_OK,

        )
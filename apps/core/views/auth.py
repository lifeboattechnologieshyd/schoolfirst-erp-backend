import secrets

from datetime import timedelta

from django.utils import timezone

from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.response import Response

from rest_framework import status

from rest_framework.views import APIView

from apps.core.models import UserOTP, UserMaster
from django.db import transaction


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

    @transaction.atomic

    def post(self, request):

        email = request.data.get("email")

        mobile = request.data.get("mobile")

        otp = request.data.get("otp")

        if not otp:

            return Response(

                {"message": "OTP is required"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        if not email and not mobile:

            return Response(

                {"message": "Email or Mobile is required"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        otp_queryset = UserOTP.objects.filter(

            otp=otp,

            is_used=False,

            expires_at__gt=timezone.now(),

        )

        if email:

            otp_obj = otp_queryset.filter(email=email).order_by("-created_at").first()

        else:

            otp_obj = otp_queryset.filter(mobile=mobile).order_by("-created_at").first()

        if not otp_obj:

            return Response(

                {"message": "Invalid or expired OTP"},

                status=status.HTTP_400_BAD_REQUEST,

            )

        otp_obj.is_used = True

        otp_obj.save(update_fields=["is_used"])

        # Find existing user

        user = None

        if email:

            user = UserMaster.objects.filter(email=email).first()

        if not user and mobile:

            user = UserMaster.objects.filter(mobile=mobile).first()

        is_new_user = False

        # Create user if not exists

        if not user:

            username = mobile if mobile else email.split("@")[0]

            counter = 1

            base_username = username

            while UserMaster.objects.filter(username=username).exists():

                username = f"{base_username}{counter}"

                counter += 1

            user = UserMaster.objects.create(

                username=username,

                email=email,

                mobile=mobile,

                is_active=True,

                status=UserMaster.Status.ACTIVE,

            )

            is_new_user = True

        return Response(

            {

                "message": "OTP verified successfully",

                "is_new_user": is_new_user,

                "user": {

                    "id": str(user.id),

                    "username": user.username,

                    "email": user.email,

                    "mobile": user.mobile,

                    "first_name": user.first_name,

                    "last_name": user.last_name,

                    "status": user.status,

                    "is_active": user.is_active,

                    "is_staff": user.is_staff,

                },

            },

            status=status.HTTP_200_OK,

        )


class LogoutAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        user = request.user

        user.status = UserMaster.Status.INACTIVE

        user.save(update_fields=["status"])

        return Response(

            {

                "message": "Logged out successfully"

            },

            status=status.HTTP_200_OK

        )
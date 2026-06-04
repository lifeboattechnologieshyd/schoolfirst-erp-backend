import secrets

from datetime import timedelta

from django.utils import timezone

from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.response import Response

from rest_framework import status

from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import UserOTP, UserMaster, UserRoles
from django.db import transaction

from shared.mixins import CustomResponse


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

        mobile = normalize_mobile(

            request.data.get("mobile")

        )

        if not mobile:

            return CustomResponse.errorResponse(

                description="mobile is required.",

                status=status.HTTP_400_BAD_REQUEST,

            )

        user = UserMaster.objects.filter(

            mobile=mobile,

            is_active=True,

        ).first()

        if not user:

            return CustomResponse.errorResponse(

                description="User not found.",

                status=status.HTTP_404_NOT_FOUND,

            )

        otp = generate_otp()

        UserOTP.objects.create(

            user_id=user.id,

            mobile=int(mobile),

            otp=otp,

            expires_at=timezone.now() + timedelta(minutes=10),

            is_used=False,

        )

        return CustomResponse.successResponse(

            data={

                "mobile_otp": otp ,

            },

            description="OTP sent successfully.",

        )



class VerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        mobile = normalize_mobile(

            request.data.get("mobile")

        )

        otp = str(

            request.data.get("otp", "")

        ).strip()

        if not mobile or not otp:
            return CustomResponse.errorResponse(

                description="mobile and otp are required.",

                status=status.HTTP_400_BAD_REQUEST,

            )

        user = UserMaster.objects.filter(

            mobile=mobile,

            is_active=True,

        ).first()

        if not user:
            return CustomResponse.errorResponse(

                description="User not found.",

                status=status.HTTP_404_NOT_FOUND,

            )

        otp_obj = UserOTP.objects.filter(

            mobile=int(mobile),

            otp=otp,

            is_used=False,

            expires_at__gt=timezone.now(),

        ).order_by(

            "-created_at"

        ).first()

        if not otp_obj:
            return CustomResponse.errorResponse(

                description="Invalid or expired OTP.",

                status=status.HTTP_400_BAD_REQUEST,

            )

        otp_obj.is_used = True

        otp_obj.save(

            update_fields=["is_used"]

        )

        refresh = RefreshToken.for_user(

            user

        )

        roles = list(

            UserRoles.objects.filter(

                user=user

            ).values_list(

                "role__role_name",

                flat=True,

            ).distinct()

        )

        permissions = list(

            set(

                UserRoles.objects.filter(

                    user=user

                ).values_list(

                    "role__role_permissions_for_role__permission__permission_name",

                    flat=True,

                )

            )

        )

        return CustomResponse.successResponse(

            data={

                "user": {

                    "id": str(user.id),

                    "username": user.username,

                    "mobile": user.mobile,

                    "email": user.email,

                    "first_name": user.first_name,

                    "last_name": user.last_name,

                },

                "roles": roles,

                "permissions": permissions,

                "tokens": {

                    "access": str(

                        refresh.access_token

                    ),

                    "refresh": str(

                        refresh

                    ),

                },

            },

            description="Login successful.",

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
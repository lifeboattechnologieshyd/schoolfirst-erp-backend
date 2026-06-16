import secrets

from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework.response import Response

from rest_framework import status

from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import UserOTP, UserMaster, UserRoles
from django.db import transaction

from shared.enums.roles import RolesEnum
from shared.helpers import get_user_roles, get_user_permissions
from shared.mixins import CustomResponse

from rest_framework.parsers import FormParser, MultiPartParser
from django.conf import settings

from shared.utils.s3 import add_unique_suffix_to_filename, sanitize_filename


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

class ADMINSendOTPAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        print("=" * 80)

        print("Send OTP API Called")

        print("Request Data :", request.data)

        mobile = normalize_mobile(request.data.get("mobile") )
        print("Normalized Mobile :", mobile)

        if not mobile:
            return CustomResponse.errorResponse(description="Mobile is required.",status=status.HTTP_400_BAD_REQUEST,)
        print("Searching User...")

        user = UserMaster.objects.filter(mobile=mobile,is_active=True,).first()
        print("User :", user)

        if user is None:
            return CustomResponse.errorResponse(description="User not found.",status=status.HTTP_404_NOT_FOUND,)

        print("Fetching User Roles...")

        roles = get_user_roles(user=user,)
        print("Roles :", roles)

        allowed_roles = [
            RolesEnum.SUPERADMIN,
            RolesEnum.ADMIN,
            RolesEnum.SCHOOL_ADMIN,
            RolesEnum.TEACHER,
            RolesEnum.DRIVER,
            RolesEnum.PRINCIPAL,

        ]
        print("Allowed Roles :", allowed_roles)

        if not any(
            role in allowed_roles
            for role in roles
        ):
            print("User is not authorized.")

            return CustomResponse.errorResponse(
                description="You are not authorized to login.",
                status=status.HTTP_403_FORBIDDEN,
            )

        otp = 1234

        # otp = generate_otp()
        print("Generated OTP :", otp)

        UserOTP.objects.create( user=user,mobile=int(mobile),otp=otp, expires_at=timezone.now() + timedelta(minutes=10),is_used=False,)
        print("OTP Saved Successfully.")

        print("=" * 80)
        return CustomResponse.successResponse(
            data={
                "mobile_otp": otp,
            },
            description="OTP sent successfully.",

        )



class ADMINVerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        mobile = normalize_mobile(request.data.get("mobile"),)

        otp = str(

            request.data.get("otp","", )).strip()

        if not mobile or not otp:

            return CustomResponse.errorResponse(description="Mobile and OTP are required.",status=status.HTTP_400_BAD_REQUEST,)

        user = UserMaster.objects.filter(mobile=mobile,is_active=True,).first()

        if user is None:

            return CustomResponse.errorResponse(description="User not found.",status=status.HTTP_404_NOT_FOUND,)

        roles = get_user_roles( user=user,)

        otp_obj = UserOTP.objects.filter( mobile=int(mobile),otp=otp,is_used=False,expires_at__gt=timezone.now(),).order_by("-created_at",).first()

        if otp_obj is None:

            return CustomResponse.errorResponse(description="Invalid or expired OTP.",status=status.HTTP_400_BAD_REQUEST,)

        otp_obj.is_used = True

        otp_obj.save(update_fields=["is_used",],)

        refresh = RefreshToken.for_user(user,)

        permissions = get_user_permissions(user=user,)

        return CustomResponse.successResponse(

            data={

                "user": {

                    "id": str(user.id,),
                    "username": user.username,
                    "mobile": user.mobile,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
                "roles": roles,
                "permissions": permissions,
                "tokens": {
                    "access": str(refresh.access_token,),
                    "refresh": str(refresh,),},},description="Login successful.",)


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

class FileUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        files = request.FILES.getlist("files")
        path = request.data.get("path", "temp")

        if not files:
            return CustomResponse().successResponse(
                {"error": "No file was provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_files = []

        try:
            for file_obj in files:
                # Save each file to the default storage
                sanitized_filename = add_unique_suffix_to_filename(sanitize_filename(file_obj.name))

                file_path = default_storage.save(f"{path}/{sanitized_filename}", ContentFile(file_obj.read()))
                file_url = settings.MEDIA_URL + file_path
                uploaded_files.append(
                    {"original_filename": file_obj.name, "file_url": file_url, "file_path": file_path}
                )

            return CustomResponse().successResponse(uploaded_files, status=status.HTTP_201_CREATED)

        except Exception as e:
            return CustomResponse().errorResponse(
                {"error": str(e)}, description="File upload failed", status=status.HTTP_400_BAD_REQUEST
            )
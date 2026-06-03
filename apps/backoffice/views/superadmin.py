from datetime import timedelta

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.backoffice.views.leads import normalize_email, normalize_mobile
from apps.core.models import UserRoles, Roles, Permissions, RolePermissions, UserOTP, UserMaster
from apps.school.models import SchoolLead
from shared.mixins import CustomResponse

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import status



class CreateSuperAdminAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):

        role, created = Roles.objects.get_or_create(
            role_name="SUPERADMIN",
            defaults={
                "description": "Platform Super Admin",
            },
        )

        if not created:
            return CustomResponse.errorResponse(
                description="SUPERADMIN role already exists.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        return CustomResponse.successResponse(
            data={
                "role_id": str(role.id),
                "role_name": role.role_name,
            },
            description="SUPERADMIN role created successfully.",
            status=status.HTTP_201_CREATED,
        )



class SuperAdminRequestOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = normalize_mobile(
            request.data.get("phone_number")
        )

        if not phone_number:
            return CustomResponse.errorResponse(
                description="phone_number is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserMaster.objects.filter(
            mobile=phone_number,
            is_active=True,
        ).first()

        print("USER ID:", user.id)
        print("MOBILE:", user.mobile)

        print(
            UserRoles.objects.filter(user=user).values(
                "role__role_name",
                "school_id"
            )
        )

        if not user:
            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        is_superadmin = UserRoles.objects.filter(
            user=user,
            role__role_name="SUPERADMIN",
        ).exists()

        if not is_superadmin:
            return CustomResponse.errorResponse(
                description="Only SUPERADMIN can login here.",
                status=status.HTTP_403_FORBIDDEN,
            )
        otp = 1234

        # otp = generate_otp()

        UserOTP.objects.create(
            user=user,
            mobile=int(phone_number),
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=15),
            is_used=False,
        )

        # send sms here

        return CustomResponse.successResponse(
            data={
                "mobile_otp": otp ,
            },
            description="OTP sent successfully.",
            status=status.HTTP_200_OK,
        )

class SuperAdminVerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        phone_number = normalize_mobile(
            request.data.get("phone_number")
        )

        otp = str(
            request.data.get("otp", "")
        ).strip()

        if not phone_number or not otp:
            return CustomResponse.errorResponse(
                description="phone_number and otp are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserMaster.objects.filter(
            mobile=phone_number,
            is_active=True,
        ).first()

        if not user:
            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        otp_obj = (
            UserOTP.objects.filter(
                user=user,
                mobile=int(phone_number),
                otp=otp,
                is_used=False,
                expires_at__gt=timezone.now(),
            )
            .order_by("-created_at")
            .first()
        )

        if not otp_obj:
            return CustomResponse.errorResponse(
                description="Invalid or expired OTP.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

        user_role = UserRoles.objects.filter(
            user=user,
            role__role_name="SUPERADMIN",
        ).exists()

        if not user_role:
            return CustomResponse.errorResponse(
                description="SUPERADMIN role not assigned.",
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        return CustomResponse.successResponse(
            data={
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "mobile": user.mobile,
                    "email": user.email,
                    "first_name": user.first_name,
                },
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            description="SUPERADMIN login successful.",
            status=status.HTTP_200_OK,
        )

class SchoolLeadListAPIView(APIView):

    def get(self, request):

        if not request.user.is_authenticated:
            return CustomResponse.successResponse(data={},description="You are not logged in")


        leads = SchoolLead.objects.all()

        return CustomResponse.successResponse(
            {
                "data": [
                    {
                        "id": str(lead.id),
                        "school_name": lead.school_name,
                        "contact_person": lead.contact_person,
                        "phone_number": lead.phone_number,
                        "email": lead.email,
                        "is_verified": lead.is_verified,
                        "status": lead.status,
                    }
                    for lead in leads
                ]
            }
        )
import secrets
from datetime import timedelta
import random

import string
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.school.models import SchoolLead, School
from apps.core.models import UserMaster, UserOTP, Roles, UserRoles
from shared.mixins import CustomResponse
from shared.utils.otp import generate_school_code

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




class SchoolLeadRequestOTPAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        required_fields = [

            "school_name",

            "contact_person",

            "number_of_students",

            "location",

            "email",

            "phone_number",

        ]

        missing = [field for field in required_fields if not request.data.get(field)]

        if missing:
            return CustomResponse.errorResponse(
                data={"fields": missing},
                description="Missing required fields.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        school_name = request.data.get("school_name")

        contact_person = request.data.get("contact_person")

        number_of_students = request.data.get("number_of_students")

        location = request.data.get("location")

        email = normalize_email(request.data.get("email"))

        phone_number = normalize_mobile(request.data.get("phone_number"))

        if not email or not phone_number:
            return CustomResponse.errorResponse(
                description="Both email and phone_number are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = SchoolLead.objects.create(

            school_name=school_name,

            contact_person=contact_person,

            number_of_students=number_of_students,

            location=location,

            phone_number=phone_number,

            email=email,

            is_verified=False,

            is_mobile_verified=False,

            is_email_verified=False,

        )


        mobile_otp = generate_otp()

        expires_at = timezone.now() + timedelta(minutes=15)



        UserOTP.objects.create(

            user_id=None,

            email=None,

            mobile=int(phone_number),

            otp=mobile_otp,

            expires_at=expires_at,

            is_used=False,

        )

        # send email OTP here

        # send sms OTP here

        return CustomResponse.successResponse(
            data={
                "lead_id": str(lead.id),
                "mobile_otp": mobile_otp if settings.DEBUG else None,
            },
            description="OTP sent successfully.",
            status=status.HTTP_200_OK,
        )

class SchoolLeadVerifyOTPAPIView(APIView):

    permission_classes = [AllowAny]

    @transaction.atomic

    def post(self, request):

        lead_id = request.data.get("lead_id")


        mobile_otp = str(request.data.get("mobile_otp", "")).strip()

        if not lead_id or not mobile_otp:
            return CustomResponse.errorResponse(
                description="lead_id and mobile_otp are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = get_object_or_404(SchoolLead, id=lead_id)



        mobile_otp_obj = UserOTP.objects.filter(

            otp=mobile_otp,

            mobile=int(lead.phone_number),

            is_used=False,

            expires_at__gt=timezone.now(),

        ).order_by("-created_at").first()

        if not mobile_otp_obj:
            return CustomResponse.errorResponse(
                description="Invalid or expired mobile OTP.",
                status=status.HTTP_400_BAD_REQUEST,
            )



        mobile_otp_obj.is_used = True

        mobile_otp_obj.save(update_fields=["is_used"])

        lead.is_verified = True

        lead.is_email_verified = True

        lead.is_mobile_verified = True

        lead.save(update_fields=["is_verified", "is_email_verified", "is_mobile_verified"])

        school = School.objects.filter(

            Q(email=lead.email) | Q(phone_number=lead.phone_number)

        ).first()

        if not school:

            school = School.objects.create(

                name=lead.school_name,

                code=generate_school_code(),

                email=lead.email,

                phone_number=lead.phone_number,

                principal_name=lead.contact_person,

                total_students=lead.number_of_students,

                address=lead.location,

                city="Unknown",

                state="Unknown",

                country="India",

                status=School.Status.ACTIVE,

                is_email_verified=True,

                is_phone_verified=True,

            )

        user = UserMaster.objects.filter(

            Q(email=lead.email) | Q(mobile=lead.phone_number)

        ).first()

        is_new_user = False

        if not user:

            username = lead.phone_number

            counter = 1

            base_username = username

            while UserMaster.objects.filter(username=username).exists():

                username = f"{base_username}{counter}"

                counter += 1

            user = UserMaster.objects.create(

                username=username,

                email=lead.email,

                mobile=lead.phone_number,

                first_name=lead.contact_person,

                is_active=True,

                is_staff=True,

                status=UserMaster.Status.ACTIVE,

            )

            user.set_unusable_password()

            user.save(update_fields=["password"])

            is_new_user = True

        role, _ = Roles.objects.get_or_create(

            role_name="SYSTEM_ADMIN",

            defaults={

                "description": "School System Admin",

            },

        )

        UserRoles.objects.get_or_create(

            user=user,

            school=school,

            role=role,

        )

        refresh = RefreshToken.for_user(user)

        return CustomResponse.successResponse(
            data={
                "is_new_user": is_new_user,
                "school": {
                    "id": str(school.id),
                    "name": school.name,
                    "code": school.code,
                },
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
                "role": role.role_name,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            description="OTP verified successfully.",
            status=status.HTTP_200_OK,
        )



class SchoolLeadListAPIView(APIView):

    def get(self, request):

        if not request.user.is_authenticated:
            return Response(
                {"message": "Unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        leads = SchoolLead.objects.all()

        return Response(
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
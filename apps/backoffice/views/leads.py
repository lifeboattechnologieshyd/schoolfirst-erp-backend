import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.school.models import SchoolLead, School
from apps.core.models import UserMaster, UserOTP, Roles, UserRoles


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
            "channel",
        ]

        missing = [
            field
            for field in required_fields
            if not request.data.get(field)
        ]

        if missing:
            return Response(
                {
                    "message": "Missing required fields",
                    "fields": missing,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = request.data.get("phone_number")
        email = request.data.get("email")
        channel = request.data.get("channel")

        if not phone_number and not email:
            return Response(
                {
                    "message": "phone_number or email is required"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = SchoolLead.objects.create(
            school_name=request.data["school_name"],
            contact_person=request.data["contact_person"],
            number_of_students=request.data["number_of_students"],
            location=request.data["location"],
            phone_number=phone_number,
            email=email,
        )
        otp = 1234

        otp = generate_otp()

        UserOTP.objects.create(
            mobile=phone_number if channel == "mobile" else None,
            email=email if channel == "email" else None,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=15),
        )

        # send sms/email here

        return Response(
            {
                "message": "OTP sent successfully",
                "lead_id": str(lead.id),
                "otp": otp if settings.DEBUG else None,
            },
            status=status.HTTP_200_OK,
        )

class SchoolLeadVerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):

        lead_id = request.data.get("lead_id")
        otp = request.data.get("otp")

        if not lead_id or not otp:
            return Response(
                {
                    "message": "lead_id and otp are required"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = get_object_or_404(
            SchoolLead,
            id=lead_id,
        )

        otp_obj = UserOTP.objects.filter(
            otp=otp,
            is_used=False,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at").first()

        if not otp_obj:
            return Response(
                {
                    "message": "Invalid or expired OTP"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

        lead.is_verified = True
        lead.is_mobile_verified = True
        lead.save()

        school, _ = School.objects.get_or_create(
            name=lead.school_name,
        )

        user, _ = UserMaster.objects.get_or_create(
            email=lead.email,
            defaults={
                "mobile": lead.phone_number,
                "is_active": True,
            },
        )

        role, _ = Roles.objects.get_or_create(
            role_name="SYSTEM_ADMIN",
            defaults={
                "description": "School System Admin"
            },
        )

        UserRoles.objects.get_or_create(
            user=user,
            school=school,
            role=role,
        )

        return Response(
            {
                "message": "OTP verified successfully",
                "school_id": str(school.id),
                "user_id": str(user.id),
                "role": role.role_name,
            },
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
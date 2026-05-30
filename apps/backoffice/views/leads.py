import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from apps.school.models import SchoolLead, School
from apps.core.models import UserMaster, UserOTP, Roles, UserRoles


def is_super_admin(user):
    roles = getattr(user, "user_role", []) or []
    return "SUPER_ADMIN" in roles


def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"


def create_system_admin_from_lead(lead: SchoolLead):
    """
    Convert verified lead into school + admin user.
    Adjust fields if your UserMaster/School models differ.
    """
    if lead.is_converted:
        return None, None, None

    school, _ = School.objects.get_or_create(
        name=lead.school_name or "Unnamed School",
        defaults={
            # add any required school fields here
        },
    )

    identifier = lead.phone_number or lead.email

    user_defaults = {
        "email": lead.email,
        "phone_number": lead.phone_number,
        "is_active": True,
    }

    user, _ = UserMaster.objects.get_or_create(
        username=identifier,
        defaults=user_defaults,
    )

    role, _ = Roles.objects.get_or_create(
        role_name="SYSTEM_ADMIN",
        defaults={"description": "School system admin"},
    )

    UserRoles.objects.get_or_create(
        user=user,
        school=school,
        role=role,
    )

    lead.is_converted = True
    lead.verification_status = SchoolLead.VerificationStatus.CONVERTED
    lead.save(update_fields=["is_converted", "verification_status", "updated_at"])

    return school, user, role


class SchoolLeadRequestOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        school_name = request.data.get("school_name")
        contact_person = request.data.get("contact_person")
        number_of_students = request.data.get("number_of_students")
        location = request.data.get("location")
        phone_number = request.data.get("phone_number")
        email = request.data.get("email")
        channel = request.data.get("channel")

        if not phone_number and not email:
            return Response(
                {"message": "Either phone_number or email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if channel not in ["mobile", "email"]:
            return Response(
                {"message": "channel must be mobile or email"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if channel == "mobile" and not phone_number:
            return Response(
                {"message": "phone_number is required for mobile OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if channel == "email" and not email:
            return Response(
                {"message": "email is required for email OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead, _ = SchoolLead.objects.update_or_create(
            phone_number=phone_number if phone_number else None,
            email=email if email else None,
            defaults={
                "school_name": school_name,
                "contact_person": contact_person,
                "number_of_students": number_of_students,
                "location": location,
                # "verification_status": SchoolLead.VerificationStatus.OTP_SENT,
            },
        )
        otp =1234

        # otp = generate_otp()

        expires_at = timezone.now() + timedelta(minutes=15)

        UserOTP.objects.create(
            user_id=None,
            mobile=phone_number if channel == "mobile" else None,
            email=email if channel == "email" else None,
            otp=otp,
            expires_at=expires_at,
            is_used=False,
        )

        return Response(
            {
                "message": "OTP sent successfully",
                "lead_id": str(lead.id),
                "otp": otp if getattr(settings, "DEBUG", False) else None,
            },
            status=status.HTTP_200_OK,
        )


class SchoolLeadVerifyOTPAndConvertAPIView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        lead_id = request.data.get("lead_id")
        channel = request.data.get("channel")
        otp = request.data.get("otp")

        if not lead_id or not channel or not otp:
            return Response(
                {"message": "lead_id, channel and otp are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = get_object_or_404(SchoolLead, id=lead_id)

        otp_qs = UserOTP.objects.filter(
            otp=otp,
            is_used=False,
            expires_at__gt=timezone.now(),
        )

        if channel == "mobile":
            otp_obj = otp_qs.filter(mobile=lead.phone_number).order_by("-created_at").first()
            if not otp_obj:
                return Response({"message": "Invalid or expired mobile OTP"}, status=status.HTTP_400_BAD_REQUEST)
            otp_obj.is_used = True
            otp_obj.save(update_fields=["is_used"])
            lead.is_mobile_verified = True

        elif channel == "email":
            otp_obj = otp_qs.filter(email=lead.email).order_by("-created_at").first()
            if not otp_obj:
                return Response({"message": "Invalid or expired email OTP"}, status=status.HTTP_400_BAD_REQUEST)
            otp_obj.is_used = True
            otp_obj.save(update_fields=["is_used"])
            lead.is_email_verified = True

        else:
            return Response({"message": "Invalid channel"}, status=status.HTTP_400_BAD_REQUEST)

        lead.is_verified = bool(lead.is_mobile_verified or lead.is_email_verified)
        # lead.verification_status = SchoolLead.VerificationStatus.VERIFIED
        lead.save()

        school, user, role = create_system_admin_from_lead(lead)

        return Response(
            {
                "message": "OTP verified successfully and system admin created",
                "lead_id": str(lead.id),
                "school_id": str(school.id) if school else None,
                "user_id": str(user.id) if user else None,
                "role": role.role_name if role else None,
                "is_verified": lead.is_verified,
                "is_converted": lead.is_converted,
            },
            status=status.HTTP_200_OK,
        )


class SchoolLeadListAPIView(APIView):
    def get(self, request):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        leads = SchoolLead.objects.all()
        data = [
            {
                "id": str(lead.id),
                "school_name": lead.school_name,
                "contact_person": lead.contact_person,
                "number_of_students": lead.number_of_students,
                "location": lead.location,
                "phone_number": lead.phone_number,
                "email": lead.email,
                "verification_status": lead.verification_status,
                "is_verified": lead.is_verified,
                "is_converted": lead.is_converted,
            }
            for lead in leads
        ]
        return Response({"data": data}, status=status.HTTP_200_OK)
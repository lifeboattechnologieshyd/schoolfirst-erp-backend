import secrets
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.school.models import SchoolLead
from apps.core.models import UserMaster, UserOTP, Roles, UserRoles
from apps.school.models import School


def is_super_admin(user):
    roles = getattr(user, "user_role", []) or []
    return "SUPER_ADMIN" in roles


class SchoolLeadListCreateAPIView(APIView):
    """
    GET  -> super admin only
    POST -> create lead
    """

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
                "is_mobile_verified": lead.is_mobile_verified,
                "is_email_verified": lead.is_email_verified,
                "is_verified": lead.is_verified,
                "created_at": lead.created_at,
                "updated_at": lead.updated_at,
            }
            for lead in leads
        ]
        return Response({"data": data}, status=status.HTTP_200_OK)

    def post(self, request):
        required_fields = ["school_name", "contact_person", "number_of_students", "location", "phone_number", "email"]
        missing = [field for field in required_fields if not request.data.get(field)]
        if missing:
            return Response(
                {"message": "Missing required fields", "missing_fields": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = SchoolLead.objects.create(
            school_name=request.data["school_name"],
            contact_person=request.data["contact_person"],
            number_of_students=request.data["number_of_students"],
            location=request.data["location"],
            phone_number=request.data["phone_number"],
            email=request.data["email"],
        )

        return Response(
            {
                "message": "School lead created successfully",
                "data": {
                    "id": str(lead.id),
                    "school_name": lead.school_name,
                    "contact_person": lead.contact_person,
                    "number_of_students": lead.number_of_students,
                    "location": lead.location,
                    "phone_number": lead.phone_number,
                    "email": lead.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class SchoolLeadDetailAPIView(APIView):
    def get(self, request, lead_id):
        lead = get_object_or_404(SchoolLead, id=lead_id)
        return Response(
            {
                "data": {
                    "id": str(lead.id),
                    "school_name": lead.school_name,
                    "contact_person": lead.contact_person,
                    "number_of_students": lead.number_of_students,
                    "location": lead.location,
                    "phone_number": lead.phone_number,
                    "email": lead.email,
                    "is_mobile_verified": lead.is_mobile_verified,
                    "is_email_verified": lead.is_email_verified,
                    "is_verified": lead.is_verified,
                }
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, lead_id):
        lead = get_object_or_404(SchoolLead, id=lead_id)

        for field in ["school_name", "contact_person", "number_of_students", "location", "phone_number", "email"]:
            if field in request.data:
                setattr(lead, field, request.data[field])

        lead.save()

        return Response({"message": "School lead updated successfully"}, status=status.HTTP_200_OK)

    def delete(self, request, lead_id):
        lead = get_object_or_404(SchoolLead, id=lead_id)
        lead.delete()
        return Response({"message": "School lead deleted successfully"}, status=status.HTTP_200_OK)


class SchoolLeadSendOTPAPIView(APIView):
    """
    POST body:
    {
        "channel": "mobile" | "email" | "both"
    }
    """

    def post(self, request, lead_id):
        lead = get_object_or_404(SchoolLead, id=lead_id)
        channel = request.data.get("channel", "both")

        otp = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(minutes=5)

        if channel in ["mobile", "both"]:
            UserOTP.objects.create(
                user_id=None,
                mobile=lead.phone_number,
                email=None,
                otp=otp,
                expires_at=expires_at,
                is_used=False,
            )
            # Call your SMS helper here

        if channel in ["email", "both"]:
            UserOTP.objects.create(
                user_id=None,
                mobile=None,
                email=lead.email,
                otp=otp,
                expires_at=expires_at,
                is_used=False,
            )
            # Call your email helper here

        return Response(
            {
                "message": "OTP sent successfully",
                "otp": otp if getattr(settings, "DEBUG", False) else None,
            },
            status=status.HTTP_200_OK,
        )


class SchoolLeadVerifyOTPAPIView(APIView):
    """
    POST body:
    {
        "channel": "mobile" | "email",
        "otp": "123456"
    }
    """

    def post(self, request, lead_id):
        lead = get_object_or_404(SchoolLead, id=lead_id)
        channel = request.data.get("channel")
        otp = request.data.get("otp")

        if not channel or not otp:
            return Response(
                {"message": "channel and otp are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            otp_obj.save()
            lead.is_mobile_verified = True

        elif channel == "email":
            otp_obj = otp_qs.filter(email=lead.email).order_by("-created_at").first()
            if not otp_obj:
                return Response({"message": "Invalid or expired email OTP"}, status=status.HTTP_400_BAD_REQUEST)

            otp_obj.is_used = True
            otp_obj.save()
            lead.is_email_verified = True

        else:
            return Response({"message": "Invalid channel"}, status=status.HTTP_400_BAD_REQUEST)

        lead.is_verified = lead.is_mobile_verified and lead.is_email_verified
        lead.save()

        return Response(
            {
                "message": "OTP verified successfully",
                "is_verified": lead.is_verified,
                "is_mobile_verified": lead.is_mobile_verified,
                "is_email_verified": lead.is_email_verified,
            },
            status=status.HTTP_200_OK,
        )
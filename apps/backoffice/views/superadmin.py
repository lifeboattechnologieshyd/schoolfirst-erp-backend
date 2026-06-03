from rest_framework.views import APIView

from apps.core.models import UserRoles, Roles
from apps.school.models import SchoolLead
from shared.mixins import CustomResponse

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status



class CreateSuperAdminAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        # superadmin_role_exists = Roles.objects.filter(
        #     role_name="SUPERADMIN"
        # ).exists()

        # if superadmin_role_exists:
        #     return CustomResponse.errorResponse(
        #         description="SUPERADMIN role already exists.",
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        role = Roles.objects.create(
            role_name="SUPERADMIN",
            description="System Super Admin"
        )

        UserRoles.objects.create(
            user=request.user,
            role=role,
            school=None
        )

        return CustomResponse.successResponse(
            data={
                "role_id": str(role.id),
                "role_name": role.role_name,
            },
            description="SUPERADMIN role created successfully.",
            status=status.HTTP_201_CREATED,
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
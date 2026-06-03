from rest_framework.views import APIView

from apps.school.models import SchoolLead
from shared.mixins import CustomResponse


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
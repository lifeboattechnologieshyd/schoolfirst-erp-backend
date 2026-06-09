from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models import School
from apps.school.models.school import AcademicYear
from shared.helpers.rbac import check_permission
from shared.mixins import CustomResponse
from shared.permissions import HasPermission


class CreateAcademicYearAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.create"

    def post(self, request):

        school = School.objects.filter(
            id=request.data.get("school_id"),
        ).first()

        if not school:
            return CustomResponse.errorResponse(
                description="School not found",
            )

        check_permission(
            request,
            "academic_year.create",
            school.id,
        )

        if request.data.get("status") == "ACTIVE":
            AcademicYear.objects.filter(
                school=school,
                status="ACTIVE",
            ).update(
                status="INACTIVE",
            )

        academic_year = AcademicYear.objects.create(
            school=school,
            name=request.data.get("name"),
            start_date=request.data.get("start_date"),
            end_date=request.data.get("end_date"),
            status=request.data.get(
                "status",
                "ACTIVE",
            ),
        )

        return CustomResponse.successResponse(
            description="Academic year created successfully",
            data={
                "id": academic_year.id,
            },
        )


class AcademicYearListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.view"

    def get(self, request):

        school_id = request.GET.get("school_id")

        check_permission(
            request,
            "academic_year.view",
            school_id,
        )

        queryset = AcademicYear.objects.filter(
            school_id=school_id,
        )

        data = []

        for obj in queryset:

            data.append({
                "id": obj.id,
                "name": obj.name,
                "start_date": obj.start_date,
                "end_date": obj.end_date,
                "status": obj.status,
            })

        return CustomResponse.successResponse(
            data=data,
        )

class UpdateAcademicYearAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "academic_year.update"

    def put(
        self,
        request,
        academic_year_id,
    ):

        academic_year = AcademicYear.objects.filter(
            id=academic_year_id,
        ).first()

        if not academic_year:
            return CustomResponse.errorResponse(
                description="Academic year not found",
            )

        check_permission(
            request,
            "academic_year.update",
            academic_year.school_id,
        )

        if request.data.get("status") == "ACTIVE":
            AcademicYear.objects.filter(
                school=academic_year.school,
            ).exclude(
                id=academic_year.id,
            ).update(
                status="INACTIVE",
            )

        academic_year.name = request.data.get(
            "name",
            academic_year.name,
        )

        academic_year.start_date = request.data.get(
            "start_date",
            academic_year.start_date,
        )

        academic_year.end_date = request.data.get(
            "end_date",
            academic_year.end_date,
        )

        academic_year.status = request.data.get(
            "status",
            academic_year.status,
        )

        academic_year.save()

        return CustomResponse.successResponse(
            description="Academic year updated successfully",
        )
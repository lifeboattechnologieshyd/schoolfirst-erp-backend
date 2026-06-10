from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.school.models import School
from apps.school.models.school import AcademicYear, Grade, Section
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


class CreateGradeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        check_permission(
            request=request,
            permission_name="grade.create",
        )
        school = School.objects.filter(

            id=request.data.get("school_id"),

        ).first()

        academic_year = AcademicYear.objects.filter(
            id=request.data.get("academic_year_id"),
        ).first()

        if academic_year is None:
            return CustomResponse.errorResponse(
                description="Academic Year not found.",
            )

        if Grade.objects.filter(
            academic_year=academic_year,
            name=request.data.get("name"),
        ).exists():
            return CustomResponse.errorResponse(
                description="Grade already exists.",
            )

        grade = Grade.objects.create(
            school=school,
            academic_year=academic_year,
            name=request.data.get("name"),
            status=request.data.get(
                "status",
                Grade.Status.ACTIVE,
            ),
        )

        return CustomResponse.successResponse(
            description="Grade created successfully.",
            data={
                "id": str(grade.id),
            },
        )

class GradeListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        check_permission(
            request=request,
            permission_name="grade.view",
        )

        grades = Grade.objects.select_related(
            "school",
            "academic_year",
        ).all()

        data = []

        for grade in grades:

            data.append(
                {
                    "id": grade.id,
                    "school": grade.school.name,
                    "academic_year": grade.academic_year.name,
                    "name": grade.name,
                    "code": grade.code,
                    "display_order": grade.display_order,
                    "status": grade.status,
                }
            )

        return CustomResponse.successResponse(
            data=data,
        )
class UpdateGradeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def put(
        self,
        request,
        grade_id,
    ):

        check_permission(
            request=request,
            permission_name="grade.update",
        )

        grade = Grade.objects.filter(
            id=grade_id,
        ).first()

        if grade is None:
            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        grade.name = request.data.get(
            "name",
            grade.name,
        )



        grade.status = request.data.get(
            "status",
            grade.status,
        )

        grade.save()

        return CustomResponse.successResponse(
            description="Grade updated successfully.",
        )

class CreateSectionAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        check_permission(
            request=request,
            permission_name="section.create",
        )

        grade = Grade.objects.filter(
            id=request.data.get("grade_id"),
        ).first()

        if grade is None:
            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        if Section.objects.filter(
            grade=grade,
            name=request.data.get("name"),
        ).exists():
            return CustomResponse.errorResponse(
                description="Section already exists.",
            )

        section = Section.objects.create(
            grade=grade,
            name=request.data.get("name"),
            capacity=request.data.get("capacity"),
            status=request.data.get(
                "status",
                Section.Status.ACTIVE,
            ),
        )

        return CustomResponse.successResponse(
            description="Section created successfully.",
            data={
                "id": str(section.id),
            },
        )

class SectionListAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        check_permission(
            request=request,
            permission_name="section.view",
        )

        sections = Section.objects.select_related(
            "grade",
        ).all()

        data = []

        for section in sections:

            data.append(
                {
                    "id": section.id,
                    "name": section.name,
                    "grade": section.grade.name,
                    "capacity": section.capacity,
                    "status": section.status,
                }
            )

        return CustomResponse.successResponse(
            data=data,
        )

class UpdateSectionAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def put(
        self,
        request,
        section_id,
    ):

        check_permission(
            request=request,
            permission_name="section.update",
        )

        section = Section.objects.filter(
            id=section_id,
        ).first()

        if section is None:
            return CustomResponse.errorResponse(
                description="Section not found.",
            )

        section.name = request.data.get(
            "name",
            section.name,
        )

        section.capacity = request.data.get(
            "capacity",
            section.capacity,
        )

        section.status = request.data.get(
            "status",
            section.status,
        )

        section.save()

        return CustomResponse.successResponse(
            description="Section updated successfully.",
        )
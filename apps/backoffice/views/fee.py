from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.fee.models import FeeType, FeeTemplateItem, FeeTemplate
from apps.school.models.school import AcademicYear
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission


class CreateFeeTypeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_type.create"

    def post(self, request):

        school = request.school

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found.",
            )

        name = str(
            request.data.get(
                "name",
                "",
            )
        ).strip()

        if not name:

            return CustomResponse.errorResponse(
                description="Fee type name is required.",
            )

        if FeeType.objects.filter(
            school=school,
            name=name,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee type already exists.",
            )

        fee_type = FeeType.objects.create(

            school=school,

            name=name,

            is_optional=request.data.get(
                "is_optional",
                False,
            ),

            description=request.data.get(
                "description",
            ),

        )

        return CustomResponse.successResponse(

            description="Fee type created successfully.",

            data={
                "id": str(fee_type.id),
            },

        )

class FeeTypeListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_type.view"

    def get(self, request):

        school = request.school

        queryset = FeeType.objects.filter(
            school=school,
        )

        search = request.GET.get(
            "search",
        )

        if search:

            queryset = queryset.filter(
                name__icontains=search,
            )

        paginator = CustomPageNumberPagination()

        queryset = paginator.paginate_queryset(
            queryset.order_by("name"),
            request,
        )

        data = []

        for obj in queryset:

            data.append({

                "id": str(obj.id),

                "name": obj.name,

                "is_optional": obj.is_optional,

                "description": obj.description,

            })

        return paginator.get_paginated_response(
            data,
        )

class UpdateFeeTypeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_type.update"

    def put(
        self,
        request,
        fee_type_id,
    ):

        school = request.school

        fee_type = FeeType.objects.filter(
            id=fee_type_id,
            school=school,
        ).first()

        if fee_type is None:

            return CustomResponse.errorResponse(
                description="Fee type not found.",
            )

        name = request.data.get(
            "name",
            fee_type.name,
        ).strip()

        if FeeType.objects.filter(
            school=school,
            name=name,
        ).exclude(
            id=fee_type.id,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee type already exists.",
            )

        fee_type.name = name

        fee_type.is_optional = request.data.get(
            "is_optional",
            fee_type.is_optional,
        )

        fee_type.description = request.data.get(
            "description",
            fee_type.description,
        )

        fee_type.save()

        return CustomResponse.successResponse(
            description="Fee type updated successfully.",
        )

class DeleteFeeTypeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_type.delete"

    def delete(
        self,
        request,
        fee_type_id,
    ):

        school = request.school

        fee_type = FeeType.objects.filter(
            id=fee_type_id,
            school=school,
        ).first()

        if fee_type is None:

            return CustomResponse.errorResponse(
                description="Fee type not found.",
            )

        if FeeTemplateItem.objects.filter(
            fee_type=fee_type,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee type is already used in fee templates.",
            )

        fee_type.delete()

        return CustomResponse.successResponse(
            description="Fee type deleted successfully.",
        )

class CreateFeeTemplateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template.create"

    def post(self, request):

        school = request.school

        if school is None:

            return CustomResponse.errorResponse(
                description="School not found.",
            )

        academic_year = AcademicYear.objects.filter(
            id=request.data.get("academic_year_id"),
            school=school,
        ).first()

        if academic_year is None:

            return CustomResponse.errorResponse(
                description="Academic year not found.",
            )

        grade = Grade.objects.filter(
            id=request.data.get("grade_id"),
            school=school,
        ).first()

        if grade is None:

            return CustomResponse.errorResponse(
                description="Grade not found.",
            )

        name = str(
            request.data.get(
                "name",
                "",
            )
        ).strip()

        if not name:

            return CustomResponse.errorResponse(
                description="Template name is required.",
            )

        if FeeTemplate.objects.filter(
            school=school,
            academic_year=academic_year,
            grade=grade,
            name=name,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee template already exists.",
            )

        fee_template = FeeTemplate.objects.create(

            school=school,

            academic_year=academic_year,

            grade=grade,

            name=name,

            is_active=request.data.get(
                "is_active",
                True,
            ),

        )

        return CustomResponse.successResponse(

            description="Fee template created successfully.",

            data={
                "id": str(fee_template.id),
            },

        )

class FeeTemplateListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template.view"

    def get(self, request):

        school = request.school

        queryset = FeeTemplate.objects.select_related(
            "academic_year",
            "grade",
        ).filter(
            school=school,
        )

        academic_year_id = request.GET.get(
            "academic_year_id",
        )

        grade_id = request.GET.get(
            "grade_id",
        )

        search = request.GET.get(
            "search",
        )

        if academic_year_id:

            queryset = queryset.filter(
                academic_year_id=academic_year_id,
            )

        if grade_id:

            queryset = queryset.filter(
                grade_id=grade_id,
            )

        if search:

            queryset = queryset.filter(
                name__icontains=search,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by("grade__display_order"),
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "name": obj.name,

                "academic_year": {

                    "id": str(obj.academic_year.id),

                    "name": obj.academic_year.name,

                },

                "grade": {

                    "id": str(obj.grade.id),

                    "name": obj.grade.name,

                },

                "is_active": obj.is_active,

            })

        return CustomResponse.successResponse(

            data=data,

            total=queryset.count(),

        )

class FeeTemplateDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template.view"

    def get(
        self,
        request,
        fee_template_id,
    ):

        school = request.school

        fee_template = FeeTemplate.objects.select_related(
            "academic_year",
            "grade",
        ).filter(
            id=fee_template_id,
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        return CustomResponse.successResponse(

            data={

                "id": str(fee_template.id),

                "name": fee_template.name,

                "academic_year": {

                    "id": str(fee_template.academic_year.id),

                    "name": fee_template.academic_year.name,

                },

                "grade": {

                    "id": str(fee_template.grade.id),

                    "name": fee_template.grade.name,

                },

                "is_active": fee_template.is_active,

            }

        )

class UpdateFeeTemplateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template.update"

    def put(
        self,
        request,
        fee_template_id,
    ):

        school = request.school

        fee_template = FeeTemplate.objects.filter(
            id=fee_template_id,
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        name = request.data.get(
            "name",
            fee_template.name,
        ).strip()

        if FeeTemplate.objects.filter(
            school=school,
            academic_year=fee_template.academic_year,
            grade=fee_template.grade,
            name=name,
        ).exclude(
            id=fee_template.id,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee template already exists.",
            )

        fee_template.name = name

        fee_template.is_active = request.data.get(
            "is_active",
            fee_template.is_active,
        )

        fee_template.save()

        return CustomResponse.successResponse(
            description="Fee template updated successfully.",
        )

class DeleteFeeTemplateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template.delete"

    def delete(
        self,
        request,
        fee_template_id,
    ):

        school = request.school

        fee_template = FeeTemplate.objects.filter(
            id=fee_template_id,
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        if FeeTemplateItem.objects.filter(
            fee_template=fee_template,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee template contains fee items and cannot be deleted.",
            )

        fee_template.delete()

        return CustomResponse.successResponse(
            description="Fee template deleted successfully.",
        )
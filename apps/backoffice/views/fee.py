from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.fee.models import FeeType, FeeTemplateItem, FeeTemplate, FeeCollectionPlan, FeeInstallment, \
    FeeInstallmentItem, LateFeeRule, FeeConcession, StudentFeeAssignment, StudentFee
from apps.school.models.school import AcademicYear, Grade, Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.fee import generate_student_fees


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
            total=queryset.count(),


            data=data


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

class CreateFeeTemplateItemAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template_item.create"

    def post(self, request):

        school = request.school

        fee_template = FeeTemplate.objects.filter(
            id=request.data.get("fee_template_id"),
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        fee_type = FeeType.objects.filter(
            id=request.data.get("fee_type_id"),
            school=school,
        ).first()

        if fee_type is None:

            return CustomResponse.errorResponse(
                description="Fee type not found.",
            )

        if FeeTemplateItem.objects.filter(
            fee_template=fee_template,
            fee_type=fee_type,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee type already added.",
            )

        amount = request.data.get(
            "amount",
        )

        if not amount:

            return CustomResponse.errorResponse(
                description="Amount is required.",
            )

        item = FeeTemplateItem.objects.create(

            fee_template=fee_template,

            fee_type=fee_type,

            amount=amount,

            is_mandatory=request.data.get(
                "is_mandatory",
                True,
            ),

        )

        return CustomResponse.successResponse(

            description="Fee template item created successfully.",

            data={
                "id": str(item.id),
            },

        )

class FeeTemplateItemListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template_item.view"

    def get(self, request):

        school = request.school

        queryset = FeeTemplateItem.objects.select_related(

            "fee_template",

            "fee_type",

        ).filter(

            fee_template__school=school,

        )

        fee_template_id = request.GET.get(
            "fee_template_id",
        )

        if fee_template_id:

            queryset = queryset.filter(
                fee_template_id=fee_template_id,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by(
                "fee_type__name",
            ),
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "fee_template": {

                    "id": str(obj.fee_template.id),

                    "name": obj.fee_template.name,

                },

                "fee_type": {

                    "id": str(obj.fee_type.id),

                    "name": obj.fee_type.name,

                },

                "amount": obj.amount,

                "is_mandatory": obj.is_mandatory,

            })

        return CustomResponse.successResponse(

            data=data,

            total=queryset.count(),

        )
class FeeTemplateItemDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template_item.view"

    def get(
        self,
        request,
        fee_template_item_id,
    ):

        school = request.school

        item = FeeTemplateItem.objects.select_related(

            "fee_template",

            "fee_type",

        ).filter(

            id=fee_template_item_id,

            fee_template__school=school,

        ).first()

        if item is None:

            return CustomResponse.errorResponse(
                description="Fee template item not found.",
            )

        return CustomResponse.successResponse(

            data={

                "id": str(item.id),

                "fee_template": {

                    "id": str(item.fee_template.id),

                    "name": item.fee_template.name,

                },

                "fee_type": {

                    "id": str(item.fee_type.id),

                    "name": item.fee_type.name,

                },

                "amount": item.amount,

                "is_mandatory": item.is_mandatory,

            }

        )
class UpdateFeeTemplateItemAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template_item.update"

    def put(
        self,
        request,
        fee_template_item_id,
    ):

        school = request.school

        item = FeeTemplateItem.objects.select_related(
            "fee_template",
        ).filter(
            id=fee_template_item_id,
            fee_template__school=school,
        ).first()

        if item is None:

            return CustomResponse.errorResponse(
                description="Fee template item not found.",
            )

        item.amount = request.data.get(
            "amount",
            item.amount,
        )

        item.is_mandatory = request.data.get(
            "is_mandatory",
            item.is_mandatory,
        )

        item.save()

        return CustomResponse.successResponse(
            description="Fee template item updated successfully.",
        )

class DeleteFeeTemplateItemAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_template_item.delete"

    def delete(
        self,
        request,
        fee_template_item_id,
    ):

        school = request.school

        item = FeeTemplateItem.objects.filter(

            id=fee_template_item_id,

            fee_template__school=school,

        ).first()

        if item is None:

            return CustomResponse.errorResponse(
                description="Fee template item not found.",
            )

        item.delete()

        return CustomResponse.successResponse(
            description="Fee template item deleted successfully.",
        )

class CreateFeeCollectionPlanAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_collection_plan.create"

    def post(self, request):

        school = request.school

        fee_template = FeeTemplate.objects.filter(
            id=request.data.get("fee_template_id"),
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        if FeeCollectionPlan.objects.filter(
            fee_template=fee_template,
        ).exists():

            return CustomResponse.errorResponse(
                description="Collection plan already exists.",
            )

        plan_type = request.data.get(
            "plan_type",
        )

        if plan_type not in FeeCollectionPlan.PlanType.values:

            return CustomResponse.errorResponse(
                description="Invalid plan type.",
            )

        collection_plan = FeeCollectionPlan.objects.create(

            fee_template=fee_template,

            plan_type=plan_type,

        )

        return CustomResponse.successResponse(

            description="Fee collection plan created successfully.",

            data={
                "id": str(collection_plan.id),
            },

        )

class FeeCollectionPlanListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_collection_plan.view"

    def get(self, request):

        school = request.school

        queryset = FeeCollectionPlan.objects.select_related(
            "fee_template",
            "fee_template__grade",
            "fee_template__academic_year",
        ).filter(
            fee_template__school=school,
        )

        academic_year_id = request.GET.get(
            "academic_year_id",
        )

        grade_id = request.GET.get(
            "grade_id",
        )

        if academic_year_id:

            queryset = queryset.filter(
                fee_template__academic_year_id=academic_year_id,
            )

        if grade_id:

            queryset = queryset.filter(
                fee_template__grade_id=grade_id,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "plan_type": obj.plan_type,

                "fee_template": {

                    "id": str(obj.fee_template.id),

                    "name": obj.fee_template.name,

                },

                "grade": obj.fee_template.grade.name,

                "academic_year": obj.fee_template.academic_year.name,

            })

        return CustomResponse.successResponse(
            data=data,
            total=queryset.count(),
        )
class FeeCollectionPlanDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_collection_plan.view"

    def get(
        self,
        request,
        collection_plan_id,
    ):

        school = request.school

        collection_plan = FeeCollectionPlan.objects.select_related(
            "fee_template",
            "fee_template__grade",
            "fee_template__academic_year",
        ).filter(
            id=collection_plan_id,
            fee_template__school=school,
        ).first()

        if collection_plan is None:

            return CustomResponse.errorResponse(
                description="Collection plan not found.",
            )

        return CustomResponse.successResponse(

            data={

                "id": str(collection_plan.id),

                "plan_type": collection_plan.plan_type,

                "fee_template": {

                    "id": str(collection_plan.fee_template.id),

                    "name": collection_plan.fee_template.name,

                },

                "grade": {

                    "id": str(collection_plan.fee_template.grade.id),

                    "name": collection_plan.fee_template.grade.name,

                },

                "academic_year": {

                    "id": str(collection_plan.fee_template.academic_year.id),

                    "name": collection_plan.fee_template.academic_year.name,

                },

            }

        )
class UpdateFeeCollectionPlanAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_collection_plan.update"

    def put(
        self,
        request,
        collection_plan_id,
    ):

        school = request.school

        collection_plan = FeeCollectionPlan.objects.select_related(
            "fee_template",
        ).filter(
            id=collection_plan_id,
            fee_template__school=school,
        ).first()

        if collection_plan is None:

            return CustomResponse.errorResponse(
                description="Collection plan not found.",
            )

        plan_type = request.data.get(
            "plan_type",
            collection_plan.plan_type,
        )

        if plan_type not in FeeCollectionPlan.PlanType.values:

            return CustomResponse.errorResponse(
                description="Invalid plan type.",
            )

        collection_plan.plan_type = plan_type

        collection_plan.save()

        return CustomResponse.successResponse(
            description="Collection plan updated successfully.",
        )

class CreateFeeInstallmentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment.create"

    def post(self, request):

        school = request.school

        collection_plan = FeeCollectionPlan.objects.select_related(
            "fee_template",
        ).filter(
            id=request.data.get("collection_plan_id"),
            fee_template__school=school,
        ).first()

        if collection_plan is None:

            return CustomResponse.errorResponse(
                description="Collection plan not found.",
            )

        name = str(
            request.data.get(
                "name",
                "",
            )
        ).strip()

        if not name:

            return CustomResponse.errorResponse(
                description="Installment name is required.",
            )

        if FeeInstallment.objects.filter(
            collection_plan=collection_plan,
            name=name,
        ).exists():

            return CustomResponse.errorResponse(
                description="Installment already exists.",
            )

        installment = FeeInstallment.objects.create(

            collection_plan=collection_plan,

            name=name,

            due_date=request.data.get(
                "due_date",
            ),

            order=request.data.get(
                "order",
                1,
            ),

        )

        return CustomResponse.successResponse(

            description="Fee installment created successfully.",

            data={
                "id": str(installment.id),
            },

        )

class FeeInstallmentListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment.view"

    def get(self, request):

        school = request.school

        queryset = FeeInstallment.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            collection_plan__fee_template__school=school,
        )

        collection_plan_id = request.GET.get(
            "collection_plan_id",
        )

        if collection_plan_id:

            queryset = queryset.filter(
                collection_plan_id=collection_plan_id,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by(
                "order",
            ),
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "name": obj.name,

                "due_date": obj.due_date,

                "order": obj.order,

                "collection_plan": {

                    "id": str(obj.collection_plan.id),

                    "plan_type": obj.collection_plan.plan_type,

                },

            })

        return CustomResponse.successResponse(
            data=data,
            total=queryset.count(),
        )

class FeeInstallmentDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment.view"

    def get(
        self,
        request,
        installment_id,
    ):

        school = request.school

        installment = FeeInstallment.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            id=installment_id,
            collection_plan__fee_template__school=school,
        ).first()

        if installment is None:

            return CustomResponse.errorResponse(
                description="Fee installment not found.",
            )

        return CustomResponse.successResponse(

            data={

                "id": str(installment.id),

                "name": installment.name,

                "due_date": installment.due_date,

                "order": installment.order,

                "collection_plan": {

                    "id": str(installment.collection_plan.id),

                    "plan_type": installment.collection_plan.plan_type,

                },

            },

        )

class UpdateFeeInstallmentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment.update"

    def put(
        self,
        request,
        installment_id,
    ):

        school = request.school

        installment = FeeInstallment.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            id=installment_id,
            collection_plan__fee_template__school=school,
        ).first()

        if installment is None:

            return CustomResponse.errorResponse(
                description="Fee installment not found.",
            )

        name = request.data.get(
            "name",
            installment.name,
        ).strip()

        if FeeInstallment.objects.filter(
            collection_plan=installment.collection_plan,
            name=name,
        ).exclude(
            id=installment.id,
        ).exists():

            return CustomResponse.errorResponse(
                description="Installment already exists.",
            )

        installment.name = name

        installment.due_date = request.data.get(
            "due_date",
            installment.due_date,
        )

        installment.order = request.data.get(
            "order",
            installment.order,
        )

        installment.save()

        return CustomResponse.successResponse(
            description="Fee installment updated successfully.",
        )

class CreateFeeInstallmentItemAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment_item.create"

    def post(self, request):

        school = request.school

        installment = FeeInstallment.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            id=request.data.get("installment_id"),
            collection_plan__fee_template__school=school,
        ).first()

        if installment is None:

            return CustomResponse.errorResponse(
                description="Installment not found.",
            )

        fee_template_item = FeeTemplateItem.objects.select_related(
            "fee_template",
        ).filter(
            id=request.data.get("fee_template_item_id"),
            fee_template__school=school,
        ).first()

        if fee_template_item is None:

            return CustomResponse.errorResponse(
                description="Fee template item not found.",
            )

        if (
            installment.collection_plan.fee_template_id
            != fee_template_item.fee_template_id
        ):

            return CustomResponse.errorResponse(
                description="Fee template mismatch.",
            )

        if FeeInstallmentItem.objects.filter(
            installment=installment,
            fee_template_item=fee_template_item,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee installment item already exists.",
            )

        amount = request.data.get("amount")

        if amount in [None, ""]:

            return CustomResponse.errorResponse(
                description="Amount is required.",
            )

        item = FeeInstallmentItem.objects.create(

            installment=installment,

            fee_template_item=fee_template_item,

            amount=amount,

        )

        return CustomResponse.successResponse(

            description="Fee installment item created successfully.",

            data={
                "id": str(item.id),
            },

        )

class FeeInstallmentItemListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment_item.view"

    def get(self, request):

        school = request.school

        queryset = FeeInstallmentItem.objects.select_related(
            "installment",
            "fee_template_item",
            "fee_template_item__fee_type",
            "fee_template_item__fee_template",
        ).filter(
            installment__collection_plan__fee_template__school=school,
        )

        installment_id = request.GET.get(
            "installment_id",
        )

        if installment_id:

            queryset = queryset.filter(
                installment_id=installment_id,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by(
                "fee_template_item__fee_type__name",
            ),
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "installment": {

                    "id": str(obj.installment.id),

                    "name": obj.installment.name,

                },

                "fee_template_item": {

                    "id": str(obj.fee_template_item.id),

                    "fee_type": obj.fee_template_item.fee_type.name,

                },

                "amount": obj.amount,

            })

        return CustomResponse.successResponse(
            data=data,
            total=queryset.count(),
        )
class FeeInstallmentItemDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment_item.view"

    def get(
        self,
        request,
        installment_item_id,
    ):

        school = request.school

        item = FeeInstallmentItem.objects.select_related(
            "installment",
            "fee_template_item",
            "fee_template_item__fee_type",
        ).filter(
            id=installment_item_id,
            installment__collection_plan__fee_template__school=school,
        ).first()

        if item is None:

            return CustomResponse.errorResponse(
                description="Fee installment item not found.",
            )

        return CustomResponse.successResponse(

            data={

                "id": str(item.id),

                "installment": {

                    "id": str(item.installment.id),

                    "name": item.installment.name,

                },

                "fee_template_item": {

                    "id": str(item.fee_template_item.id),

                    "fee_type": item.fee_template_item.fee_type.name,

                },

                "amount": item.amount,

            },

        )


class UpdateFeeInstallmentItemAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_installment_item.update"

    def put(
        self,
        request,
        installment_item_id,
    ):

        school = request.school

        item = FeeInstallmentItem.objects.select_related(
            "installment",
            "installment__collection_plan",
            "installment__collection_plan__fee_template",
        ).filter(
            id=installment_item_id,
            installment__collection_plan__fee_template__school=school,
        ).first()

        if item is None:

            return CustomResponse.errorResponse(
                description="Fee installment item not found.",
            )

        item.amount = request.data.get(
            "amount",
            item.amount,
        )

        item.save()

        return CustomResponse.successResponse(
            description="Fee installment item updated successfully.",
        )

class CreateLateFeeRuleAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "late_fee_rule.create"

    def post(self, request):

        school = request.school

        collection_plan = FeeCollectionPlan.objects.select_related(
            "fee_template",
        ).filter(
            id=request.data.get("collection_plan_id"),
            fee_template__school=school,
        ).first()

        if collection_plan is None:

            return CustomResponse.errorResponse(
                description="Collection plan not found.",
            )

        rule_type = request.data.get(
            "rule_type",
        )

        if rule_type not in LateFeeRule.RuleType.values:

            return CustomResponse.errorResponse(
                description="Invalid rule type.",
            )

        from_day = request.data.get(
            "from_day",
        )

        to_day = request.data.get(
            "to_day",
        )

        if from_day is None or to_day is None:

            return CustomResponse.errorResponse(
                description="from_day and to_day are required.",
            )

        if int(from_day) > int(to_day):

            return CustomResponse.errorResponse(
                description="from_day should be less than or equal to to_day.",
            )

        overlap = LateFeeRule.objects.filter(
            collection_plan=collection_plan,
            from_day__lte=to_day,
            to_day__gte=from_day,
        ).exists()

        if overlap:

            return CustomResponse.errorResponse(
                description="Late fee range overlaps existing rule.",
            )

        late_fee_rule = LateFeeRule.objects.create(

            collection_plan=collection_plan,

            from_day=from_day,

            to_day=to_day,

            rule_type=rule_type,

            value=request.data.get(
                "value",
            ),

        )

        return CustomResponse.successResponse(

            description="Late fee rule created successfully.",

            data={
                "id": str(late_fee_rule.id),
            },

        )

class LateFeeRuleListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "late_fee_rule.view"

    def get(self, request):

        school = request.school

        queryset = LateFeeRule.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            collection_plan__fee_template__school=school,
        )

        collection_plan_id = request.GET.get(
            "collection_plan_id",
        )

        if collection_plan_id:

            queryset = queryset.filter(
                collection_plan_id=collection_plan_id,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by(
                "from_day",
            ),
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "collection_plan": {

                    "id": str(obj.collection_plan.id),

                    "plan_type": obj.collection_plan.plan_type,

                },

                "from_day": obj.from_day,

                "to_day": obj.to_day,

                "rule_type": obj.rule_type,

                "value": obj.value,

            })

        return CustomResponse.successResponse(
            data=data,
            total=queryset.count(),
        )
class LateFeeRuleDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "late_fee_rule.view"

    def get(
        self,
        request,
        late_fee_rule_id,
    ):

        school = request.school

        rule = LateFeeRule.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            id=late_fee_rule_id,
            collection_plan__fee_template__school=school,
        ).first()

        if rule is None:

            return CustomResponse.errorResponse(
                description="Late fee rule not found.",
            )

        return CustomResponse.successResponse(

            data={

                "id": str(rule.id),

                "collection_plan": {

                    "id": str(rule.collection_plan.id),

                    "plan_type": rule.collection_plan.plan_type,

                },

                "from_day": rule.from_day,

                "to_day": rule.to_day,

                "rule_type": rule.rule_type,

                "value": rule.value,

            },

        )

class UpdateLateFeeRuleAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "late_fee_rule.update"

    def put(
        self,
        request,
        late_fee_rule_id,
    ):

        school = request.school

        rule = LateFeeRule.objects.select_related(
            "collection_plan",
            "collection_plan__fee_template",
        ).filter(
            id=late_fee_rule_id,
            collection_plan__fee_template__school=school,
        ).first()

        if rule is None:

            return CustomResponse.errorResponse(
                description="Late fee rule not found.",
            )

        from_day = request.data.get(
            "from_day",
            rule.from_day,
        )

        to_day = request.data.get(
            "to_day",
            rule.to_day,
        )

        if int(from_day) > int(to_day):

            return CustomResponse.errorResponse(
                description="from_day should be less than or equal to to_day.",
            )

        overlap = LateFeeRule.objects.filter(
            collection_plan=rule.collection_plan,
            from_day__lte=to_day,
            to_day__gte=from_day,
        ).exclude(
            id=rule.id,
        ).exists()

        if overlap:

            return CustomResponse.errorResponse(
                description="Late fee range overlaps existing rule.",
            )

        rule_type = request.data.get(
            "rule_type",
            rule.rule_type,
        )

        if rule_type not in LateFeeRule.RuleType.values:

            return CustomResponse.errorResponse(
                description="Invalid rule type.",
            )

        rule.from_day = from_day

        rule.to_day = to_day

        rule.rule_type = rule_type

        rule.value = request.data.get(
            "value",
            rule.value,
        )

        rule.save()

        return CustomResponse.successResponse(
            description="Late fee rule updated successfully.",
        )

class CreateFeeConcessionAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_concession.create"

    def post(self, request):

        school = request.school

        name = str(
            request.data.get(
                "name",
                "",
            )
        ).strip()

        if not name:

            return CustomResponse.errorResponse(
                description="Concession name is required.",
            )

        if FeeConcession.objects.filter(
            school=school,
            name=name,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee concession already exists.",
            )

        concession_type = request.data.get(
            "concession_type",
        )

        if concession_type not in FeeConcession.Type.values:

            return CustomResponse.errorResponse(
                description="Invalid concession type.",
            )

        value = request.data.get(
            "value",
        )

        if value in [None, ""]:

            return CustomResponse.errorResponse(
                description="Value is required.",
            )

        concession = FeeConcession.objects.create(

            school=school,

            name=name,

            concession_type=concession_type,

            value=value,

        )

        return CustomResponse.successResponse(

            description="Fee concession created successfully.",

            data={
                "id": str(concession.id),
            },

        )

class FeeConcessionListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_concession.view"

    def get(self, request):

        school = request.school

        queryset = FeeConcession.objects.filter(
            school=school,
        ).order_by(
            "name",
        )

        search = request.GET.get(
            "search",
        )

        if search:

            queryset = queryset.filter(
                name__icontains=search,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "name": obj.name,

                "concession_type": obj.concession_type,

                "value": obj.value,

            })

        return CustomResponse.successResponse(

            data=data,

            total=queryset.count(),

        )

class UpdateFeeConcessionAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_concession.update"

    def put(
        self,
        request,
        concession_id,
    ):

        school = request.school

        concession = FeeConcession.objects.filter(
            id=concession_id,
            school=school,
        ).first()

        if concession is None:

            return CustomResponse.errorResponse(
                description="Fee concession not found.",
            )

        name = request.data.get(
            "name",
            concession.name,
        ).strip()

        if FeeConcession.objects.filter(
            school=school,
            name=name,
        ).exclude(
            id=concession.id,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee concession already exists.",
            )

        concession_type = request.data.get(
            "concession_type",
            concession.concession_type,
        )

        if concession_type not in FeeConcession.Type.values:

            return CustomResponse.errorResponse(
                description="Invalid concession type.",
            )

        concession.name = name

        concession.concession_type = concession_type

        concession.value = request.data.get(
            "value",
            concession.value,
        )

        concession.save()

        return CustomResponse.successResponse(
            description="Fee concession updated successfully.",
        )

class CreateStudentFeeAssignmentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee_assignment.create"

    def post(self, request):

        school = request.school

        student = Student.objects.filter(
            id=request.data.get(
                "student_id",
            ),
            school=school,
        ).first()

        if student is None:

            return CustomResponse.errorResponse(
                description="Student not found.",
            )

        fee_template = FeeTemplate.objects.filter(
            id=request.data.get(
                "fee_template_id",
            ),
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        if StudentFeeAssignment.objects.filter(
            student=student,
            fee_template=fee_template,
        ).exists():

            return CustomResponse.errorResponse(
                description="Fee template already assigned.",
            )

        assignment = StudentFeeAssignment.objects.create(

            student=student,

            fee_template=fee_template,

            assigned_by=request.user,

        )

        return CustomResponse.successResponse(

            description="Fee template assigned successfully.",

            data={
                "id": str(assignment.id),
            },

        )

class StudentFeeAssignmentListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee_assignment.view"

    def get(self, request):

        school = request.school

        queryset = StudentFeeAssignment.objects.select_related(
            "student",
            "fee_template",
        ).filter(
            student__school=school,
        )

        student_id = request.GET.get(
            "student_id",
        )

        if student_id:

            queryset = queryset.filter(
                student_id=student_id,
            )

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
        )

        data = []

        for obj in page:

            data.append({

                "id": str(obj.id),

                "student": {

                    "id": str(obj.student.id),

                    "name": obj.student.name,

                    "admission_number": obj.student.admission_number,

                },

                "fee_template": {

                    "id": str(obj.fee_template.id),

                    "name": obj.fee_template.name,

                },

                "assigned_date": obj.assigned_date,

            })

        return CustomResponse.successResponse(
            data=data,
            total=queryset.count(),
        )

class StudentFeeListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.view"

    pagination_class = CustomPageNumberPagination

    def get(self, request):

        school = request.school

        queryset = StudentFee.objects.select_related(
            "student",
            "installment_item",
            "installment_item__installment",
            "installment_item__fee_template_item",
            "installment_item__fee_template_item__fee_type",
            "concession",
        ).filter(
            student__school=school,
        )

        student_id = request.query_params.get(
            "student_id"
        )

        status = request.query_params.get(
            "status"
        )

        if student_id:
            queryset = queryset.filter(
                student_id=student_id,
            )

        if status:
            queryset = queryset.filter(
                status=status,
            )

        paginator = self.pagination_class()

        page = paginator.paginate_queryset(
            queryset,
            request,
        )

        data = []

        for fee in page:

            data.append({

                "id": str(fee.id),

                "student": fee.student.name,

                "fee_type": fee.installment_item.fee_template_item.fee_type.name,

                "installment": fee.installment_item.installment.name,

                "amount": fee.amount,

                "concession_amount": fee.concession_amount,

                "late_fee": fee.late_fee,

                "paid_amount": fee.paid_amount,

                "balance": fee.payable_amount,

                "due_date": fee.due_date,

                "status": fee.status,

            })

        return CustomResponse.successResponse(
            data=data,
            total=queryset.count(),
        )

class StudentFeeDetailAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.view"

    def get(self, request, fee_id):

        fee = StudentFee.objects.select_related(
            "student",
            "concession",
            "installment_item",
            "installment_item__installment",
            "installment_item__fee_template_item",
            "installment_item__fee_template_item__fee_type",
        ).filter(
            id=fee_id,
        ).first()

        if fee is None:

            return CustomResponse.errorResponse(
                description="Student fee not found.",
            )

        return CustomResponse.successResponse(
            data={
                "id": str(fee.id),
                "student": fee.student.name,
                "fee_type": fee.installment_item.fee_template_item.fee_type.name,
                "installment": fee.installment_item.installment.name,
                "amount": fee.amount,
                "concession": (
                    fee.concession.name
                    if fee.concession
                    else None
                ),
                "concession_amount": fee.concession_amount,
                "late_fee": fee.late_fee,
                "paid_amount": fee.paid_amount,
                "balance": fee.payable_amount,
                "due_date": fee.due_date,
                "status": fee.status,
            }
        )
class GenerateStudentFeesAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.create"

    def post(self, request):

        school = request.school

        fee_template = FeeTemplate.objects.filter(
            id=request.data.get(
                "fee_template_id",
            ),
            school=school,
        ).first()

        if fee_template is None:

            return CustomResponse.errorResponse(
                description="Fee template not found.",
            )

        print("=" * 80)
        print("Fee Template :", fee_template.id)
        print("School :", fee_template.school)
        print("Academic Year :", fee_template.academic_year)
        print("Grade :", fee_template.grade)

        students = Student.objects.filter(
            school=school,
            academic_year=fee_template.academic_year,
            grade=fee_template.grade,
        )

        print("Students Count :", students.count())

        for student in students:

            print(
                "Student ID :", student.id,
                "Name :", student.name,
                "Grade :", student.grade_id,
                "Academic Year :", student.academic_year_id,
            )

        print("=" * 80)

        generated_count = 0

        for student in students:

            print(
                f"Generating fees for : {student.name}"
            )

            generate_student_fees(
                student=student,
                fee_template=fee_template,
            )

            generated_count += 1

        print("Generated Count :", generated_count)

        return CustomResponse.successResponse(

            description="Student fees generated successfully.",

            data={
                "students_processed": generated_count,
            },

        )

class CollectFeeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.collect"

    def post(self, request):

        fee = StudentFee.objects.filter(
            id=request.data.get(
                "student_fee_id",
            )
        ).first()

        if fee is None:

            return CustomResponse.errorResponse(
                description="Student fee not found.",
            )

        amount = Decimal(
            request.data.get(
                "amount",
                0,
            )
        )

        if amount <= 0:

            return CustomResponse.errorResponse(
                description="Invalid amount.",
            )

        if amount > fee.payable_amount:

            return CustomResponse.errorResponse(
                description="Amount exceeds balance.",
            )

        payment = StudentFeePayment.objects.create(

            student_fee=fee,

            receipt_number=uuid.uuid4().hex[:12].upper(),

            amount=amount,

            payment_mode=request.data.get(
                "payment_mode",
            ),

            transaction_id=request.data.get(
                "transaction_id",
            ),

            remarks=request.data.get(
                "remarks",
            ),

            collected_by=request.user,

        )

        fee.paid_amount += amount

        if fee.payable_amount <= 0:

            fee.status = StudentFee.Status.PAID

        else:

            fee.status = StudentFee.Status.PARTIAL

        fee.save()

        return CustomResponse.successResponse(
            description="Fee collected successfully.",
            data={
                "receipt_number": payment.receipt_number,
            },
        )

class PaymentHistoryAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.view"

    def get(self, request):

        student_id = request.query_params.get(
            "student_id"
        )

        payments = StudentFeePayment.objects.select_related(
            "student_fee",
            "student_fee__student",
        )

        if student_id:

            payments = payments.filter(
                student_fee__student_id=student_id,
            )

        data = []

        for payment in payments:

            data.append({

                "receipt_number": payment.receipt_number,

                "student": payment.student_fee.student.name,

                "amount": payment.amount,

                "payment_mode": payment.payment_mode,

                "payment_date": payment.payment_date,

                "is_cancelled": payment.is_cancelled,

            })

        return CustomResponse.successResponse(
            data=data,
        )
class OutstandingFeesAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.view"

    def get(self, request):

        fees = StudentFee.objects.filter(
            status__in=[
                StudentFee.Status.PENDING,
                StudentFee.Status.PARTIAL,
                StudentFee.Status.OVERDUE,
            ]
        )

        data = []

        for fee in fees:

            data.append({

                "student": fee.student.name,

                "balance": fee.payable_amount,

                "due_date": fee.due_date,

            })

        return CustomResponse.successResponse(
            data=data,
        )

class FeeDefaultersAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "student_fee.view"

    def get(self, request):

        today = timezone.now().date()

        fees = StudentFee.objects.filter(
            due_date__lt=today,
            status__in=[
                StudentFee.Status.PENDING,
                StudentFee.Status.PARTIAL,
            ],
        )

        data = []

        for fee in fees:

            data.append({

                "student": fee.student.name,

                "amount_due": fee.payable_amount,

                "due_date": fee.due_date,

            })

        return CustomResponse.successResponse(
            data=data,
        )
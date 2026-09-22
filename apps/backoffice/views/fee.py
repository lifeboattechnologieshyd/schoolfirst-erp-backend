import uuid
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.fee.models import FeeType, FeeTemplateItem, FeeTemplate, FeeCollectionPlan, FeeInstallment, \
    FeeInstallmentItem, LateFeeRule, FeeConcession, StudentFeeAssignment, StudentFee, StudentFeePayment, FeePlan, \
    FeePlanInstallment
from apps.school.models.school import AcademicYear, Grade, Student
from shared.mixins import CustomResponse, CustomPageNumberPagination
from shared.permissions import HasPermission
from shared.utils.fee import generate_student_fees
from shared.utils.logger import application_logger
from decimal import Decimal, InvalidOperation
from django.db import transaction, IntegrityError


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

        if not school:
            return CustomResponse.errorResponse(
                description="School is required.",
            )

        queryset = FeeTemplate.objects.select_related(
            "academic_year",
            "grade",
            "collection_plan",
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

        total = queryset.count()

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by(
                "grade__display_order",
                "name",
            ),
            request,
        )

        data = []

        for obj in page:

            collection_plan = getattr(
                obj,
                "collection_plan",
                None,
            )

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

                "collection_plan": (
                    {
                        "id": str(collection_plan.id),
                        "name": collection_plan.name,
                        "plan_type": collection_plan.plan_type,
                        "is_active": collection_plan.is_active,
                    }
                    if collection_plan
                    else None
                ),
            })

        return CustomResponse.successResponse(
            total=total,
            data=data,
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

# class CreateFeeCollectionPlanAPIView(APIView):
#
#     permission_classes = [
#         IsAuthenticated,
#         HasPermission,
#     ]
#
#     required_permission = "fee_collection_plan.create"
#
#     def post(self, request):
#
#         school = request.school
#
#         fee_template = FeeTemplate.objects.filter(
#             id=request.data.get("fee_template_id"),
#             school=school,
#         ).first()
#
#         if fee_template is None:
#
#             return CustomResponse.errorResponse(
#                 description="Fee template not found.",
#             )
#
#         if FeeCollectionPlan.objects.filter(
#             fee_template=fee_template,
#         ).exists():
#
#             return CustomResponse.errorResponse(
#                 description="Collection plan already exists.",
#             )
#
#         plan_type = request.data.get(
#             "plan_type",
#         )
#
#         if plan_type not in FeeCollectionPlan.PlanType.values:
#
#             return CustomResponse.errorResponse(
#                 description="Invalid plan type.",
#             )
#
#         collection_plan = FeeCollectionPlan.objects.create(
#
#             fee_template=fee_template,
#
#             plan_type=plan_type,
#
#         )
#
#         return CustomResponse.successResponse(
#
#             description="Fee collection plan created successfully.",
#
#             data={
#                 "id": str(collection_plan.id),
#             },
#
#         )

class CreateFeeCollectionPlanAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_collection_plan.create"

    @transaction.atomic
    def post(self, request):

        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required.",
            )

        try:
            # ---------------------------------------------------------
            # 1. Validate Fee Template
            # ---------------------------------------------------------

            fee_template_id = request.data.get(
                "fee_template_id",
            )

            if not fee_template_id:
                return CustomResponse.errorResponse(
                    description="Fee template is required.",
                )

            fee_template = (
                FeeTemplate.objects
                .filter(
                    id=fee_template_id,
                    school=school,
                    is_active=True,
                )
                .first()
            )

            if not fee_template:
                return CustomResponse.errorResponse(
                    description="Fee template not found.",
                )

            # ---------------------------------------------------------
            # 2. Check Collection Plan
            # ---------------------------------------------------------

            if FeeCollectionPlan.objects.filter(
                fee_template=fee_template,
            ).exists():

                return CustomResponse.errorResponse(
                    description=(
                        "Collection plan already exists "
                        "for this fee template."
                    ),
                )

            # ---------------------------------------------------------
            # 3. Validate Name
            # ---------------------------------------------------------

            name = str(
                request.data.get(
                    "name",
                    "",
                )
            ).strip()

            if not name:
                return CustomResponse.errorResponse(
                    description="Collection plan name is required.",
                )

            # ---------------------------------------------------------
            # 4. Validate Plan Type
            # ---------------------------------------------------------

            plan_type = request.data.get(
                "plan_type",
            )

            if plan_type not in FeeCollectionPlan.PlanType.values:

                return CustomResponse.errorResponse(
                    description="Invalid plan type.",
                )

            # ---------------------------------------------------------
            # 5. Validate Active Status
            # ---------------------------------------------------------

            is_active = request.data.get(
                "is_active",
                True,
            )

            if not isinstance(
                is_active,
                bool,
            ):

                return CustomResponse.errorResponse(
                    description="Invalid active status.",
                )

            # ---------------------------------------------------------
            # 6. Validate Installments
            # ---------------------------------------------------------

            installments_data = request.data.get(
                "installments",
                [],
            )

            if not isinstance(
                installments_data,
                list,
            ) or not installments_data:

                return CustomResponse.errorResponse(
                    description="At least one installment is required.",
                )

            total_allocation = Decimal("0")

            installment_names = set()
            installment_orders = set()

            validated_installments = []

            for index, installment_data in enumerate(
                installments_data,
                start=1,
            ):

                if not isinstance(
                    installment_data,
                    dict,
                ):

                    return CustomResponse.errorResponse(
                        description=(
                            f"Invalid installment data at position {index}."
                        ),
                    )

                # -----------------------------------------------------
                # Installment name
                # -----------------------------------------------------

                installment_name = str(
                    installment_data.get(
                        "name",
                        "",
                    )
                ).strip()

                if not installment_name:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "name is required."
                        ),
                    )

                name_key = installment_name.lower()

                if name_key in installment_names:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "duplicate installment name."
                        ),
                    )

                installment_names.add(
                    name_key,
                )

                # -----------------------------------------------------
                # Due date
                # -----------------------------------------------------

                due_date = installment_data.get(
                    "due_date",
                )

                if not due_date:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "due date is required."
                        ),
                    )

                parsed_due_date = parse_date(
                    str(due_date),
                )

                if not parsed_due_date:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "invalid due date."
                        ),
                    )

                # -----------------------------------------------------
                # Order
                # -----------------------------------------------------

                order = installment_data.get(
                    "order",
                    index,
                )

                try:
                    order = int(order)
                except (TypeError, ValueError):

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "invalid order."
                        ),
                    )

                if order <= 0:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "order must be greater than 0."
                        ),
                    )

                if order in installment_orders:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "duplicate order."
                        ),
                    )

                installment_orders.add(
                    order,
                )

                # -----------------------------------------------------
                # Allocation percentage
                # -----------------------------------------------------

                allocation = installment_data.get(
                    "allocation_percentage",
                    0,
                )

                try:
                    allocation = Decimal(
                        str(allocation)
                    )
                except (InvalidOperation, ValueError):

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "invalid allocation percentage."
                        ),
                    )

                if allocation < 0 or allocation > 100:

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "allocation percentage must be "
                            "between 0 and 100."
                        ),
                    )

                total_allocation += allocation

                validated_installments.append(
                    {
                        "name": installment_name,
                        "due_date": parsed_due_date,
                        "order": order,
                        "allocation_percentage": allocation,
                    }
                )

            # ---------------------------------------------------------
            # 7. Allocation must be exactly 100%
            # ---------------------------------------------------------

            if total_allocation != Decimal("100"):

                return CustomResponse.errorResponse(
                    description=(
                        "Total installment allocation must be 100%. "
                        f"Current allocation is {total_allocation}%."
                    ),
                )

            # ---------------------------------------------------------
            # 8. Get Fee Template Items
            # ---------------------------------------------------------

            template_items = list(
                fee_template.items.all()
            )

            if not template_items:

                return CustomResponse.errorResponse(
                    description=(
                        "Fee template does not contain "
                        "any fee items."
                    ),
                )

            # ---------------------------------------------------------
            # 9. Create Collection Plan
            # ---------------------------------------------------------

            collection_plan = FeeCollectionPlan.objects.create(
                fee_template=fee_template,
                name=name,
                plan_type=plan_type,
                is_active=is_active,
            )

            # ---------------------------------------------------------
            # 10. Create Installments
            #     + Installment Items
            # ---------------------------------------------------------

            created_installments = []

            for installment_data in validated_installments:

                installment = FeeInstallment.objects.create(
                    collection_plan=collection_plan,
                    name=installment_data["name"],
                    due_date=installment_data["due_date"],
                    order=installment_data["order"],
                    allocation_percentage=(
                        installment_data[
                            "allocation_percentage"
                        ]
                    ),
                )

                created_installments.append(
                    installment
                )

                # -----------------------------------------------------
                # Create FeeInstallmentItems
                # -----------------------------------------------------

                for template_item in template_items:

                    amount = (
                        template_item.amount
                        * installment_data[
                            "allocation_percentage"
                        ]
                        / Decimal("100")
                    )

                    FeeInstallmentItem.objects.create(
                        installment=installment,
                        fee_template_item=template_item,
                        amount=amount,
                    )

            # ---------------------------------------------------------
            # 11. Response
            # ---------------------------------------------------------

            return CustomResponse.successResponse(
                description=(
                    "Fee collection plan created successfully."
                ),
                data={
                    "id": str(collection_plan.id),
                    "name": collection_plan.name,
                    "plan_type": collection_plan.plan_type,
                    "is_active": collection_plan.is_active,
                    "installments": [
                        {
                            "id": str(installment.id),
                            "name": installment.name,
                            "due_date": installment.due_date,
                            "order": installment.order,
                            "allocation_percentage": (
                                installment.allocation_percentage
                            ),
                        }
                        for installment in created_installments
                    ],
                },
            )

        except Exception as e:

            application_logger.exception(
                "fee_collection_plan_create_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to create fee collection plan."
                ),
            )


class FeeCollectionPlanListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_collection_plan.view"

    def get(self, request):

        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required.",
            )

        queryset = FeeCollectionPlan.objects.select_related(
            "fee_template",
            "fee_template__grade",
            "fee_template__academic_year",
        ).prefetch_related(
            "installments__items__fee_template_item__fee_type",
        ).filter(
            fee_template__school=school,
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
                fee_template__academic_year_id=academic_year_id,
            )

        if grade_id:
            queryset = queryset.filter(
                fee_template__grade_id=grade_id,
            )

        if search:
            queryset = queryset.filter(
                name__icontains=search,
            )

        total = queryset.count()

        paginator = CustomPageNumberPagination()

        page = paginator.paginate_queryset(
            queryset.order_by(
                "fee_template__grade__display_order",
                "name",
            ),
            request,
        )

        data = []

        for obj in page:

            installments = []

            for installment in obj.installments.all():

                items = []

                for item in installment.items.all():

                    items.append({
                        "id": str(item.id),

                        "fee_template_item_id": str(
                            item.fee_template_item.id
                        ),

                        "fee_type": {
                            "id": str(
                                item.fee_template_item.fee_type.id
                            ),
                            "name": (
                                item.fee_template_item.fee_type.name
                            ),
                        },

                        "amount": item.amount,
                    })

                installments.append({
                    "id": str(installment.id),

                    "name": installment.name,

                    "due_date": installment.due_date,

                    "order": installment.order,

                    "allocation_percentage": (
                        installment.allocation_percentage
                    ),

                    "items": items,
                })

            data.append({

                "id": str(obj.id),

                "name": obj.name,

                "plan_type": obj.plan_type,

                "is_active": obj.is_active,

                "fee_template": {
                    "id": str(obj.fee_template.id),
                    "name": obj.fee_template.name,
                },

                "grade": {
                    "id": str(obj.fee_template.grade.id),
                    "name": obj.fee_template.grade.name,
                },

                "academic_year": {
                    "id": str(
                        obj.fee_template.academic_year.id
                    ),
                    "name": (
                        obj.fee_template.academic_year.name
                    ),
                },

                "installments": installments,
            })

        return CustomResponse.successResponse(
            data=data,
            total=total,
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

    @transaction.atomic
    def put(
        self,
        request,
        collection_plan_id,
    ):

        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required.",
            )

        try:

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

            # ---------------------------------
            # Basic fields
            # ---------------------------------

            name = str(
                request.data.get(
                    "name",
                    collection_plan.name,
                )
            ).strip()

            if not name:
                return CustomResponse.errorResponse(
                    description="Collection plan name is required.",
                )

            plan_type = request.data.get(
                "plan_type",
                collection_plan.plan_type,
            )

            if plan_type not in FeeCollectionPlan.PlanType.values:
                return CustomResponse.errorResponse(
                    description="Invalid plan type.",
                )

            is_active = request.data.get(
                "is_active",
                collection_plan.is_active,
            )

            if not isinstance(is_active, bool):
                return CustomResponse.errorResponse(
                    description="Invalid active status.",
                )

            # ---------------------------------
            # Installments
            # ---------------------------------

            installments_data = request.data.get(
                "installments",
            )

            if installments_data is None:
                return CustomResponse.errorResponse(
                    description="Installments are required.",
                )

            if (
                not isinstance(installments_data, list)
                or not installments_data
            ):
                return CustomResponse.errorResponse(
                    description="At least one installment is required.",
                )

            total_allocation = Decimal("0")

            installment_names = set()
            installment_orders = set()

            validated_installments = []

            for index, installment_data in enumerate(
                installments_data,
                start=1,
            ):

                if not isinstance(
                    installment_data,
                    dict,
                ):
                    return CustomResponse.errorResponse(
                        description=(
                            f"Invalid installment data at position {index}."
                        ),
                    )

                # -------------------------
                # Name
                # -------------------------

                installment_name = str(
                    installment_data.get(
                        "name",
                        "",
                    )
                ).strip()

                if not installment_name:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "name is required."
                        ),
                    )

                name_key = installment_name.lower()

                if name_key in installment_names:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "duplicate installment name."
                        ),
                    )

                installment_names.add(name_key)

                # -------------------------
                # Due date
                # -------------------------

                due_date = installment_data.get(
                    "due_date",
                )

                if not due_date:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "due date is required."
                        ),
                    )

                parsed_due_date = parse_date(
                    str(due_date),
                )

                if not parsed_due_date:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "invalid due date."
                        ),
                    )

                # -------------------------
                # Order
                # -------------------------

                order = installment_data.get(
                    "order",
                    index,
                )

                try:
                    order = int(order)
                except (TypeError, ValueError):

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "invalid order."
                        ),
                    )

                if order <= 0:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "order must be greater than 0."
                        ),
                    )

                if order in installment_orders:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "duplicate order."
                        ),
                    )

                installment_orders.add(order)

                # -------------------------
                # Allocation
                # -------------------------

                allocation = installment_data.get(
                    "allocation_percentage",
                    0,
                )

                try:
                    allocation = Decimal(
                        str(allocation)
                    )
                except (
                    InvalidOperation,
                    ValueError,
                ):

                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "invalid allocation percentage."
                        ),
                    )

                if allocation < 0 or allocation > 100:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Installment {index}: "
                            "allocation percentage "
                            "must be between 0 and 100."
                        ),
                    )

                total_allocation += allocation

                validated_installments.append(
                    {
                        "name": installment_name,
                        "due_date": parsed_due_date,
                        "order": order,
                        "allocation_percentage": allocation,
                    }
                )

            # ---------------------------------
            # Allocation validation
            # ---------------------------------

            if total_allocation != Decimal("100"):
                return CustomResponse.errorResponse(
                    description=(
                        "Total installment allocation "
                        "must be 100%. "
                        f"Current allocation is "
                        f"{total_allocation}%."
                    ),
                )

            # ---------------------------------
            # Fee template items
            # ---------------------------------

            template_items = list(
                collection_plan
                .fee_template
                .items
                .all()
            )

            if not template_items:
                return CustomResponse.errorResponse(
                    description=(
                        "Fee template does not contain "
                        "any fee items."
                    ),
                )

            # ---------------------------------
            # Update collection plan
            # ---------------------------------

            collection_plan.name = name
            collection_plan.plan_type = plan_type
            collection_plan.is_active = is_active

            collection_plan.save(
                update_fields=[
                    "name",
                    "plan_type",
                    "is_active",
                ]
            )

            # ---------------------------------
            # Replace installments
            # ---------------------------------

            FeeInstallment.objects.filter(
                collection_plan=collection_plan,
            ).delete()

            created_installments = []

            for installment_data in validated_installments:

                installment = FeeInstallment.objects.create(
                    collection_plan=collection_plan,
                    name=installment_data["name"],
                    due_date=installment_data["due_date"],
                    order=installment_data["order"],
                    allocation_percentage=(
                        installment_data[
                            "allocation_percentage"
                        ]
                    ),
                )

                created_installments.append(
                    installment
                )

                # -------------------------
                # Create installment items
                # -------------------------

                for template_item in template_items:

                    amount = (
                        template_item.amount
                        * installment_data[
                            "allocation_percentage"
                        ]
                        / Decimal("100")
                    )

                    FeeInstallmentItem.objects.create(
                        installment=installment,
                        fee_template_item=template_item,
                        amount=amount,
                    )

            return CustomResponse.successResponse(
                description=(
                    "Collection plan updated successfully."
                ),
                data={
                    "id": str(collection_plan.id),
                    "name": collection_plan.name,
                    "plan_type": collection_plan.plan_type,
                    "is_active": collection_plan.is_active,
                    "installments": [
                        {
                            "id": str(installment.id),
                            "name": installment.name,
                            "due_date": installment.due_date,
                            "order": installment.order,
                            "allocation_percentage": (
                                installment.allocation_percentage
                            ),
                        }
                        for installment in created_installments
                    ],
                },
            )

        except Exception as e:

            application_logger.exception(
                "fee_collection_plan_update_failed",
                error=str(e),
                collection_plan_id=str(
                    collection_plan_id
                ),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Failed to update collection plan."
                ),
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
        try:
            school = request.school

            if not school:
                return CustomResponse.errorResponse(
                    description="School is required."
                )

            queryset = (
                StudentFee.objects
                .select_related(
                    # Student
                    "student",

                    # Installment hierarchy
                    "installment_item",
                    "installment_item__installment",
                    "installment_item__installment__collection_plan",
                    "installment_item__installment__collection_plan__fee_template",

                    # Template item / fee type
                    "installment_item__fee_template_item",
                    "installment_item__fee_template_item__fee_type",
                )
                .prefetch_related(
                    "payments",
                )
                .filter(
                    student__school=school,
                )
                .order_by(
                    "due_date",
                    "student__name",
                )
            )

            student_id = request.query_params.get(
                "student_id"
            )

            status = request.query_params.get(
                "status"
            )

            grade_id = request.query_params.get(
                "grade_id"
            )

            fee_template_id = request.query_params.get(
                "fee_template_id"
            )

            fee_type_id = request.query_params.get(
                "fee_type_id"
            )

            installment_id = request.query_params.get(
                "installment_id"
            )

            search = request.query_params.get(
                "search"
            )

            # -----------------------------------------
            # Filters
            # -----------------------------------------

            if student_id:
                queryset = queryset.filter(
                    student_id=student_id
                )

            if status:
                queryset = queryset.filter(
                    status=status
                )

            if grade_id:
                queryset = queryset.filter(
                    student__grade_id=grade_id
                )

            if fee_template_id:
                queryset = queryset.filter(
                    installment_item__installment__collection_plan__fee_template_id=fee_template_id
                )

            if fee_type_id:
                queryset = queryset.filter(
                    installment_item__fee_template_item__fee_type_id=fee_type_id
                )

            if installment_id:
                queryset = queryset.filter(
                    installment_item__installment_id=installment_id
                )

            if search:
                search = search.strip()

                queryset = queryset.filter(
                    Q(student__name__icontains=search)
                    |
                    Q(
                        student__admission_number__icontains=search
                    )
                    |
                    Q(
                        installment_item__fee_template_item__fee_type__name__icontains=search
                    )
                    |
                    Q(
                        installment_item__installment__name__icontains=search
                    )
                    |
                    Q(
                        installment_item__installment__collection_plan__fee_template__name__icontains=search
                    )
                )

            # -----------------------------------------
            # Pagination
            # -----------------------------------------

            total_count = queryset.count()

            paginator = self.pagination_class()

            page = paginator.paginate_queryset(
                queryset,
                request,
            )

            # -----------------------------------------
            # Get assignments for current page
            # Avoid N+1 query from concession_amount property
            # -----------------------------------------

            student_ids = {
                fee.student_id
                for fee in page
            }

            fee_template_ids = {
                fee.installment_item
                .installment
                .collection_plan
                .fee_template_id
                for fee in page
            }

            assignments = (
                StudentFeeAssignment.objects
                .filter(
                    student_id__in=student_ids,
                    fee_template_id__in=fee_template_ids,
                )
                .select_related(
                    "concession",
                    "assigned_by",
                    "fee_template",
                )
            )

            assignment_map = {
                (
                    assignment.student_id,
                    assignment.fee_template_id,
                ): assignment
                for assignment in assignments
            }

            # -----------------------------------------
            # Get late fee rules for current page
            # -----------------------------------------

            collection_plan_ids = {
                fee.installment_item
                .installment
                .collection_plan_id
                for fee in page
            }

            late_fee_rules = (
                LateFeeRule.objects
                .filter(
                    collection_plan_id__in=collection_plan_ids,
                )
                .order_by(
                    "collection_plan_id",
                    "from_day",
                )
            )

            late_fee_rule_map = {}

            for rule in late_fee_rules:
                late_fee_rule_map.setdefault(
                    rule.collection_plan_id,
                    []
                ).append(rule)

            # -----------------------------------------
            # Response Data
            # -----------------------------------------

            data = []

            for fee in page:

                installment_item = (
                    fee.installment_item
                )

                installment = (
                    installment_item.installment
                )

                collection_plan = (
                    installment.collection_plan
                )

                fee_template = (
                    collection_plan.fee_template
                )

                template_item = (
                    installment_item.fee_template_item
                )

                fee_type = (
                    template_item.fee_type
                )

                assignment = assignment_map.get(
                    (
                        fee.student_id,
                        fee_template.id,
                    )
                )

                # -------------------------------------
                # Concession
                # -------------------------------------

                concession_data = None
                concession_amount = 0

                if assignment and assignment.concession:

                    concession = assignment.concession

                    concession_data = {
                        "id": str(concession.id),
                        "name": concession.name,
                        "type": concession.concession_type,
                        "value": concession.value,
                    }

                    if (
                        concession.concession_type
                        == FeeConcession.Type.PERCENTAGE
                    ):
                        concession_amount = (
                            fee.amount * concession.value
                        ) / 100

                    else:
                        concession_amount = (
                            concession.value
                        )

                # -------------------------------------
                # Late Fee Rules
                # -------------------------------------

                late_fee_rules_data = [
                    {
                        "id": str(rule.id),
                        "from_day": rule.from_day,
                        "to_day": rule.to_day,
                        "rule_type": rule.rule_type,
                        "value": rule.value,
                    }
                    for rule in late_fee_rule_map.get(
                        collection_plan.id,
                        []
                    )
                ]

                # -------------------------------------
                # Payments
                # -------------------------------------

                payments_data = []

                for payment in fee.payments.all():

                    payments_data.append(
                        {
                            "id": str(payment.id),
                            "receipt_number": (
                                payment.receipt_number
                            ),
                            "amount": payment.amount,
                            "payment_mode": (
                                payment.payment_mode
                            ),
                            "payment_date": (
                                payment.payment_date
                            ),
                            "transaction_id": (
                                payment.transaction_id
                            ),
                            "gateway_name": (
                                payment.gateway_name
                            ),
                            "remarks": payment.remarks,
                            "collected_by": (
                                str(payment.collected_by_id)
                                if payment.collected_by_id
                                else None
                            ),
                            "is_cancelled": (
                                payment.is_cancelled
                            ),
                        }
                    )

                # -------------------------------------
                # Balance
                # -------------------------------------

                balance = (
                    fee.amount
                    - concession_amount
                    + fee.late_fee
                    - fee.paid_amount
                )

                # -------------------------------------
                # Assignment Details
                # -------------------------------------

                assignment_data = None

                if assignment:

                    assignment_data = {
                        "id": str(assignment.id),
                        "assigned_date": (
                            assignment.assigned_date
                        ),
                        "assigned_by": (
                            {
                                "id": str(
                                    assignment.assigned_by_id
                                ),
                                "name": (
                                    assignment.assigned_by.first_name
                                    if assignment.assigned_by
                                    else None
                                ),
                            }
                            if assignment.assigned_by_id
                            else None
                        ),
                    }

                # -------------------------------------
                # Final Response
                # -------------------------------------

                data.append(
                    {
                        # =============================
                        # Student
                        # =============================

                        "student": {
                            "id": str(fee.student.id),
                            "name": fee.student.name,
                            "admission_number": (
                                fee.student.admission_number
                            ),
                        },

                        # =============================
                        # Assignment
                        # =============================

                        "assignment": assignment_data,

                        # =============================
                        # Fee Template
                        # =============================

                        "fee_template": {
                            "id": str(fee_template.id),
                            "name": fee_template.name,
                            "academic_year_id": str(
                                fee_template.academic_year_id
                            ),
                            "grade_id": str(
                                fee_template.grade_id
                            ),
                            "is_active": (
                                fee_template.is_active
                            ),
                        },

                        # =============================
                        # Fee Template Item
                        # =============================

                        "fee_template_item": {
                            "id": str(template_item.id),
                            "amount": template_item.amount,
                            "is_mandatory": (
                                template_item.is_mandatory
                            ),
                        },

                        # =============================
                        # Fee Type
                        # =============================

                        "fee_type": {
                            "id": str(fee_type.id),
                            "name": fee_type.name,
                            "is_optional": (
                                fee_type.is_optional
                            ),
                            "description": (
                                fee_type.description
                            ),
                        },

                        # =============================
                        # Collection Plan
                        # =============================

                        "collection_plan": {
                            "id": str(collection_plan.id),
                            "plan_type": (
                                collection_plan.plan_type
                            ),
                        },

                        # =============================
                        # Installment
                        # =============================

                        "installment": {
                            "id": str(installment.id),
                            "name": installment.name,
                            "due_date": installment.due_date,
                            "order": installment.order,
                        },

                        # =============================
                        # Installment Item
                        # =============================

                        "installment_item": {
                            "id": str(installment_item.id),
                            "amount": installment_item.amount,
                        },

                        # =============================
                        # Student Fee
                        # =============================

                        "student_fee": {
                            "id": str(fee.id),
                            "due_date": fee.due_date,
                            "amount": fee.amount,
                            "late_fee": fee.late_fee,
                            "paid_amount": fee.paid_amount,
                            "concession_amount": (
                                concession_amount
                            ),
                            "balance": balance,
                            "status": fee.status,
                        },

                        # =============================
                        # Concession
                        # =============================

                        "concession": concession_data,

                        # =============================
                        # Late Fee Rules
                        # =============================

                        "late_fee_rules": (
                            late_fee_rules_data
                        ),

                        # =============================
                        # Payments
                        # =============================

                        "payments": payments_data,
                    }
                )

            return CustomResponse.successResponse(
                data=data,
                total=total_count,
                description=(
                    "Student fees fetched successfully."
                ),
            )

        except Exception as e:

            application_logger.exception(
                "student_fee_list_failed",
                error=str(e),
            )

            return CustomResponse.errorResponse(
                description="Internal server error."
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

class PendingStudentFeeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        student = Student.objects.filter(
            id=request.query_params.get("student_id"),
        ).first()

        if student is None:

            return CustomResponse.errorResponse(
                description="Student not found.",
            )

        fees = StudentFee.objects.select_related(
            "installment_item",
            "installment_item__fee_template_item",
            "installment_item__fee_template_item__fee_type",
            "installment_item__installment",
        ).filter(
            student=student,
        ).exclude(
            status=StudentFee.Status.PAID,
        ).order_by(
            "due_date",
        )

        total_amount = 0

        data = []

        for fee in fees:

            payable = fee.payable_amount

            total_amount += payable

            data.append({

                "student_fee_id": str(fee.id),

                "fee_type": fee.installment_item.fee_template_item.fee_type.name,

                "installment": fee.installment_item.installment.name,

                "amount": fee.amount,

                "concession": fee.concession_amount,

                "late_fee": fee.late_fee,

                "paid_amount": fee.paid_amount,

                "payable_amount": payable,

                "due_date": fee.due_date,

                "status": fee.status,

            })

        return CustomResponse.successResponse(

            data={

                "student": {

                    "id": str(student.id),

                    "name": student.name,

                    "admission_number": student.admission_number,

                },

                "fees": data,

                "total_payable_amount": total_amount,

            }

        )



class FeePlanCreateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_plan.create"

    def post(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            academic_year_id = request.data.get("academic_year_id")
            grade_id = request.data.get("grade_id")
            name = request.data.get("name")
            total_amount = request.data.get("total_amount")
            plan_type = request.data.get("plan_type", FeePlan.PlanType.ANNUAL)
            number_of_terms = request.data.get("number_of_terms", 1)

            if not academic_year_id:
                return CustomResponse.errorResponse(
                    description="Academic year is required."
                )

            if not grade_id:
                return CustomResponse.errorResponse(
                    description="Grade is required."
                )

            if not name:
                return CustomResponse.errorResponse(
                    description="Plan name is required."
                )

            if total_amount is None:
                return CustomResponse.errorResponse(
                    description="Total amount is required."
                )

            try:
                total_amount = Decimal(str(total_amount))
            except (InvalidOperation, ValueError):
                return CustomResponse.errorResponse(
                    description="Invalid total amount."
                )

            if total_amount <= 0:
                return CustomResponse.errorResponse(
                    description="Total amount must be greater than zero."
                )

            try:
                number_of_terms = int(number_of_terms)
            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    description="Invalid number of terms."
                )

            if number_of_terms <= 0:
                return CustomResponse.errorResponse(
                    description="Number of terms must be greater than zero."
                )

            if plan_type not in FeePlan.PlanType.values:
                return CustomResponse.errorResponse(
                    description="Invalid plan type."
                )

            academic_year = AcademicYear.objects.filter(
                id=academic_year_id,
                school=school,
            ).first()

            if not academic_year:
                return CustomResponse.errorResponse(
                    description="Academic year not found."
                )

            grade = Grade.objects.filter(
                id=grade_id,
                school=school,
                academic_year=academic_year,
            ).first()

            if not grade:
                return CustomResponse.errorResponse(
                    description="Grade not found."
                )

            if FeePlan.objects.filter(
                school=school,
                academic_year=academic_year,
                grade=grade,
                name=name,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Fee plan already exists."
                )

            fee_plan = FeePlan.objects.create(
                school=school,
                academic_year=academic_year,
                grade=grade,
                name=name,
                total_amount=total_amount,
                plan_type=plan_type,
                number_of_terms=number_of_terms,
                is_active=True,
            )

            application_logger.info(
                "fee_plan_created",
                fee_plan_id=str(fee_plan.id),
                school_id=str(school.id),
                academic_year_id=str(academic_year.id),
                grade_id=str(grade.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(fee_plan.id),
                    "name": fee_plan.name,
                    "academic_year": {
                        "id": str(academic_year.id),
                        "name": academic_year.name,
                    },
                    "grade": {
                        "id": str(grade.id),
                        "name": grade.name,
                    },
                    "total_amount": fee_plan.total_amount,
                    "plan_type": fee_plan.plan_type,
                    "number_of_terms": fee_plan.number_of_terms,
                    "is_active": fee_plan.is_active,
                },
                description="Fee plan created successfully.",
            )

        except IntegrityError:
            return CustomResponse.errorResponse(
                description="Fee plan already exists."
            )

        except Exception as e:
            application_logger.exception(
                "fee_plan_create_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to create fee plan."
            )


class FeePlanListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_plan.view"

    def get(self, request):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            queryset = (
                FeePlan.objects
                .select_related(
                    "academic_year",
                    "grade",
                )
                .prefetch_related(
                    "installments"
                )
                .filter(
                    school=school,
                )
                .order_by("-id")
            )

            academic_year_id = request.query_params.get(
                "academic_year_id"
            )
            grade_id = request.query_params.get("grade_id")
            plan_type = request.query_params.get("plan_type")
            is_active = request.query_params.get("is_active")

            if academic_year_id:
                queryset = queryset.filter(
                    academic_year_id=academic_year_id
                )

            if grade_id:
                queryset = queryset.filter(
                    grade_id=grade_id
                )

            if plan_type:
                queryset = queryset.filter(
                    plan_type=plan_type
                )

            if is_active is not None:
                queryset = queryset.filter(
                    is_active=is_active.lower() == "true"
                )

            total_count = queryset.count()

            data = []

            for plan in queryset:
                installments = plan.installments.all()

                scheduled_amount = sum(
                    (
                        installment.amount
                        for installment in installments
                    ),
                    Decimal("0"),
                )

                remaining_schedule_amount = (
                    plan.total_amount - scheduled_amount
                )

                data.append({
                    "id": str(plan.id),

                    "name": plan.name,

                    "academic_year": {
                        "id": str(
                            plan.academic_year.id
                        ),
                        "name": (
                            plan.academic_year.name
                        ),
                    },

                    "grade": {
                        "id": str(
                            plan.grade.id
                        ),
                        "name": (
                            plan.grade.name
                        ),
                    },

                    "total_amount": plan.total_amount,

                    "plan_type": plan.plan_type,

                    "number_of_terms": (
                        plan.number_of_terms
                    ),

                    "is_active": plan.is_active,

                    "installment_summary": {
                        "scheduled_amount": scheduled_amount,
                        "remaining_amount": (
                            remaining_schedule_amount
                        ),
                    },

                    "installments": [
                        {
                            "id": str(
                                installment.id
                            ),
                            "name": (
                                installment.name
                            ),
                            "installment_number": (
                                installment.installment_number
                            ),
                            "amount": (
                                installment.amount
                            ),
                            "due_date": (
                                installment.due_date
                            ),
                        }
                        for installment in installments
                    ],
                })

            return CustomResponse.successResponse(
                data=data,
                total=total_count,
                description="Fee plans fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "fee_plan_list_failed",
                error=str(e),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch fee plans."
            )


class FeePlanUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_plan.update"

    def put(self, request, fee_plan_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            fee_plan = FeePlan.objects.filter(
                id=fee_plan_id,
                school=school,
            ).first()

            if not fee_plan:
                return CustomResponse.errorResponse(
                    description="Fee plan not found."
                )

            name = request.data.get("name")
            total_amount = request.data.get("total_amount")
            plan_type = request.data.get("plan_type")
            number_of_terms = request.data.get("number_of_terms")

            if name is not None:
                if not name.strip():
                    return CustomResponse.errorResponse(
                        description="Plan name cannot be empty."
                    )
                fee_plan.name = name.strip()

            if total_amount is not None:
                try:
                    total_amount = Decimal(
                        str(total_amount)
                    )
                except (InvalidOperation, ValueError):
                    return CustomResponse.errorResponse(
                        description="Invalid total amount."
                    )

                if total_amount <= 0:
                    return CustomResponse.errorResponse(
                        description="Total amount must be greater than zero."
                    )

                fee_plan.total_amount = total_amount

            if plan_type is not None:
                if plan_type not in FeePlan.PlanType.values:
                    return CustomResponse.errorResponse(
                        description="Invalid plan type."
                    )

                fee_plan.plan_type = plan_type

            if number_of_terms is not None:
                try:
                    number_of_terms = int(number_of_terms)
                except (TypeError, ValueError):
                    return CustomResponse.errorResponse(
                        description="Invalid number of terms."
                    )

                if number_of_terms <= 0:
                    return CustomResponse.errorResponse(
                        description=(
                            "Number of terms must be greater than zero."
                        )
                    )

                fee_plan.number_of_terms = number_of_terms

            fee_plan.save()

            application_logger.info(
                "fee_plan_updated",
                fee_plan_id=str(fee_plan.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(fee_plan.id),
                    "name": fee_plan.name,
                    "total_amount": fee_plan.total_amount,
                    "plan_type": fee_plan.plan_type,
                    "number_of_terms": fee_plan.number_of_terms,
                    "is_active": fee_plan.is_active,
                },
                description="Fee plan updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "fee_plan_update_failed",
                error=str(e),
                fee_plan_id=str(fee_plan_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update fee plan."
            )


class FeePlanInstallmentCreateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_plan_installment.create"

    def post(self, request, fee_plan_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            name = request.data.get("name")
            installment_number = request.data.get(
                "installment_number"
            )
            amount = request.data.get("amount")
            due_date = request.data.get("due_date")

            if not name:
                return CustomResponse.errorResponse(
                    description="Installment name is required."
                )

            if installment_number is None:
                return CustomResponse.errorResponse(
                    description="Installment number is required."
                )

            if amount is None:
                return CustomResponse.errorResponse(
                    description="Installment amount is required."
                )

            if not due_date:
                return CustomResponse.errorResponse(
                    description="Due date is required."
                )

            try:
                installment_number = int(
                    installment_number
                )
            except (TypeError, ValueError):
                return CustomResponse.errorResponse(
                    description="Invalid installment number."
                )

            if installment_number <= 0:
                return CustomResponse.errorResponse(
                    description=(
                        "Installment number must be greater than zero."
                    )
                )

            try:
                amount = Decimal(str(amount))
            except (InvalidOperation, ValueError):
                return CustomResponse.errorResponse(
                    description="Invalid installment amount."
                )

            if amount <= 0:
                return CustomResponse.errorResponse(
                    description=(
                        "Installment amount must be greater than zero."
                    )
                )

            fee_plan = FeePlan.objects.filter(
                id=fee_plan_id,
                school=school,
            ).first()

            if not fee_plan:
                return CustomResponse.errorResponse(
                    description="Fee plan not found."
                )

            if not fee_plan.is_active:
                return CustomResponse.errorResponse(
                    description="Cannot modify an inactive fee plan."
                )

            if FeePlanInstallment.objects.filter(
                fee_plan=fee_plan,
                installment_number=installment_number,
            ).exists():
                return CustomResponse.errorResponse(
                    description="Installment number already exists."
                )

            existing_total = (
                FeePlanInstallment.objects
                .filter(fee_plan=fee_plan)
                .aggregate(total=Sum("amount"))
                ["total"]
                or Decimal("0")
            )

            if existing_total + amount > fee_plan.total_amount:
                return CustomResponse.errorResponse(
                    description=(
                        "Installment total cannot exceed "
                        "the fee plan total amount."
                    )
                )

            installment = FeePlanInstallment.objects.create(
                school=school,
                fee_plan=fee_plan,
                name=name,
                installment_number=installment_number,
                amount=amount,
                due_date=due_date,
            )

            application_logger.info(
                "fee_plan_installment_created",
                installment_id=str(installment.id),
                fee_plan_id=str(fee_plan.id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(installment.id),
                    "fee_plan_id": str(fee_plan.id),
                    "name": installment.name,
                    "installment_number": (
                        installment.installment_number
                    ),
                    "amount": installment.amount,
                    "due_date": installment.due_date,
                },
                description="Fee plan installment created successfully.",
            )

        except IntegrityError:
            return CustomResponse.errorResponse(
                description="Installment number already exists."
            )

        except Exception as e:
            application_logger.exception(
                "fee_plan_installment_create_failed",
                error=str(e),
                fee_plan_id=str(fee_plan_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to create fee plan installment."
            )


class FeePlanInstallmentListAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_plan_installment.view"

    def get(self, request, fee_plan_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            fee_plan = FeePlan.objects.filter(
                id=fee_plan_id,
                school=school,
            ).first()

            if not fee_plan:
                return CustomResponse.errorResponse(
                    description="Fee plan not found."
                )

            queryset = (
                FeePlanInstallment.objects
                .filter(
                    fee_plan=fee_plan,
                    school=school,
                )
                .order_by("installment_number")
            )

            total_installment_amount = (
                queryset.aggregate(
                    total=Sum("amount")
                )["total"]
                or Decimal("0")
            )

            data = [
                {
                    "id": str(installment.id),
                    "name": installment.name,
                    "installment_number": (
                        installment.installment_number
                    ),
                    "amount": installment.amount,
                    "due_date": installment.due_date,
                }
                for installment in queryset
            ]

            return CustomResponse.successResponse(
                data={
                    "fee_plan": {
                        "id": str(fee_plan.id),
                        "name": fee_plan.name,
                        "total_amount": fee_plan.total_amount,
                    },
                    "total_installment_amount": (
                        total_installment_amount
                    ),
                    "remaining_amount": (
                        fee_plan.total_amount
                        - total_installment_amount
                    ),
                    "installments": data,
                },
                total=queryset.count(),
                description="Fee plan installments fetched successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "fee_plan_installment_list_failed",
                error=str(e),
                fee_plan_id=str(fee_plan_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to fetch fee plan installments."
            )


class FeePlanInstallmentUpdateAPIView(APIView):
    permission_classes = [
        IsAuthenticated,
        HasPermission,
    ]

    required_permission = "fee_plan_installment.update"

    def put(self, request, fee_plan_id, installment_id):
        school = request.school

        if not school:
            return CustomResponse.errorResponse(
                description="School is required."
            )

        try:
            installment = (
                FeePlanInstallment.objects
                .filter(
                    id=installment_id,
                    fee_plan_id=fee_plan_id,
                    school=school,
                )
                .select_related("fee_plan")
                .first()
            )

            if not installment:
                return CustomResponse.errorResponse(
                    description="Fee plan installment not found."
                )

            name = request.data.get("name")
            amount = request.data.get("amount")
            due_date = request.data.get("due_date")
            installment_number = request.data.get(
                "installment_number"
            )

            if name is not None:
                if not name.strip():
                    return CustomResponse.errorResponse(
                        description="Installment name cannot be empty."
                    )

                installment.name = name.strip()

            if installment_number is not None:
                try:
                    installment_number = int(
                        installment_number
                    )
                except (TypeError, ValueError):
                    return CustomResponse.errorResponse(
                        description="Invalid installment number."
                    )

                if installment_number <= 0:
                    return CustomResponse.errorResponse(
                        description=(
                            "Installment number must be greater than zero."
                        )
                    )

                duplicate = (
                    FeePlanInstallment.objects
                    .filter(
                        fee_plan_id=fee_plan_id,
                        installment_number=installment_number,
                    )
                    .exclude(id=installment.id)
                    .exists()
                )

                if duplicate:
                    return CustomResponse.errorResponse(
                        description="Installment number already exists."
                    )

                installment.installment_number = (
                    installment_number
                )

            if amount is not None:
                try:
                    amount = Decimal(str(amount))
                except (InvalidOperation, ValueError):
                    return CustomResponse.errorResponse(
                        description="Invalid installment amount."
                    )

                if amount <= 0:
                    return CustomResponse.errorResponse(
                        description=(
                            "Installment amount must be greater than zero."
                        )
                    )

                existing_total = (
                    FeePlanInstallment.objects
                    .filter(fee_plan_id=fee_plan_id)
                    .exclude(id=installment.id)
                    .aggregate(total=Sum("amount"))
                    ["total"]
                    or Decimal("0")
                )

                if (
                    existing_total + amount
                    > installment.fee_plan.total_amount
                ):
                    return CustomResponse.errorResponse(
                        description=(
                            "Installment total cannot exceed "
                            "the fee plan total amount."
                        )
                    )

                installment.amount = amount

            if due_date is not None:
                installment.due_date = due_date

            installment.save()

            application_logger.info(
                "fee_plan_installment_updated",
                installment_id=str(installment.id),
                fee_plan_id=str(fee_plan_id),
                school_id=str(school.id),
            )

            return CustomResponse.successResponse(
                data={
                    "id": str(installment.id),
                    "name": installment.name,
                    "installment_number": (
                        installment.installment_number
                    ),
                    "amount": installment.amount,
                    "due_date": installment.due_date,
                },
                description="Fee plan installment updated successfully.",
            )

        except Exception as e:
            application_logger.exception(
                "fee_plan_installment_update_failed",
                error=str(e),
                installment_id=str(installment_id),
                school_id=str(school.id),
            )

            return CustomResponse.errorResponse(
                description="Failed to update fee plan installment."
            )
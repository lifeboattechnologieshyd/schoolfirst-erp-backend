import uuid
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db import transaction as db_transaction

from apps.fee.models import StudentFee, SchoolPaymentGateway, StudentFeeSummary
from apps.payment.models import PaymentTransaction, PaymentTransactionItem
from apps.payment.services.gateway import PaymentGatewayService
from apps.payment.services.phonepe import create_phonepe_payment, get_phonepe_client, phone_pe_initate
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from django.db import transaction

from shared.utils.logger import payment_logger



from decimal import Decimal
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Prefetch


class PendingStudentFeeAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        student_id = request.query_params.get("student_id")

        try:
            payment_logger.info(
                "pending_student_fee_started",
                user_id=str(request.user.id),
                student_id=student_id,
            )

            if not student_id:
                return CustomResponse.errorResponse(
                    description="Student ID is required."
                )

            student = Student.objects.filter(
                id=student_id,
            ).first()

            if student is None:
                payment_logger.warning(
                    "pending_student_fee_student_not_found",
                    student_id=student_id,
                )
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            # IMPORTANT:
            # Validate the authenticated parent's relationship
            # with this student before returning fee information.

            summary = StudentFeeSummary.objects.filter(
                school=student.school,
                student=student,
                academic_year=student.academic_year,
            ).first()

            # -------------------------------------------------
            # Overall fee summary
            # -------------------------------------------------

            if summary:
                fee_summary = {
                    "total_fee": str(summary.total_fee),
                    "total_concession": str(summary.total_concession),
                    "total_late_fee": str(summary.total_late_fee),
                    "total_paid": str(summary.total_paid),
                    "outstanding_amount": str(
                        summary.outstanding_amount
                    ),
                }
            else:
                fee_summary = {
                    "total_fee": "0.00",
                    "total_concession": "0.00",
                    "total_late_fee": "0.00",
                    "total_paid": "0.00",
                    "outstanding_amount": "0.00",
                }

            # -------------------------------------------------
            # Aggregate amounts by fee type
            # -------------------------------------------------

            fee_types = (
                StudentFee.objects
                .filter(
                    school=student.school,
                    student=student,
                    fee_template__academic_year=student.academic_year,
                )
                .exclude(
                    status=StudentFee.Status.WAIVED,
                )
                .values(
                    "fee_type_id",
                    "fee_type__name",
                )
                .annotate(
                    total_amount=Sum("total_amount"),
                    total_concession=Sum("concession_amount"),
                    total_late_fee=Sum("late_fee"),
                    total_paid=Sum("paid_amount"),
                )
                .order_by("fee_type__name")
            )

            fee_type_data = []

            for fee in fee_types:
                total_amount = (
                    fee["total_amount"] or Decimal("0.00")
                )
                concession_amount = (
                    fee["total_concession"] or Decimal("0.00")
                )
                late_fee = (
                    fee["total_late_fee"] or Decimal("0.00")
                )
                paid_amount = (
                    fee["total_paid"] or Decimal("0.00")
                )

                payable_amount = (
                    total_amount
                    - concession_amount
                    + late_fee
                )

                outstanding_amount = (
                    payable_amount - paid_amount
                )

                fee_type_data.append({
                    "fee_type_id": str(fee["fee_type_id"]),
                    "fee_type": fee["fee_type__name"],
                    "total_amount": str(total_amount),
                    "concession_amount": str(concession_amount),
                    "late_fee": str(late_fee),
                    "payable_amount": str(payable_amount),
                    "paid_amount": str(paid_amount),
                    "outstanding_amount": str(
                        max(outstanding_amount, Decimal("0.00"))
                    ),
                })

            payment_logger.info(
                "pending_student_fee_fetched",
                user_id=str(request.user.id),
                student_id=str(student.id),
                fee_type_count=len(fee_type_data),
            )

            return CustomResponse.successResponse(
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "admission_number": student.admission_number,
                        "academic_year": {
                            "id": str(student.academic_year_id),
                            "name": student.academic_year.name,
                        },
                    },
                    "fee_summary": fee_summary,
                    "fee_types": fee_type_data,
                }
            )

        except Exception:
            payment_logger.exception(
                "pending_student_fee_failed",
                user_id=str(request.user.id),
                student_id=student_id,
            )

            return CustomResponse.errorResponse(
                description="Internal server error."
            )

#
# class PendingStudentFeeAPIView(APIView):
#
#     permission_classes = [
#         IsAuthenticated,
#     ]
#
#     def get(self, request):
#
#         try:
#
#             payment_logger.info(
#                 "pending_student_fee_started",
#                 school_id=str(request.school.id),
#                 user_id=str(request.user.id),
#                 student_id=request.query_params.get("student_id"),
#             )
#
#             student = Student.objects.filter(
#                 id=request.query_params.get("student_id"),
#             ).first()
#
#             if student is None:
#
#                 payment_logger.warning(
#                     "pending_student_fee_student_not_found",
#                     school_id=str(request.school.id),
#                     student_id=request.query_params.get("student_id"),
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="Student not found.",
#                 )
#
#             fees = StudentFee.objects.select_related(
#                 "installment_item",
#                 "installment_item__fee_template_item",
#                 "installment_item__fee_template_item__fee_type",
#                 "installment_item__installment",
#                 "installment_item__installment__collection_plan",
#                 "installment_item__installment__collection_plan__fee_template",
#                 "installment_item__installment__collection_plan__fee_template__academic_year",
#             ).filter(
#                 student=student,
#             ).exclude(
#                 status=StudentFee.Status.PAID,
#             ).order_by(
#                 "due_date",
#             )
#
#             total_amount = 0
#             data = []
#
#             for fee in fees:
#
#                 payable = fee.payable_amount
#                 total_amount += payable
#                 academic_year = (
#                     fee.installment_item
#                     .installment
#                     .collection_plan
#                     .fee_template
#                     .academic_year
#                 )
#
#                 data.append({
#                     "student_fee_id": str(fee.id),
#                     "academic_year": {
#                         "id": str(academic_year.id),
#                         "name": academic_year.name,
#                     },
#                     "fee_type": fee.installment_item.fee_template_item.fee_type.name,
#                     "installment": fee.installment_item.installment.name,
#                     "amount": fee.amount,
#                     "concession": fee.concession_amount,
#                     "late_fee": fee.late_fee,
#                     "paid_amount": fee.paid_amount,
#                     "payable_amount": payable,
#                     "due_date": fee.due_date,
#                     "status": fee.status,
#                 })
#
#             payment_logger.info(
#                 "pending_student_fee_fetched",
#                 school_id=str(request.school.id),
#                 student_id=str(student.id),
#                 fee_count=fees.count(),
#                 total_payable_amount=str(total_amount),
#             )
#
#             return CustomResponse.successResponse(
#                 data={
#                     "student": {
#                         "id": str(student.id),
#                         "name": student.name,
#                         "admission_number": student.admission_number,
#                     },
#                     "fees": data,
#                     "total_payable_amount": total_amount,
#                 }
#             )
#
#         except Exception:
#
#             payment_logger.exception(
#                 "pending_student_fee_failed",
#                 school_id=str(request.school.id) if hasattr(request, "school") else None,
#                 user_id=str(request.user.id) if request.user.is_authenticated else None,
#                 student_id=request.query_params.get("student_id"),
#             )
#
#             return CustomResponse.errorResponse(
#                 description="Internal server error.",
#             )




class CreatePaymentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        school = request.school
        student_id = request.data.get("student_id")
        amount = request.data.get("amount")

        try:
            payment_logger.info(
                "create_payment_started",
                school_id=str(school.id),
                user_id=str(request.user.id),
                student_id=str(student_id),
                amount=str(amount),
            )

            # -------------------------------------------------
            # Validate required fields
            # -------------------------------------------------

            if not student_id:
                return CustomResponse.errorResponse(
                    description="Student ID is required."
                )

            if amount in (None, ""):
                return CustomResponse.errorResponse(
                    description="Payment amount is required."
                )

            try:
                payment_amount = Decimal(str(amount))
            except (InvalidOperation, ValueError, TypeError):
                return CustomResponse.errorResponse(
                    description="Invalid payment amount."
                )

            if (
                not payment_amount.is_finite()
                or payment_amount <= Decimal("0.00")
                or payment_amount.as_tuple().exponent < -2
            ):
                return CustomResponse.errorResponse(
                    description=(
                        "Payment amount must be positive "
                        "and have at most two decimal places."
                    )
                )

            # -------------------------------------------------
            # Validate student
            # -------------------------------------------------

            student = Student.objects.filter(
                id=student_id,
                school=school,
            ).first()

            if student is None:
                payment_logger.warning(
                    "student_not_found",
                    school_id=str(school.id),
                    student_id=str(student_id),
                )

                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            # IMPORTANT:
            # For parent-facing APIs, verify that request.user is
            # authorized to make payments for this student using
            # your actual parent-student relationship model.

            # -------------------------------------------------
            # Lock and fetch outstanding fees
            # -------------------------------------------------

            with db_transaction.atomic():

                fees = list(
                    StudentFee.objects
                    .select_for_update()
                    .filter(
                        school=school,
                        student=student,
                    )
                    .exclude(
                        status__in=[
                            StudentFee.Status.PAID,
                            StudentFee.Status.WAIVED,
                        ]
                    )
                    .order_by("due_date", "created_at", "id")
                )

                outstanding_fees = []
                total_outstanding = Decimal("0.00")

                for fee in fees:
                    payable_amount = (
                        Decimal(str(fee.total_amount))
                        - Decimal(str(fee.concession_amount or 0))
                        + Decimal(str(fee.late_fee or 0))
                    )

                    outstanding = (
                        payable_amount
                        - Decimal(str(fee.paid_amount or 0))
                    )

                    if outstanding <= Decimal("0.00"):
                        continue

                    outstanding_fees.append(
                        (fee, outstanding)
                    )

                    total_outstanding += outstanding

                if not outstanding_fees:
                    return CustomResponse.errorResponse(
                        description="No outstanding fees found."
                    )

                # -------------------------------------------------
                # Validate requested amount
                # -------------------------------------------------

                if payment_amount > total_outstanding:
                    return CustomResponse.errorResponse(
                        description=(
                            f"Payment amount cannot exceed the "
                            f"outstanding balance of "
                            f"{total_outstanding:.2f}."
                        )
                    )

                # -------------------------------------------------
                # Get payment gateway
                # -------------------------------------------------

                gateway = SchoolPaymentGateway.objects.filter(
                    school=school,
                    is_active=True,
                ).first()

                if gateway is None:
                    payment_logger.warning(
                        "payment_gateway_not_configured",
                        school_id=str(school.id),
                    )

                    return CustomResponse.errorResponse(
                        description="Payment gateway not configured."
                    )

                # -------------------------------------------------
                # Create payment transaction
                # -------------------------------------------------

                payment_transaction = PaymentTransaction.objects.create(
                    school=school,
                    student=student,
                    gateway=gateway,
                    transaction_number=(
                        f"TXN-{uuid.uuid4().hex[:12].upper()}"
                    ),
                    amount=payment_amount,
                    status=PaymentTransaction.Status.INITIATED,
                )

                # -------------------------------------------------
                # Allocate requested amount across fee records
                # -------------------------------------------------

                remaining_amount = payment_amount
                transaction_items = []

                for fee, outstanding in outstanding_fees:
                    if remaining_amount <= Decimal("0.00"):
                        break

                    allocated_amount = min(
                        remaining_amount,
                        outstanding,
                    )

                    transaction_items.append(
                        PaymentTransactionItem(
                            transaction=payment_transaction,
                            student_fee=fee,
                            amount=allocated_amount,
                        )
                    )

                    remaining_amount -= allocated_amount

                if remaining_amount != Decimal("0.00"):
                    raise ValueError(
                        "Unable to allocate the requested payment amount."
                    )

                PaymentTransactionItem.objects.bulk_create(
                    transaction_items
                )

                payment_logger.info(
                    "payment_transaction_created",
                    school_id=str(school.id),
                    student_id=str(student.id),
                    transaction_id=str(payment_transaction.id),
                    transaction_number=payment_transaction.transaction_number,
                    amount=str(payment_amount),
                    items_count=len(transaction_items),
                )

                # -------------------------------------------------
                # Initiate PhonePe payment
                # -------------------------------------------------

                phonepe_response = phone_pe_initate(
                    payment_transaction.transaction_number,
                    gateway,
                    payment_transaction.amount,
                    payment_transaction.student.id,
                )

                payment_transaction.gateway_order_id = (
                    phonepe_response.order_id
                )

                payment_transaction.save(
                    update_fields=["gateway_order_id"]
                )

                payment_logger.info(
                    "create_payment_completed",
                    school_id=str(school.id),
                    student_id=str(student.id),
                    transaction_id=str(payment_transaction.id),
                    amount=str(payment_amount),
                    gateway_order_id=payment_transaction.gateway_order_id,
                )

                return CustomResponse.successResponse(
                    description="Payment created successfully.",
                    data={
                        "transaction_id": str(payment_transaction.id),
                        "transaction_number": (
                            payment_transaction.transaction_number
                        ),
                        "student_id": str(student.id),
                        "amount": str(payment_transaction.amount),
                        "token": phonepe_response.token,
                        "order_id": phonepe_response.order_id,
                        "state": phonepe_response.state,
                        "expire_at": phonepe_response.expire_at,
                    },
                )

        except Exception:
            payment_logger.exception(
                "create_payment_failed",
                school_id=str(school.id),
                user_id=str(request.user.id),
                student_id=str(student_id),
            )

            return CustomResponse.errorResponse(
                description="Internal server error."
            )

# class CreatePaymentAPIView(APIView):
#
#     permission_classes = [
#         IsAuthenticated,
#     ]
#
#     def post(self, request):
#
#         try:
#
#             payment_logger.info(
#                 "create_payment_started",
#                 school_id=str(request.school.id),
#                 user_id=str(request.user.id),
#                 request_data=request.data,
#             )
#
#             school = request.school
#
#             student = Student.objects.filter(
#                 id=request.data.get("student_id"),
#                 school=school,
#             ).first()
#
#             if student is None:
#
#                 payment_logger.warning(
#                     "student_not_found",
#                     school_id=str(school.id),
#                     student_id=request.data.get("student_id"),
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="Student not found.",
#                 )
#
#             student_fee_ids = request.data.get(
#                 "student_fee_ids",
#                 [],
#             )
#
#             if not student_fee_ids:
#
#                 payment_logger.warning(
#                     "student_fee_ids_missing",
#                     student_id=str(student.id),
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="Please select fees.",
#                 )
#
#             fees = StudentFee.objects.filter(
#                 id__in=student_fee_ids,
#                 student=student,
#             ).exclude(
#                 status=StudentFee.Status.PAID,
#             )
#
#             if not fees.exists():
#
#                 payment_logger.warning(
#                     "pending_fees_not_found",
#                     student_id=str(student.id),
#                     fee_ids=student_fee_ids,
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="No pending fees found.",
#                 )
#
#             total_amount = sum(
#                 fee.payable_amount
#                 for fee in fees
#             )
#
#             payment_logger.info(
#                 "payment_amount_calculated",
#                 student_id=str(student.id),
#                 fee_count=fees.count(),
#                 total_amount=str(total_amount),
#             )
#
#             gateway = SchoolPaymentGateway.objects.filter(
#                 school=school,
#                 is_active=True,
#             ).first()
#
#             if gateway is None:
#
#                 payment_logger.warning(
#                     "payment_gateway_not_configured",
#                     school_id=str(school.id),
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="Payment gateway not configured.",
#                 )
#
#             transaction = PaymentTransaction.objects.create(
#                 school=school,
#                 student=student,
#                 gateway=gateway,
#                 transaction_number=f"TXN-{uuid.uuid4().hex[:12].upper()}",
#                 amount=total_amount,
#                 status=PaymentTransaction.Status.INITIATED,
#             )
#
#             payment_logger.info(
#                 "payment_transaction_created",
#                 transaction_id=str(transaction.id),
#                 transaction_number=transaction.transaction_number,
#             )
#
#             for fee in fees:
#
#                 PaymentTransactionItem.objects.create(
#                     transaction=transaction,
#                     student_fee=fee,
#                     amount=fee.payable_amount,
#                 )
#
#             payment_logger.info(
#                 "payment_transaction_items_created",
#                 transaction_id=str(transaction.id),
#                 items_count=fees.count(),
#             )
#
#             phonepe_response = phone_pe_initate(
#                 transaction.transaction_number,
#                 gateway,
#                 transaction.amount,
#                 transaction.student.id,
#             )
#
#             payment_logger.info(
#                 "phonepe_payment_initiated",
#                 transaction_id=str(transaction.id),
#                 order_id=phonepe_response.order_id,
#                 state=phonepe_response.state,
#             )
#
#             transaction.gateway_order_id = phonepe_response.order_id
#
#             transaction.save(
#                 update_fields=[
#                     "gateway_order_id",
#                 ]
#             )
#
#             payment_logger.info(
#                 "payment_transaction_updated",
#                 transaction_id=str(transaction.id),
#                 gateway_order_id=transaction.gateway_order_id,
#             )
#
#             payment_logger.info(
#                 "create_payment_completed",
#                 transaction_id=str(transaction.id),
#                 student_id=str(student.id),
#             )
#
#             return CustomResponse.successResponse(
#                 description="Payment created successfully.",
#                 data={
#                     "transaction_id": str(transaction.id),
#                     "transaction_number": transaction.transaction_number,
#                     "amount": transaction.amount,
#                     "token": phonepe_response.token,
#                     "order_id": phonepe_response.order_id,
#                     "state": phonepe_response.state,
#                     "expire_at": phonepe_response.expire_at,
#                 },
#             )
#
#         except Exception:
#
#             payment_logger.exception(
#                 "create_payment_failed",
#                 school_id=str(request.school.id) if hasattr(request, "school") else None,
#                 user_id=str(request.user.id) if request.user.is_authenticated else None,
#             )
#
#             return CustomResponse.errorResponse(
#                 description="Internal server error.",
#             )
#

class PhonePeWebhookAPIView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):

        payment_logger.info("phonepe_webhook_received")

        raw_body = request.body.decode("utf-8")
        auth_header = request.headers.get("Authorization")

        gateway = SchoolPaymentGateway.objects.filter(
            gateway=SchoolPaymentGateway.Gateway.PHONEPE,
            is_active=True,
        ).first()

        if gateway is None:
            payment_logger.warning("phonepe_gateway_not_configured")

            return CustomResponse.successResponse(
                description="Gateway not configured.",
            )

        # -----------------------------------------------------
        # Validate PhonePe callback
        # -----------------------------------------------------

        try:
            client = get_phonepe_client(gateway)

            callback = client.validate_callback(
                username="Ranjith",
                password="password123",
                callback_header_data=auth_header,
                callback_response_data=raw_body,
            )

        except Exception:
            payment_logger.exception(
                "phonepe_webhook_validation_failed",
            )

            return CustomResponse.errorResponse(
                description="Webhook validation failed.",
            )

        if not callback.payload:
            payment_logger.info(
                "phonepe_validation_callback_received",
            )

            return CustomResponse.successResponse(
                description="Validation success.",
            )

        payload = callback.payload

        merchant_order_id = payload.merchant_order_id
        gateway_order_id = payload.order_id
        state = payload.state

        payment_logger.info(
            "phonepe_callback_received",
            merchant_order_id=merchant_order_id,
            gateway_order_id=gateway_order_id,
            state=state,
        )

        try:
            with transaction.atomic():

                # Lock transaction to prevent duplicate processing.
                payment_transaction = (
                    PaymentTransaction.objects
                    .select_for_update()
                    .select_related("student")
                    .filter(
                        transaction_number=merchant_order_id,
                        gateway=gateway,
                    )
                    .first()
                )

                if payment_transaction is None:
                    payment_logger.warning(
                        "payment_transaction_not_found",
                        merchant_order_id=merchant_order_id,
                    )

                    return CustomResponse.successResponse(
                        description="Transaction not found.",
                    )

                # -------------------------------------------------
                # Validate gateway order ID
                # -------------------------------------------------

                if (
                    payment_transaction.gateway_order_id
                    and payment_transaction.gateway_order_id
                    != gateway_order_id
                ):
                    payment_logger.warning(
                        "phonepe_order_id_mismatch",
                        transaction_id=str(payment_transaction.id),
                        expected_gateway_order_id=(
                            payment_transaction.gateway_order_id
                        ),
                        received_gateway_order_id=gateway_order_id,
                    )

                    return CustomResponse.errorResponse(
                        description="Order mismatch.",
                    )

                # -------------------------------------------------
                # Handle duplicate successful callbacks
                # -------------------------------------------------

                if (
                    payment_transaction.status
                    == PaymentTransaction.Status.SUCCESS
                ):
                    payment_logger.info(
                        "phonepe_duplicate_webhook",
                        transaction_id=str(payment_transaction.id),
                    )

                    return CustomResponse.successResponse(
                        description="Already processed.",
                    )

                # Prevent a late callback from changing a terminal
                # failure/cancellation into a different state.
                if payment_transaction.status in [
                    PaymentTransaction.Status.FAILED,
                    PaymentTransaction.Status.CANCELLED,
                ]:
                    payment_logger.warning(
                        "phonepe_callback_for_terminal_transaction",
                        transaction_id=str(payment_transaction.id),
                        current_status=payment_transaction.status,
                        received_state=state,
                    )

                    return CustomResponse.successResponse(
                        description="Transaction already finalized.",
                    )

                payment_transaction.gateway_transaction_id = (
                    gateway_order_id
                )

                # -------------------------------------------------
                # Successful payment
                # -------------------------------------------------

                if state == "COMPLETED":

                    payment_transaction.status = (
                        PaymentTransaction.Status.SUCCESS
                    )
                    payment_transaction.paid_at = timezone.now()

                    payment_transaction.save(
                        update_fields=[
                            "gateway_transaction_id",
                            "status",
                            "paid_at",
                        ],
                    )

                    self.update_student_fees(payment_transaction)

                    payment_logger.info(
                        "payment_completed",
                        transaction_id=str(payment_transaction.id),
                        student_id=str(payment_transaction.student_id),
                        amount=str(payment_transaction.amount),
                    )

                elif state == "FAILED":

                    payment_transaction.status = (
                        PaymentTransaction.Status.FAILED
                    )

                    payment_transaction.save(
                        update_fields=[
                            "gateway_transaction_id",
                            "status",
                        ],
                    )

                    payment_logger.info(
                        "payment_failed",
                        transaction_id=str(payment_transaction.id),
                    )

                elif state == "PENDING":

                    payment_transaction.status = (
                        PaymentTransaction.Status.PENDING
                    )

                    payment_transaction.save(
                        update_fields=[
                            "gateway_transaction_id",
                            "status",
                        ],
                    )

                    payment_logger.info(
                        "payment_pending",
                        transaction_id=str(payment_transaction.id),
                    )

                else:

                    payment_transaction.status = (
                        PaymentTransaction.Status.CANCELLED
                    )

                    payment_transaction.save(
                        update_fields=[
                            "gateway_transaction_id",
                            "status",
                        ],
                    )

                    payment_logger.info(
                        "payment_cancelled",
                        transaction_id=str(payment_transaction.id),
                        state=state,
                    )

        except Exception:
            payment_logger.exception(
                "phonepe_webhook_processing_failed",
                merchant_order_id=merchant_order_id,
            )

            return CustomResponse.errorResponse(
                description="Failed to process webhook.",
            )

        payment_logger.info(
            "phonepe_webhook_completed",
            transaction_id=str(payment_transaction.id),
            status=payment_transaction.status,
        )

        return CustomResponse.successResponse(
            description="Webhook processed successfully.",
        )

    def update_student_fees(self, payment_transaction):

        payment_logger.info(
            "student_fee_update_started",
            transaction_id=str(payment_transaction.id),
        )

        # -----------------------------------------------------
        # Lock and retrieve allocated fee items
        # -----------------------------------------------------

        items = list(
            PaymentTransactionItem.objects
            .select_for_update()
            .filter(
                transaction=payment_transaction,
            )
            .order_by("id")
        )

        if not items:
            raise ValueError(
                "No fee allocations found for this payment transaction."
            )

        # Lock fee rows as well.
        fee_ids = [item.student_fee_id for item in items]

        locked_fees = {
            fee.id: fee
            for fee in (
                StudentFee.objects
                .select_for_update()
                .filter(id__in=fee_ids)
                .order_by("id")
            )
        }

        for item in items:

            fee = locked_fees.get(item.student_fee_id)

            if fee is None:
                raise ValueError(
                    f"Student fee {item.student_fee_id} not found."
                )

            previous_paid_amount = Decimal(
                str(fee.paid_amount or 0)
            )

            allocated_amount = Decimal(str(item.amount))

            if allocated_amount <= Decimal("0.00"):
                raise ValueError(
                    "Payment allocation must be greater than zero."
                )

            # -------------------------------------------------
            # Update paid amount
            # -------------------------------------------------

            fee.paid_amount = previous_paid_amount + allocated_amount

            payable_amount = (
                Decimal(str(fee.total_amount))
                - Decimal(str(fee.concession_amount or 0))
                + Decimal(str(fee.late_fee or 0))
            )

            if fee.paid_amount >= payable_amount:
                fee.status = StudentFee.Status.PAID

            elif (
                fee.due_date
                and fee.due_date < timezone.localdate()
            ):
                fee.status = StudentFee.Status.OVERDUE

            else:
                fee.status = StudentFee.Status.PARTIAL

            fee.save(
                update_fields=[
                    "paid_amount",
                    "status",
                    "updated_at",
                ],
            )

            payment_logger.info(
                "student_fee_updated",
                student_fee_id=str(fee.id),
                previous_paid_amount=str(previous_paid_amount),
                allocated_amount=str(allocated_amount),
                current_paid_amount=str(fee.paid_amount),
                status=fee.status,
            )

        # -----------------------------------------------------
        # Recalculate StudentFeeSummary
        # -----------------------------------------------------

        student = payment_transaction.student
        academic_year = student.academic_year

        totals = (
            StudentFee.objects
            .filter(
                school=payment_transaction.school,
                student=student,
                fee_template__academic_year=academic_year,
            )
            .exclude(
                status=StudentFee.Status.WAIVED,
            )
            .aggregate(
                total_fee=Sum("total_amount"),
                total_concession=Sum("concession_amount"),
                total_late_fee=Sum("late_fee"),
                total_paid=Sum("paid_amount"),
            )
        )

        total_fee = totals["total_fee"] or Decimal("0.00")
        total_concession = (
            totals["total_concession"] or Decimal("0.00")
        )
        total_late_fee = (
            totals["total_late_fee"] or Decimal("0.00")
        )
        total_paid = totals["total_paid"] or Decimal("0.00")

        outstanding_amount = (
            total_fee
            - total_concession
            + total_late_fee
            - total_paid
        )

        summary, _ = StudentFeeSummary.objects.update_or_create(
            school=payment_transaction.school,
            student=student,
            academic_year=academic_year,
            defaults={
                "total_fee": total_fee,
                "total_concession": total_concession,
                "total_late_fee": total_late_fee,
                "total_paid": total_paid,
                "outstanding_amount": max(
                    outstanding_amount,
                    Decimal("0.00"),
                ),
            },
        )

        payment_logger.info(
            "student_fee_summary_updated",
            transaction_id=str(payment_transaction.id),
            student_id=str(student.id),
            summary_id=str(summary.id),
            total_fee=str(summary.total_fee),
            total_concession=str(summary.total_concession),
            total_paid=str(summary.total_paid),
            outstanding_amount=str(summary.outstanding_amount),
        )

        payment_logger.info(
            "student_fee_update_completed",
            transaction_id=str(payment_transaction.id),
        )

#
# class PhonePeWebhookAPIView(APIView):
#
#     permission_classes = [AllowAny]
#     authentication_classes = []
#
#     def post(self, request):
#
#         payment_logger.info(
#             "phonepe_webhook_received",
#         )
#
#         raw_body = request.body.decode("utf-8")
#         auth_header = request.headers.get("Authorization")
#
#         gateway = SchoolPaymentGateway.objects.filter(
#             gateway=SchoolPaymentGateway.Gateway.PHONEPE,
#             is_active=True,
#         ).first()
#
#         if gateway is None:
#
#             payment_logger.warning(
#                 "phonepe_gateway_not_configured",
#             )
#
#             return CustomResponse.successResponse(
#                 description="Gateway not configured.",
#             )
#
#         try:
#
#             client = get_phonepe_client(gateway)
#
#             callback = client.validate_callback(
#                 username="Ranjith",
#                 password="password123",
#                 callback_header_data=auth_header,
#                 callback_response_data=raw_body,
#             )
#
#         except Exception:
#
#             payment_logger.exception(
#                 "phonepe_webhook_validation_failed",
#             )
#
#             return CustomResponse.successResponse(
#                 description="Ignored",
#             )
#
#         if not callback.payload:
#
#             payment_logger.info(
#                 "phonepe_validation_callback_received",
#             )
#
#             return CustomResponse.successResponse(
#                 description="Validation success.",
#             )
#
#         payload = callback.payload
#
#         merchant_order_id = payload.merchant_order_id
#         gateway_order_id = payload.order_id
#         state = payload.state
#
#         payment_logger.info(
#             "phonepe_callback_received",
#             merchant_order_id=merchant_order_id,
#             gateway_order_id=gateway_order_id,
#             state=state,
#         )
#
#         payment_transaction = PaymentTransaction.objects.select_related(
#             "student",
#         ).filter(
#             transaction_number=merchant_order_id,
#         ).first()
#
#         if payment_transaction is None:
#
#             payment_logger.warning(
#                 "payment_transaction_not_found",
#                 merchant_order_id=merchant_order_id,
#             )
#
#             return CustomResponse.successResponse(
#                 description="Transaction not found.",
#             )
#
#         if (
#             payment_transaction.gateway_order_id
#             and payment_transaction.gateway_order_id != gateway_order_id
#         ):
#
#             payment_logger.warning(
#                 "phonepe_order_id_mismatch",
#                 transaction_id=str(payment_transaction.id),
#                 expected_gateway_order_id=payment_transaction.gateway_order_id,
#                 received_gateway_order_id=gateway_order_id,
#             )
#
#             return CustomResponse.successResponse(
#                 description="Order mismatch.",
#             )
#
#         if payment_transaction.status == PaymentTransaction.Status.SUCCESS:
#
#             payment_logger.info(
#                 "phonepe_duplicate_webhook",
#                 transaction_id=str(payment_transaction.id),
#             )
#
#             return CustomResponse.successResponse(
#                 description="Already processed.",
#             )
#
#         try:
#
#             with transaction.atomic():
#
#                 payment_transaction.gateway_transaction_id = gateway_order_id
#
#                 if state == "COMPLETED":
#
#                     payment_transaction.status = (
#                         PaymentTransaction.Status.SUCCESS
#                     )
#
#                     payment_transaction.paid_at = timezone.now()
#
#                     payment_transaction.save(
#                         update_fields=[
#                             "gateway_transaction_id",
#                             "status",
#                             "paid_at",
#                         ],
#                     )
#
#                     self.update_student_fees(
#                         payment_transaction,
#                     )
#
#                     payment_logger.info(
#                         "payment_completed",
#                         transaction_id=str(payment_transaction.id),
#                     )
#
#                 elif state == "FAILED":
#
#                     payment_transaction.status = (
#                         PaymentTransaction.Status.FAILED
#                     )
#
#                     payment_transaction.save(
#                         update_fields=[
#                             "gateway_transaction_id",
#                             "status",
#                         ],
#                     )
#
#                     payment_logger.info(
#                         "payment_failed",
#                         transaction_id=str(payment_transaction.id),
#                     )
#
#                 elif state == "PENDING":
#
#                     payment_transaction.status = (
#                         PaymentTransaction.Status.PENDING
#                     )
#
#                     payment_transaction.save(
#                         update_fields=[
#                             "gateway_transaction_id",
#                             "status",
#                         ],
#                     )
#
#                     payment_logger.info(
#                         "payment_pending",
#                         transaction_id=str(payment_transaction.id),
#                     )
#
#                 else:
#
#                     payment_transaction.status = (
#                         PaymentTransaction.Status.CANCELLED
#                     )
#
#                     payment_transaction.save(
#                         update_fields=[
#                             "gateway_transaction_id",
#                             "status",
#                         ],
#                     )
#
#                     payment_logger.info(
#                         "payment_cancelled",
#                         transaction_id=str(payment_transaction.id),
#                         state=state,
#                     )
#
#         except Exception:
#
#             payment_logger.exception(
#                 "phonepe_webhook_processing_failed",
#                 transaction_id=str(payment_transaction.id),
#             )
#
#             return CustomResponse.errorResponse(
#                 description="Failed to process webhook.",
#             )
#
#         payment_logger.info(
#             "phonepe_webhook_completed",
#             transaction_id=str(payment_transaction.id),
#             status=payment_transaction.status,
#         )
#
#         return CustomResponse.successResponse(
#             description="Webhook processed successfully.",
#         )
#
#     def update_student_fees(self, payment_transaction):
#
#         payment_logger.info(
#             "student_fee_update_started",
#             transaction_id=str(payment_transaction.id),
#         )
#
#         items = (
#             PaymentTransactionItem.objects.select_related(
#                 "student_fee",
#             )
#             .filter(
#                 transaction=payment_transaction,
#             )
#         )
#
#         for item in items:
#
#             fee = item.student_fee
#
#             previous_paid_amount = fee.paid_amount
#
#             fee.paid_amount += item.amount
#
#             if fee.paid_amount >= fee.payable_amount:
#
#                 fee.status = StudentFee.Status.PAID
#
#             else:
#
#                 fee.status = StudentFee.Status.PARTIAL
#
#             fee.save(
#                 update_fields=[
#                     "paid_amount",
#                     "status",
#                 ],
#             )
#
#             payment_logger.info(
#                 "student_fee_updated",
#                 student_fee_id=str(fee.id),
#                 previous_paid_amount=str(previous_paid_amount),
#                 current_paid_amount=str(fee.paid_amount),
#                 status=fee.status,
#             )
#
#         payment_logger.info(
#             "student_fee_update_completed",
#             transaction_id=str(payment_transaction.id),
#         )

class CompletedStudentFeePaymentsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student_id = request.query_params.get("student_id")

        payment_logger.info(
            "completed_fee_payments_requested",
            student_id=student_id,
            user_id=str(request.user.id),
        )

        try:
            if not student_id:
                payment_logger.warning(
                    "completed_fee_payments_failed",
                    reason="student_id_required",
                    user_id=str(request.user.id),
                )
                return CustomResponse.errorResponse(
                    description="student_id is required."
                )

            student = (
                Student.objects.select_related("academic_year")
                .filter(id=student_id)
                .first()
            )

            if student is None:
                payment_logger.warning(
                    "completed_fee_payments_failed",
                    reason="student_not_found",
                    student_id=student_id,
                    user_id=str(request.user.id),
                )
                return CustomResponse.errorResponse(
                    description="Student not found."
                )

            transactions = (
                PaymentTransaction.objects.select_related("gateway")
                .prefetch_related(
                    Prefetch(
                        "items",
                        queryset=PaymentTransactionItem.objects.select_related(
                            "student_fee",
                            "student_fee__fee_template",
                            "student_fee__fee_template__academic_year",
                            "student_fee__fee_type",
                        ),
                    )
                )
                .filter(
                    student=student,
                    status=PaymentTransaction.Status.SUCCESS,
                )
                .order_by("-paid_at")
            )

            total_paid_amount = Decimal("0.00")
            payments = []

            for transaction in transactions:
                fee_items = []

                for item in transaction.items.all():
                    fee = item.student_fee
                    fee_template = fee.fee_template
                    academic_year = (
                        fee_template.academic_year if fee_template else None
                    )

                    fee_items.append({
                        "student_fee_id": str(fee.id),
                        "academic_year": {
                            "id": str(academic_year.id),
                            "name": academic_year.name,
                        } if academic_year else None,
                        "fee_type": fee.fee_type.name,
                        "amount": str(fee.total_amount),
                        "concession": str(fee.concession_amount),
                        "late_fee": str(fee.late_fee),
                        "paid_amount": str(item.amount),
                        "status": fee.status,
                    })

                total_paid_amount += transaction.amount

                payments.append({
                    "transaction_id": str(transaction.id),
                    "reference_number": transaction.transaction_number,
                    "gateway_order_id": transaction.gateway_order_id,
                    "gateway_transaction_id": (
                        transaction.gateway_transaction_id
                    ),
                    "payment_gateway": transaction.gateway.gateway,
                    "payment_date": transaction.paid_at,
                    "total_amount": str(transaction.amount),
                    "fees": fee_items,
                })

            payment_logger.info(
                "completed_fee_payments_fetched",
                student_id=str(student.id),
                transaction_count=len(payments),
                total_paid_amount=str(total_paid_amount),
                user_id=str(request.user.id),
            )

            return CustomResponse.successResponse(
                description="Completed fee payments fetched successfully.",
                data={
                    "student": {
                        "id": str(student.id),
                        "name": student.name,
                        "admission_number": student.admission_number,
                        "academic_year": {
                            "id": str(student.academic_year.id),
                            "name": student.academic_year.name,
                        } if student.academic_year else None,
                    },
                    "total_paid_amount": str(total_paid_amount),
                    "payments": payments,
                },
            )

        except Exception:
            payment_logger.exception(
                "completed_fee_payments_api_failed",
                student_id=student_id,
                user_id=str(request.user.id),
            )

            return CustomResponse.errorResponse(
                description=(
                    "Something went wrong while fetching completed fee payments."
                )
            )

# class CompletedStudentFeePaymentsAPIView(APIView):
#
#     permission_classes = [IsAuthenticated]
#
#     def get(self, request):
#
#         student_id = request.query_params.get("student_id")
#
#         payment_logger.info(
#             "completed_fee_payments_requested",
#             student_id=student_id,
#             user_id=str(request.user.id),
#         )
#
#         try:
#
#             if not student_id:
#
#                 payment_logger.warning(
#                     "completed_fee_payments_failed",
#                     reason="student_id_required",
#                     user_id=str(request.user.id),
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="student_id is required."
#                 )
#
#             student = Student.objects.select_related(
#                 "academic_year",
#             ).filter(
#                 id=student_id,
#             ).first()
#
#             if student is None:
#
#                 payment_logger.warning(
#                     "completed_fee_payments_failed",
#                     reason="student_not_found",
#                     student_id=student_id,
#                     user_id=str(request.user.id),
#                 )
#
#                 return CustomResponse.errorResponse(
#                     description="Student not found."
#                 )
#
#             transactions = PaymentTransaction.objects.select_related(
#                 "gateway",
#             ).prefetch_related(
#                 "items",
#                 "items__student_fee",
#                 "items__student_fee__installment_item",
#                 "items__student_fee__installment_item__fee_template_item",
#                 "items__student_fee__installment_item__fee_template_item__fee_type",
#                 "items__student_fee__installment_item__installment",
#                 "items__student_fee__installment_item__installment__collection_plan",
#                 "items__student_fee__installment_item__installment__collection_plan__fee_template",
#                 "items__student_fee__installment_item__installment__collection_plan__fee_template__academic_year",
#             ).filter(
#                 student=student,
#                 status=PaymentTransaction.Status.SUCCESS,
#             ).order_by(
#                 "-paid_at",
#             )
#
#             total_paid_amount = 0
#             payments = []
#
#             for transaction in transactions:
#
#                 fee_items = []
#
#                 for item in transaction.items.all():
#
#                     fee = item.student_fee
#
#                     academic_year = (
#                         fee.installment_item
#                         .installment
#                         .collection_plan
#                         .fee_template
#                         .academic_year
#                     )
#
#                     fee_items.append({
#                         "student_fee_id": str(fee.id),
#                         "academic_year": {
#                             "id": str(academic_year.id),
#                             "name": academic_year.name,
#                         },
#                         "fee_type": fee.installment_item.fee_template_item.fee_type.name,
#                         "installment": fee.installment_item.installment.name,
#                         "amount": fee.amount,
#                         "concession": fee.concession_amount,
#                         "late_fee": fee.late_fee,
#                         "paid_amount": item.amount,
#                         "status": fee.status,
#                     })
#
#                 total_paid_amount += transaction.amount
#
#                 payments.append({
#                     "transaction_id": str(transaction.id),
#                     "reference_number": transaction.transaction_number,
#                     "gateway_order_id": transaction.gateway_order_id,
#                     "gateway_transaction_id": transaction.gateway_transaction_id,
#                     "payment_gateway": transaction.gateway.gateway,
#                     "payment_date": transaction.paid_at,
#                     "total_amount": transaction.amount,
#                     "fees": fee_items,
#                 })
#
#             payment_logger.info(
#                 "completed_fee_payments_fetched",
#                 student_id=str(student.id),
#                 transaction_count=transactions.count(),
#                 total_paid_amount=str(total_paid_amount),
#                 user_id=str(request.user.id),
#             )
#
#             return CustomResponse.successResponse(
#                 description="Completed fee payments fetched successfully.",
#                 data={
#                     "student": {
#                         "id": str(student.id),
#                         "name": student.name,
#                         "admission_number": student.admission_number,
#                         "academic_year": {
#                             "id": str(student.academic_year.id),
#                             "name": student.academic_year.name,
#                         } if student.academic_year else None,
#                     },
#                     "total_paid_amount": total_paid_amount,
#                     "payments": payments,
#                 },
#             )
#
#         except Exception:
#
#             payment_logger.exception(
#                 "completed_fee_payments_api_failed",
#                 student_id=student_id,
#                 user_id=str(request.user.id),
#             )
#
#             return CustomResponse.errorResponse(
#                 description="Something went wrong while fetching completed fee payments."
#             )

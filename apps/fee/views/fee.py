import uuid
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.fee.models import StudentFee, SchoolPaymentGateway
from apps.payment.models import PaymentTransaction, PaymentTransactionItem
from apps.payment.services.gateway import PaymentGatewayService
from apps.payment.services.phonepe import create_phonepe_payment, get_phonepe_client, phone_pe_initate
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from django.db import transaction

from shared.utils.logger import payment_logger




class PendingStudentFeeAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        try:

            payment_logger.info(
                "pending_student_fee_started",
                school_id=str(request.school.id),
                user_id=str(request.user.id),
                student_id=request.query_params.get("student_id"),
            )

            student = Student.objects.filter(
                id=request.query_params.get("student_id"),
            ).first()

            if student is None:

                payment_logger.warning(
                    "pending_student_fee_student_not_found",
                    school_id=str(request.school.id),
                    student_id=request.query_params.get("student_id"),
                )

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

            payment_logger.info(
                "pending_student_fee_fetched",
                school_id=str(request.school.id),
                student_id=str(student.id),
                fee_count=fees.count(),
                total_payable_amount=str(total_amount),
            )

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

        except Exception:

            payment_logger.exception(
                "pending_student_fee_failed",
                school_id=str(request.school.id) if hasattr(request, "school") else None,
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                student_id=request.query_params.get("student_id"),
            )

            return CustomResponse.errorResponse(
                description="Internal server error.",
            )

class CreatePaymentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        try:

            payment_logger.info(
                "create_payment_started",
                school_id=str(request.school.id),
                user_id=str(request.user.id),
                request_data=request.data,
            )

            school = request.school

            student = Student.objects.filter(
                id=request.data.get("student_id"),
                school=school,
            ).first()

            if student is None:

                payment_logger.warning(
                    "student_not_found",
                    school_id=str(school.id),
                    student_id=request.data.get("student_id"),
                )

                return CustomResponse.errorResponse(
                    description="Student not found.",
                )

            student_fee_ids = request.data.get(
                "student_fee_ids",
                [],
            )

            if not student_fee_ids:

                payment_logger.warning(
                    "student_fee_ids_missing",
                    student_id=str(student.id),
                )

                return CustomResponse.errorResponse(
                    description="Please select fees.",
                )

            fees = StudentFee.objects.filter(
                id__in=student_fee_ids,
                student=student,
            ).exclude(
                status=StudentFee.Status.PAID,
            )

            if not fees.exists():

                payment_logger.warning(
                    "pending_fees_not_found",
                    student_id=str(student.id),
                    fee_ids=student_fee_ids,
                )

                return CustomResponse.errorResponse(
                    description="No pending fees found.",
                )

            total_amount = sum(
                fee.payable_amount
                for fee in fees
            )

            payment_logger.info(
                "payment_amount_calculated",
                student_id=str(student.id),
                fee_count=fees.count(),
                total_amount=str(total_amount),
            )

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
                    description="Payment gateway not configured.",
                )

            transaction = PaymentTransaction.objects.create(
                school=school,
                student=student,
                gateway=gateway,
                transaction_number=f"TXN-{uuid.uuid4().hex[:12].upper()}",
                amount=total_amount,
                status=PaymentTransaction.Status.INITIATED,
            )

            payment_logger.info(
                "payment_transaction_created",
                transaction_id=str(transaction.id),
                transaction_number=transaction.transaction_number,
            )

            for fee in fees:

                PaymentTransactionItem.objects.create(
                    transaction=transaction,
                    student_fee=fee,
                    amount=fee.payable_amount,
                )

            payment_logger.info(
                "payment_transaction_items_created",
                transaction_id=str(transaction.id),
                items_count=fees.count(),
            )

            phonepe_response = phone_pe_initate(
                transaction.transaction_number,
                gateway,
                transaction.amount,
                transaction.student.id,
            )

            payment_logger.info(
                "phonepe_payment_initiated",
                transaction_id=str(transaction.id),
                order_id=phonepe_response.order_id,
                state=phonepe_response.state,
            )

            transaction.gateway_order_id = phonepe_response.order_id

            transaction.save(
                update_fields=[
                    "gateway_order_id",
                ]
            )

            payment_logger.info(
                "payment_transaction_updated",
                transaction_id=str(transaction.id),
                gateway_order_id=transaction.gateway_order_id,
            )

            payment_logger.info(
                "create_payment_completed",
                transaction_id=str(transaction.id),
                student_id=str(student.id),
            )

            return CustomResponse.successResponse(
                description="Payment created successfully.",
                data={
                    "transaction_id": str(transaction.id),
                    "transaction_number": transaction.transaction_number,
                    "amount": transaction.amount,
                    "token": phonepe_response.token,
                    "order_id": phonepe_response.order_id,
                    "state": phonepe_response.state,
                    "expire_at": phonepe_response.expire_at,
                },
            )

        except Exception:

            payment_logger.exception(
                "create_payment_failed",
                school_id=str(request.school.id) if hasattr(request, "school") else None,
                user_id=str(request.user.id) if request.user.is_authenticated else None,
            )

            return CustomResponse.errorResponse(
                description="Internal server error.",
            )





class PhonePeWebhookAPIView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):

        payment_logger.info(
            "phonepe_webhook_received",
        )

        raw_body = request.body.decode("utf-8")
        auth_header = request.headers.get("Authorization")

        gateway = SchoolPaymentGateway.objects.filter(
            gateway=SchoolPaymentGateway.Gateway.PHONEPE,
            is_active=True,
        ).first()

        if gateway is None:

            payment_logger.warning(
                "phonepe_gateway_not_configured",
            )

            return CustomResponse.successResponse(
                description="Gateway not configured.",
            )

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

            return CustomResponse.successResponse(
                description="Ignored",
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

        payment_transaction = PaymentTransaction.objects.select_related(
            "student",
        ).filter(
            transaction_number=merchant_order_id,
        ).first()

        if payment_transaction is None:

            payment_logger.warning(
                "payment_transaction_not_found",
                merchant_order_id=merchant_order_id,
            )

            return CustomResponse.successResponse(
                description="Transaction not found.",
            )

        if (
            payment_transaction.gateway_order_id
            and payment_transaction.gateway_order_id != gateway_order_id
        ):

            payment_logger.warning(
                "phonepe_order_id_mismatch",
                transaction_id=str(payment_transaction.id),
                expected_gateway_order_id=payment_transaction.gateway_order_id,
                received_gateway_order_id=gateway_order_id,
            )

            return CustomResponse.successResponse(
                description="Order mismatch.",
            )

        if payment_transaction.status == PaymentTransaction.Status.SUCCESS:

            payment_logger.info(
                "phonepe_duplicate_webhook",
                transaction_id=str(payment_transaction.id),
            )

            return CustomResponse.successResponse(
                description="Already processed.",
            )

        try:

            with transaction.atomic():

                payment_transaction.gateway_transaction_id = gateway_order_id

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

                    self.update_student_fees(
                        payment_transaction,
                    )

                    payment_logger.info(
                        "payment_completed",
                        transaction_id=str(payment_transaction.id),
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
                transaction_id=str(payment_transaction.id),
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

        items = (
            PaymentTransactionItem.objects.select_related(
                "student_fee",
            )
            .filter(
                transaction=payment_transaction,
            )
        )

        for item in items:

            fee = item.student_fee

            previous_paid_amount = fee.paid_amount

            fee.paid_amount += item.amount

            if fee.paid_amount >= fee.payable_amount:

                fee.status = StudentFee.Status.PAID

            else:

                fee.status = StudentFee.Status.PARTIAL

            fee.save(
                update_fields=[
                    "paid_amount",
                    "status",
                ],
            )

            payment_logger.info(
                "student_fee_updated",
                student_fee_id=str(fee.id),
                previous_paid_amount=str(previous_paid_amount),
                current_paid_amount=str(fee.paid_amount),
                status=fee.status,
            )

        payment_logger.info(
            "student_fee_update_completed",
            transaction_id=str(payment_transaction.id),
        )


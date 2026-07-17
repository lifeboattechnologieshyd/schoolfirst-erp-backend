import uuid
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.fee.models import StudentFee, SchoolPaymentGateway
from apps.payment.models import PaymentTransaction, PaymentTransactionItem
from apps.payment.services.gateway import PaymentGatewayService
from apps.payment.services.phonepe import create_phonepe_payment, get_phonepe_client
from apps.school.models.school import Student
from shared.mixins import CustomResponse
from django.db import transaction

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

class CreatePaymentAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):

        try:

            print("=" * 100)
            print("CREATE PAYMENT API STARTED")
            print("Request Data:", request.data)
            print("=" * 100)

            school = request.school

            print("School:", school)

            student = Student.objects.filter(
                id=request.data.get("student_id"),
                school=school,
            ).first()

            print("Student:", student)

            if student is None:

                print("Student not found")

                return CustomResponse.errorResponse(
                    description="Student not found.",
                )

            student_fee_ids = request.data.get(
                "student_fee_ids",
                [],
            )

            print("Student Fee IDs:", student_fee_ids)

            if not student_fee_ids:

                print("No fee ids selected")

                return CustomResponse.errorResponse(
                    description="Please select fees.",
                )

            fees = StudentFee.objects.filter(
                id__in=student_fee_ids,
                student=student,
            ).exclude(
                status=StudentFee.Status.PAID,
            )

            print("Pending Fees Count:", fees.count())

            if not fees.exists():

                print("No pending fees")

                return CustomResponse.errorResponse(
                    description="No pending fees found.",
                )

            total_amount = 0

            for fee in fees:

                print("-" * 80)
                print("Fee ID:", fee.id)
                print("Amount:", fee.amount)
                print("Payable:", fee.payable_amount)

                total_amount += fee.payable_amount

            print("Total Amount:", total_amount)

            gateway = SchoolPaymentGateway.objects.filter(
                school=school,
                is_active=True,
            ).first()

            print("Gateway:", gateway)

            if gateway is None:

                print("Gateway not configured")

                return CustomResponse.errorResponse(
                    description="Payment gateway not configured.",
                )

            print("Creating transaction...")

            total_amount = sum(
            fee.payable_amount
            for fee in fees)

            amount_paisa = int(total_amount * 100)

            transaction = PaymentTransaction.objects.create(
                school=school,
                student=student,
                gateway=gateway,
                transaction_number=f"TXN-{uuid.uuid4().hex[:12].upper()}",
                amount=total_amount,
                status=PaymentTransaction.Status.INITIATED,
            )
            print("Creating Transaction Items...")

            for fee in fees:

                print(
                    f"Adding Fee -> {fee.id} | "
                    f"{fee.installment_item.fee_template_item.fee_type.name} | "
                    f"Amount: {fee.payable_amount}"
                )
                PaymentTransactionItem.objects.create(
                            transaction=transaction,
                            student_fee=fee,
                            amount=fee.payable_amount,
                        )

            print("Transaction Items Created")

            phonepe_response = create_phonepe_payment(
                transaction,

            )

            transaction.gateway_order_id = phonepe_response["order_id"]

            transaction.save(
                update_fields=[
                    "gateway_order_id",
                ]
            )

            print("Transaction Updated")

            print("=" * 100)
            print("CREATE PAYMENT SUCCESS")
            print("=" * 100)

            return CustomResponse.successResponse(
                description="Payment created successfully.",
                data={
                    "transaction_id": str(transaction.id),
                    "gateway": gateway.gateway,
                    "amount": total_amount,
                    "payment_url": phonepe_response["redirect_url"]}
            )

        except Exception as e:

            import traceback

            print("=" * 100)
            print("CREATE PAYMENT FAILED")
            print(type(e))
            print(str(e))
            traceback.print_exc()
            print("=" * 100)

            return CustomResponse.errorResponse(
                description=str(e),
            )

class PhonePeWebhookAPIView(APIView):

    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    def post(self, request):

        print("=" * 100)
        print("PHONEPE WEBHOOK")
        print("=" * 100)

        raw_body = request.body.decode("utf-8")
        auth_header = request.headers.get("Authorization")

        print("Headers:", request.headers)
        print("Body:", raw_body)

        try:

            gateway = SchoolPaymentGateway.objects.filter(
                gateway=SchoolPaymentGateway.Gateway.PHONEPE,
                is_active=True,
            ).first()

            if gateway is None:

                print("PhonePe gateway not configured")

                return CustomResponse.successResponse(
                    description="Gateway not configured.",
                )

            client = get_phonepe_client(gateway)

            callback = client.validate_callback(
                username="Ranjith",
                password="password123",
                callback_header_data=auth_header,
                callback_response_data=raw_body,
            )

            print("Webhook validated successfully")

        except Exception as e:

            print("Validation Failed:", str(e))

            return CustomResponse.successResponse(
                description="Ignored",
            )

        if not callback.payload:

            print("Validation Ping")

            return CustomResponse.successResponse(
                description="Validation success",
            )

        payload = callback.payload

        merchant_order_id = payload.merchant_order_id

        print("Merchant Order ID:", merchant_order_id)

        payment_transaction = PaymentTransaction.objects.select_related(
            "student",
        ).filter(
            transaction_number=merchant_order_id,
        ).first()

        if payment_transaction is None:

            print("Transaction not found")

            return CustomResponse.successResponse(
                description="Transaction not found.",
            )

        if payment_transaction.status == PaymentTransaction.Status.SUCCESS:

            print("Already processed")

            return CustomResponse.successResponse(
                description="Already processed.",
            )

        state = payload.state

        print("Payment State:", state)

        with transaction.atomic():

            payment_transaction.gateway_transaction_id = payload.order_id

            if state == "COMPLETED":

                payment_transaction.status = PaymentTransaction.Status.SUCCESS
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

                print("Payment Success")

            elif state == "FAILED":

                payment_transaction.status = PaymentTransaction.Status.FAILED

                payment_transaction.save(
                    update_fields=[
                        "gateway_transaction_id",
                        "status",
                    ],
                )

                print("Payment Failed")

            else:

                payment_transaction.status = PaymentTransaction.Status.CANCELLED

                payment_transaction.save(
                    update_fields=[
                        "gateway_transaction_id",
                        "status",
                    ],
                )

                print("Payment Cancelled")

        print("=" * 100)
        print("WEBHOOK COMPLETED")
        print("=" * 100)

        return CustomResponse.successResponse(
            description="Webhook processed.",
        )

    def update_student_fees(self, payment_transaction):

        print("=" * 80)
        print("Updating Student Fees")
        print("=" * 80)

        items = PaymentTransactionItem.objects.select_related(
            "student_fee",
        ).filter(
            transaction=payment_transaction,
        )

        print("Total Items:", items.count())

        for item in items:

            fee = item.student_fee

            print("-" * 80)
            print("Student Fee:", fee.id)
            print("Fee Amount:", fee.amount)
            print("Paid Before:", fee.paid_amount)
            print("Transaction Amount:", item.amount)

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

            print("Paid After:", fee.paid_amount)
            print("Fee Status:", fee.status)

        print("=" * 80)
        print("Student Fee Update Completed")
        print("=" * 80)


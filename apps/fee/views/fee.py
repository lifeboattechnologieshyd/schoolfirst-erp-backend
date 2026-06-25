from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.fee.models import StudentFee, SchoolPaymentGateway
from apps.payment.models import PaymentTransaction, PaymentTransactionItem
from apps.payment.services.gateway import PaymentGatewayService
from apps.school.models.school import Student
from shared.mixins import CustomResponse


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

            transaction = PaymentTransaction.objects.create(
                school=school,
                student=student,
                gateway=gateway.gateway,
                amount=total_amount,
                status=PaymentTransaction.Status.INITIATED,
            )

            print("Transaction Created:", transaction.id)

            for fee in fees:

                print("Creating transaction item for:", fee.id)

                PaymentTransactionItem.objects.create(
                    transaction=transaction,
                    student_fee=fee,
                    amount=fee.payable_amount,
                )

            print("Calling Payment Gateway Service...")

            payment_response = PaymentGatewayService(
                gateway,
            ).create_payment(
                transaction=transaction,
            )

            print("Gateway Response:", payment_response)

            transaction.gateway_order_id = payment_response["order_id"]

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
                    "payment_url": payment_response["payment_url"],
                },
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
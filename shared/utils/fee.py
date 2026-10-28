from django.db.models import Sum, Q

from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment, FeeTemplateItem, FeeConcession, \
    StudentFeeSummary
from apps.payment.models import PaymentTransactionItem, PaymentTransaction
from shared.utils.calendar import create_calendar_event

from django.db import transaction

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from decimal import Decimal, ROUND_HALF_UP

from shared.utils.logger import application_logger, payment_logger


def generate_student_fees(
    *,
    student,
    fee_template,
    concession=None,
):
    application_logger.info(
        "student_fee_generation_started",
        extra={
            "student_id": str(student.id),
            "school_id": str(student.school_id),
            "fee_template_id": str(fee_template.id),
            "concession_id": (
                str(concession.id) if concession else None
            ),
        },
    )

    try:
        with transaction.atomic():

            # ---------------------------------------------------------
            # Fetch fee items
            # ---------------------------------------------------------

            fee_items = list(
                FeeTemplateItem.objects
                .select_related("fee_type")
                .filter(fee_template=fee_template)
                .order_by("id")
            )

            if not fee_items:
                raise ValueError(
                    f"No fee items configured for fee template "
                    f"'{fee_template.name}'."
                )

            # ---------------------------------------------------------
            # Calculate total fee
            # ---------------------------------------------------------

            total_fee = sum(
                (item.amount for item in fee_items),
                Decimal("0.00"),
            )

            if total_fee <= Decimal("0.00"):
                raise ValueError(
                    "Total fee amount must be greater than zero."
                )

            # ---------------------------------------------------------
            # Calculate total concession
            # ---------------------------------------------------------

            total_concession = Decimal("0.00")

            if concession:
                if concession.concession_type == FeeConcession.Type.FLAT:
                    total_concession = concession.value

                elif (
                    concession.concession_type
                    == FeeConcession.Type.PERCENTAGE
                ):
                    total_concession = (
                        total_fee * concession.value
                    ) / Decimal("100")

                if total_concession < Decimal("0.00"):
                    raise ValueError(
                        "Concession amount cannot be negative."
                    )

                total_concession = min(
                    total_concession,
                    total_fee,
                )

            application_logger.info(
                "student_fee_generation_amounts_calculated",
                extra={
                    "student_id": str(student.id),
                    "school_id": str(student.school_id),
                    "fee_template_id": str(fee_template.id),
                    "fee_item_count": len(fee_items),
                    "total_fee": str(total_fee),
                    "total_concession": str(total_concession),
                },
            )

            # ---------------------------------------------------------
            # Prepare StudentFee records
            # ---------------------------------------------------------

            student_fees = []
            allocated_concession = Decimal("0.00")

            for index, item in enumerate(fee_items):

                if index == len(fee_items) - 1:
                    item_concession = (
                        total_concession - allocated_concession
                    )
                else:
                    item_concession = (
                        total_concession * item.amount
                    ) / total_fee

                    item_concession = item_concession.quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP,
                    )

                item_concession = min(
                    item_concession,
                    item.amount,
                )

                allocated_concession += item_concession

                student_fees.append(
                    StudentFee(
                        school=student.school,
                        student=student,
                        fee_template=fee_template,
                        fee_type=item.fee_type,
                        concession=concession,
                        total_amount=item.amount,
                        concession_amount=item_concession,
                        late_fee=Decimal("0.00"),
                        paid_amount=Decimal("0.00"),
                        due_date=None,
                        status=StudentFee.Status.PENDING,
                    )
                )

            # ---------------------------------------------------------
            # Create StudentFee records
            # ---------------------------------------------------------

            StudentFee.objects.bulk_create(
                student_fees,
                ignore_conflicts=True,
            )

            # ---------------------------------------------------------
            # Recalculate StudentFeeSummary
            # ---------------------------------------------------------

            academic_year = fee_template.academic_year

            fee_totals = (
                StudentFee.objects
                .filter(
                    school=student.school,
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

            summary_total_fee = (
                fee_totals["total_fee"] or Decimal("0.00")
            )

            summary_concession = (
                fee_totals["total_concession"] or Decimal("0.00")
            )

            summary_late_fee = (
                fee_totals["total_late_fee"] or Decimal("0.00")
            )

            summary_paid = (
                fee_totals["total_paid"] or Decimal("0.00")
            )

            outstanding_amount = (
                summary_total_fee
                - summary_concession
                + summary_late_fee
                - summary_paid
            )

            summary, _ = StudentFeeSummary.objects.update_or_create(
                school=student.school,
                student=student,
                academic_year=academic_year,
                defaults={
                    "total_fee": summary_total_fee,
                    "total_concession": summary_concession,
                    "total_late_fee": summary_late_fee,
                    "total_paid": summary_paid,
                    "outstanding_amount": max(
                        outstanding_amount,
                        Decimal("0.00"),
                    ),
                },
            )

            application_logger.info(
                "student_fee_generation_completed",
                extra={
                    "student_id": str(student.id),
                    "school_id": str(student.school_id),
                    "fee_template_id": str(fee_template.id),
                    "fee_count": len(student_fees),
                    "total_fee": str(summary.total_fee),
                    "total_concession": str(
                        summary.total_concession
                    ),
                    "total_paid": str(summary.total_paid),
                    "outstanding_amount": str(
                        summary.outstanding_amount
                    ),
                    "summary_id": str(summary.id),
                },
            )

            return student_fees

    except Exception as e:
        application_logger.exception(
            "student_fee_generation_failed",
            extra={
                "student_id": str(student.id),
                "school_id": str(student.school_id),
                "fee_template_id": str(fee_template.id),
                "concession_id": (
                    str(concession.id) if concession else None
                ),
                "error": str(e),
            },
        )

        raise







class PhonePePaymentProcessingMixin:

    # =============================================================
    # PROCESS PHONEPE PAYMENT STATUS
    # =============================================================

    def process_payment_status(
        self,
        payment_transaction_id,
        state,
        gateway_order_id=None,
        gateway_transaction_id=None,
    ):
        """
        Common payment processing method used by:

        1. VerifyPaymentAPIView
        2. PhonePeWebhookAPIView

        The PaymentTransaction row is locked before processing.

        This guarantees that if Webhook and Verify API arrive
        simultaneously, only one of them can process SUCCESS
        and update the student fees.
        """

        with transaction.atomic():

            # -----------------------------------------------------
            # Lock payment transaction
            # -----------------------------------------------------

            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .select_related(
                    "student",
                    "gateway",
                )
                .get(
                    id=payment_transaction_id,
                )
            )

            current_status = payment_transaction.status

            payment_logger.info(
                "payment_processing_started",
                transaction_id=str(
                    payment_transaction.id
                ),
                transaction_number=(
                    payment_transaction.transaction_number
                ),
                current_status=current_status,
                phonepe_state=state,
            )

            # -----------------------------------------------------
            # Validate gateway order ID
            # -----------------------------------------------------

            if (
                payment_transaction.gateway_order_id
                and gateway_order_id
                and payment_transaction.gateway_order_id
                != gateway_order_id
            ):
                payment_logger.warning(
                    "phonepe_order_id_mismatch",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                    expected_gateway_order_id=(
                        payment_transaction.gateway_order_id
                    ),
                    received_gateway_order_id=(
                        gateway_order_id
                    ),
                )

                raise ValueError(
                    "Payment order mismatch."
                )

            # -----------------------------------------------------
            # IMPORTANT:
            #
            # If another process already completed the payment,
            # DO NOT update student fees again.
            # -----------------------------------------------------

            if (
                current_status
                == PaymentTransaction.Status.SUCCESS
            ):
                payment_logger.info(
                    "payment_already_processed",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                    transaction_number=(
                        payment_transaction.transaction_number
                    ),
                    source="webhook_or_verify",
                )

                return payment_transaction, False

            # -----------------------------------------------------
            # Do not allow a late callback to change a terminal
            # failure/cancellation.
            # -----------------------------------------------------

            if current_status in [
                PaymentTransaction.Status.FAILED,
                PaymentTransaction.Status.CANCELLED,
            ]:

                payment_logger.warning(
                    "payment_already_finalized",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                    current_status=current_status,
                    received_state=state,
                )

                return payment_transaction, False

            # -----------------------------------------------------
            # Store gateway transaction/order ID
            # -----------------------------------------------------

            if gateway_transaction_id:
                payment_transaction.gateway_transaction_id = (
                    gateway_transaction_id
                )

            elif gateway_order_id:
                payment_transaction.gateway_transaction_id = (
                    gateway_order_id
                )

            # =====================================================
            # COMPLETED
            # =====================================================

            if state == "COMPLETED":

                # -------------------------------------------------
                # This process won the race.
                # -------------------------------------------------

                payment_transaction.status = (
                    PaymentTransaction.Status.SUCCESS
                )

                payment_transaction.paid_at = timezone.now()

                payment_transaction.save(
                    update_fields=[
                        "status",
                        "gateway_transaction_id",
                        "paid_at",
                        "updated_at",
                    ]
                )

                # -------------------------------------------------
                # IMPORTANT:
                #
                # Fees are updated only here.
                #
                # Since PaymentTransaction is locked, another
                # webhook/verify request cannot execute this
                # section for the same transaction.
                # -------------------------------------------------

                self.update_student_fees(
                    payment_transaction
                )

                payment_logger.info(
                    "payment_completed",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                    student_id=str(
                        payment_transaction.student_id
                    ),
                    amount=str(
                        payment_transaction.amount
                    ),
                )

                return payment_transaction, True

            # =====================================================
            # FAILED
            # =====================================================

            elif state == "FAILED":

                payment_transaction.status = (
                    PaymentTransaction.Status.FAILED
                )

                payment_transaction.save(
                    update_fields=[
                        "status",
                        "gateway_transaction_id",
                        "updated_at",
                    ]
                )

                payment_logger.info(
                    "payment_failed",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                )

                return payment_transaction, False

            # =====================================================
            # PENDING
            # =====================================================

            elif state == "PENDING":

                payment_transaction.status = (
                    PaymentTransaction.Status.PENDING
                )

                payment_transaction.save(
                    update_fields=[
                        "status",
                        "gateway_transaction_id",
                        "updated_at",
                    ]
                )

                payment_logger.info(
                    "payment_pending",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                )

                return payment_transaction, False

            # =====================================================
            # CANCELLED / UNKNOWN
            # =====================================================

            else:

                payment_transaction.status = (
                    PaymentTransaction.Status.CANCELLED
                )

                payment_transaction.save(
                    update_fields=[
                        "status",
                        "gateway_transaction_id",
                        "updated_at",
                    ]
                )

                payment_logger.info(
                    "payment_cancelled",
                    transaction_id=str(
                        payment_transaction.id
                    ),
                    state=state,
                )

                return payment_transaction, False

    # =============================================================
    # UPDATE STUDENT FEES
    # =============================================================

    def update_student_fees(self, payment_transaction):

        payment_logger.info(
            "student_fee_update_started",
            transaction_id=str(
                payment_transaction.id
            ),
        )

        # ---------------------------------------------------------
        # Lock payment allocations
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # Lock student fee rows
        # ---------------------------------------------------------

        fee_ids = [
            item.student_fee_id
            for item in items
        ]

        locked_fees = {
            fee.id: fee
            for fee in (
                StudentFee.objects
                .select_for_update()
                .filter(
                    id__in=fee_ids,
                )
                .order_by("id")
            )
        }

        # ---------------------------------------------------------
        # Update allocated fees
        # ---------------------------------------------------------

        for item in items:

            fee = locked_fees.get(
                item.student_fee_id
            )

            if fee is None:
                raise ValueError(
                    f"Student fee {item.student_fee_id} not found."
                )

            previous_paid_amount = Decimal(
                str(fee.paid_amount or 0)
            )

            allocated_amount = Decimal(
                str(item.amount)
            )

            if allocated_amount <= Decimal("0.00"):
                raise ValueError(
                    "Payment allocation must be greater than zero."
                )

            # -----------------------------------------------------
            # Add payment amount
            # -----------------------------------------------------

            fee.paid_amount = (
                previous_paid_amount
                + allocated_amount
            )

            # -----------------------------------------------------
            # Calculate payable amount
            # -----------------------------------------------------

            payable_amount = (
                Decimal(str(fee.total_amount))
                - Decimal(
                    str(fee.concession_amount or 0)
                )
                + Decimal(
                    str(fee.late_fee or 0)
                )
            )

            # -----------------------------------------------------
            # Update fee status
            # -----------------------------------------------------

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
                ]
            )

            payment_logger.info(
                "student_fee_updated",
                transaction_id=str(
                    payment_transaction.id
                ),
                student_fee_id=str(
                    fee.id
                ),
                previous_paid_amount=str(
                    previous_paid_amount
                ),
                allocated_amount=str(
                    allocated_amount
                ),
                current_paid_amount=str(
                    fee.paid_amount
                ),
                status=fee.status,
            )

        # =========================================================
        # UPDATE STUDENT FEE SUMMARY
        # =========================================================

        student = payment_transaction.student
        academic_year = student.academic_year

        totals = (
            StudentFee.objects
            .filter(
                school=payment_transaction.school,
                student=student,
            )
            .filter(
                Q(
                    fee_template__academic_year=academic_year
                )
                | Q(
                    transport_fee_rule__academic_year=academic_year
                )
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

        total_fee = (
            totals["total_fee"]
            or Decimal("0.00")
        )

        total_concession = (
            totals["total_concession"]
            or Decimal("0.00")
        )

        total_late_fee = (
            totals["total_late_fee"]
            or Decimal("0.00")
        )

        total_paid = (
            totals["total_paid"]
            or Decimal("0.00")
        )

        outstanding_amount = (
            total_fee
            - total_concession
            + total_late_fee
            - total_paid
        )

        summary, _ = (
            StudentFeeSummary.objects.update_or_create(
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
        )

        payment_logger.info(
            "student_fee_summary_updated",
            transaction_id=str(
                payment_transaction.id
            ),
            student_id=str(student.id),
            summary_id=str(summary.id),
            total_fee=str(summary.total_fee),
            total_concession=str(
                summary.total_concession
            ),
            total_paid=str(summary.total_paid),
            outstanding_amount=str(
                summary.outstanding_amount
            ),
        )

        payment_logger.info(
            "student_fee_update_completed",
            transaction_id=str(
                payment_transaction.id
            ),
        )









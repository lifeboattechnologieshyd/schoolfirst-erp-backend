from django.db.models import Sum

from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment, FeeTemplateItem, FeeConcession, \
    StudentFeeSummary
from shared.utils.calendar import create_calendar_event

from django.db import transaction



from decimal import Decimal, ROUND_HALF_UP

from shared.utils.logger import application_logger


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
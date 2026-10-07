from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment, FeeTemplateItem, FeeConcession
from shared.utils.calendar import create_calendar_event




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
                str(concession.id)
                if concession
                else None
            ),
        },
    )

    try:
        fee_items = list(
            FeeTemplateItem.objects
            .select_related("fee_type")
            .filter(
                fee_template=fee_template,
            )
        )

        if not fee_items:
            application_logger.warning(
                "student_fee_generation_no_fee_items",
                extra={
                    "student_id": str(student.id),
                    "school_id": str(student.school_id),
                    "fee_template_id": str(fee_template.id),
                },
            )

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
            application_logger.warning(
                "student_fee_generation_invalid_total",
                extra={
                    "student_id": str(student.id),
                    "school_id": str(student.school_id),
                    "fee_template_id": str(fee_template.id),
                    "total_fee": str(total_fee),
                },
            )

            raise ValueError(
                "Total fee amount must be greater than zero."
            )

        # ---------------------------------------------------------
        # Calculate total concession
        # ---------------------------------------------------------

        total_concession = Decimal("0.00")

        if concession:
            if (
                concession.concession_type
                == FeeConcession.Type.FLAT
            ):
                total_concession = concession.value

            elif (
                concession.concession_type
                == FeeConcession.Type.PERCENTAGE
            ):
                total_concession = (
                    total_fee * concession.value
                ) / Decimal("100")

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
                "concession_id": (
                    str(concession.id)
                    if concession
                    else None
                ),
                "concession_type": (
                    concession.concession_type
                    if concession
                    else None
                ),
                "total_concession": str(total_concession),
            },
        )

        # ---------------------------------------------------------
        # Create StudentFee records
        # ---------------------------------------------------------

        student_fees = []
        allocated_concession = Decimal("0.00")

        for index, item in enumerate(fee_items):

            if index == len(fee_items) - 1:
                item_concession = (
                    total_concession
                    - allocated_concession
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
        # Save StudentFee records
        # ---------------------------------------------------------

        StudentFee.objects.bulk_create(
            student_fees,
            ignore_conflicts=True,
        )

        application_logger.info(
            "student_fee_generation_completed",
            extra={
                "student_id": str(student.id),
                "school_id": str(student.school_id),
                "fee_template_id": str(fee_template.id),
                "fee_count": len(student_fees),
                "total_fee": str(total_fee),
                "total_concession": str(total_concession),
                "total_payable": str(
                    total_fee - total_concession
                ),
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
                    str(concession.id)
                    if concession
                    else None
                ),
                "error": str(e),
            },
        )

        raise
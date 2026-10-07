from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment, FeeTemplateItem, FeeConcession
from shared.utils.calendar import create_calendar_event




from decimal import Decimal, ROUND_HALF_UP


def generate_student_fees(
    *,
    student,
    fee_template,
    concession=None,
):
    fee_items = list(
        FeeTemplateItem.objects
        .select_related("fee_type")
        .filter(
            fee_template=fee_template,
        )
    )

    if not fee_items:
        raise ValueError(
            f"No fee items configured for fee template "
            f"'{fee_template.name}'."
        )

    # ---------------------------------------------------------
    # 1. Calculate total fee
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
    # 2. Calculate total concession
    # ---------------------------------------------------------

    total_concession = Decimal("0.00")

    if concession:
        if concession.concession_type == FeeConcession.Type.FLAT:

            total_concession = concession.value

        elif concession.concession_type == FeeConcession.Type.PERCENTAGE:

            total_concession = (
                total_fee * concession.value
            ) / Decimal("100")

        # Concession cannot exceed total fee
        total_concession = min(
            total_concession,
            total_fee,
        )

    # ---------------------------------------------------------
    # 3. Create StudentFee records
    # ---------------------------------------------------------

    student_fees = []

    allocated_concession = Decimal("0.00")

    for index, item in enumerate(fee_items):

        # -----------------------------------------------------
        # Proportionate concession
        # -----------------------------------------------------

        if index == len(fee_items) - 1:
            # Give rounding difference to the last item
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

        allocated_concession += item_concession

        # Safety
        item_concession = min(
            item_concession,
            item.amount,
        )

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
    # 4. Bulk create
    # ---------------------------------------------------------

    StudentFee.objects.bulk_create(
        student_fees,
        ignore_conflicts=True,
    )

    return student_fees
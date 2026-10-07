from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment, FeeTemplateItem, FeeConcession
from shared.utils.calendar import create_calendar_event




from decimal import Decimal


def generate_student_fees(
    *,
    student,
    fee_template,
    concession=None,
):
    fee_items = (
        FeeTemplateItem.objects
        .select_related("fee_type")
        .filter(
            fee_template=fee_template,
        )
    )

    student_fees = []

    for item in fee_items:
        total_amount = item.amount
        concession_amount = Decimal("0.00")

        if concession:
            if concession.concession_type == FeeConcession.Type.FLAT:
                concession_amount = concession.value

            elif concession.concession_type == FeeConcession.Type.PERCENTAGE:
                concession_amount = (
                    total_amount * concession.value
                ) / Decimal("100")

            # Never allow concession greater than fee amount
            concession_amount = min(
                concession_amount,
                total_amount,
            )

        student_fees.append(
            StudentFee(
                school=student.school,
                student=student,
                fee_template=fee_template,
                fee_type=item.fee_type,
                concession=concession,
                total_amount=total_amount,
                concession_amount=concession_amount,
                late_fee=Decimal("0.00"),
                paid_amount=Decimal("0.00"),
                due_date=None,
                status=StudentFee.Status.PENDING,
            )
        )

    StudentFee.objects.bulk_create(
        student_fees,
        ignore_conflicts=True,
    )

    return student_fees
from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment, FeeTemplateItem
from shared.utils.calendar import create_calendar_event


def generate_student_fees(
    *,
    student,
    fee_template,
):
    fee_template_items = (
        FeeTemplateItem.objects
        .select_related("fee_type")
        .filter(
            fee_template=fee_template,
        )
    )

    student_fees = []

    for item in fee_template_items:
        student_fees.append(
            StudentFee(
                student=student,
                fee_template_item=item,
                due_date=None,
                amount=item.amount,
            )
        )

    StudentFee.objects.bulk_create(
        student_fees,
        ignore_conflicts=True,
    )

    student_fees = (
        StudentFee.objects
        .filter(
            student=student,
            fee_template_item__fee_template=fee_template,
        )
        .select_related(
            "fee_template_item__fee_type",
        )
    )

    for student_fee in student_fees:
        if CalendarEvent.objects.filter(
            event_type=CalendarEvent.EventType.FEE,
            reference_id=student_fee.id,
        ).exists():
            continue

        create_calendar_event(
            school=student.school,
            title=(
                f"{student_fee.fee_template_item.fee_type.name} Fee Due"
            ),
            description="",
            event_type=CalendarEvent.EventType.FEE,
            event_date=student_fee.due_date,
            reference_id=student_fee.id,
            target_type=CalendarEventTarget.TargetType.STUDENT,
            students=[student],
        )

    return student_fees


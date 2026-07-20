from apps.calendar.models import CalendarEvent, CalendarEventTarget
from apps.fee.models import FeeInstallmentItem, StudentFee, StudentFeeAssignment
from shared.utils.calendar import create_calendar_event


def generate_student_fees(
    *,
    student,
    fee_template,
    assigned_by=None,
):

    assignment, _ = StudentFeeAssignment.objects.get_or_create(
        student=student,
        fee_template=fee_template,
        defaults={
            "assigned_by": assigned_by,
        },
    )

    installment_items = FeeInstallmentItem.objects.select_related(
        "installment",
        "fee_template_item",
    ).filter(
        installment__collection_plan__fee_template=fee_template,
    )

    student_fees = []

    for item in installment_items:

        student_fees.append(
            StudentFee(
                student=student,
                installment_item=item,
                due_date=item.installment.due_date,
                amount=item.amount,
            )
        )

    StudentFee.objects.bulk_create(
        student_fees,
        ignore_conflicts=True,
    )

    student_fees = StudentFee.objects.filter(
        student=student,
        installment_item__in=[
            item.installment_item
            for item in student_fees
        ],
    ).select_related(
        "installment_item__fee_template_item__fee_type",
    )

    for student_fee in student_fees:
        if CalendarEvent.objects.filter(
                event_type=CalendarEvent.EventType.FEE,
                reference_id=student_fee.id,
        ).exists():
            continue

        create_calendar_event(
            school=student.school,
            title=f"{student_fee.installment_item.fee_template_item.fee_type.name} Fee Due",
            description="",
            event_type=CalendarEvent.EventType.FEE,
            event_date=student_fee.due_date,
            reference_id=student_fee.id,
            target_type=CalendarEventTarget.TargetType.STUDENT,
            students=[student],
        )

    return assignment


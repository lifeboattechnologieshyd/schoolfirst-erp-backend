from apps.fee.models import FeeInstallmentItem, StudentFee


def generate_student_fees(
    student,
    fee_template,
):

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
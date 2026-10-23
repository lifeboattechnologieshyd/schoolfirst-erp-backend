from django.utils import timezone

from apps.examination.models import ExaminationGrade, HallTicket
from apps.school.models.school import Student


@staticmethod
def generate_hall_tickets(examination):
    examination_grades = ExaminationGrade.objects.filter(
        examination=examination
    ).select_related("grade")

    generated_count = 0

    for examination_grade in examination_grades:

        students = Student.objects.filter(
            school=examination.school,
            grade=examination_grade.grade,
            status=Student.Status.ACTIVE,
        )

        for student in students:

            hall_ticket, created = HallTicket.objects.get_or_create(
                examination=examination,
                student=student,
                defaults={
                    "hall_ticket_number": generate_hall_ticket_number(
                        examination
                    ),
                    "status": HallTicket.Status.GENERATED,
                    "generated_at": timezone.now(),
                },
            )

            if created:
                generated_count += 1

    return generated_count
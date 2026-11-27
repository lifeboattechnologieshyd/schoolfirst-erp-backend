import uuid

from django.db.models import Q

from apps.school.models.school import Student


def get_family_zone_grade(student):
    grade = student.grade
    standard_grade = grade.standard_grade if grade else None
    if not standard_grade or standard_grade.is_deleted or not standard_grade.is_active:
        return None
    return standard_grade

def parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None

def get_kid(kid_id, user):
    """
    Family Zone kid = school Student linked to this parent by mobile.
    The app passes the student id from verify OTP as kid_id.
    """
    kid_uuid = parse_uuid(kid_id)

    if kid_uuid is None or not user.mobile:
        return None

    mobile = str(user.mobile)

    return Student.objects.filter(
        Q(father_mobile=mobile)
        | Q(mother_mobile=mobile)
        | Q(guardian_mobile=mobile),
        id=kid_uuid,
        status=Student.Status.ACTIVE,
    ).select_related(
        "grade",
        "grade__standard_grade",
    ).first()

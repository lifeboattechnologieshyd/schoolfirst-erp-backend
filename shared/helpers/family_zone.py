def get_family_zone_grade(student):
    grade = student.grade
    standard_grade = grade.standard_grade if grade else None
    if not standard_grade or standard_grade.is_deleted or not standard_grade.is_active:
        return None
    return standard_grade
def get_family_zone_grade(student):
    grade = student.grade
    return grade.standard_grade if grade else None
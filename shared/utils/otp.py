import secrets

from apps.school.models import School


# def generate_otp(digits=4):
#     if digits < 1:
#         raise ValueError("Digits must be at least 1")
#     otp = secrets.randbelow(10**digits - 10 ** (digits - 1)) + 10 ** (digits - 1)
#     return otp


import random
import string

def generate_school_code():
    while True:
        code = "SCH" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )

        if not School.objects.filter(code=code).exists():
            return code
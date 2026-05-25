import secrets


def generate_otp(digits=4):
    if digits < 1:
        raise ValueError("Digits must be at least 1")
    otp = secrets.randbelow(10**digits - 10 ** (digits - 1)) + 10 ** (digits - 1)
    return otp

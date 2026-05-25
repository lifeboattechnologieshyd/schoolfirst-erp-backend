"""
OTP helper functions for creating, sending, and verifying OTPs.
"""

import structlog

from shared.enums import OTPPurpose

logger = structlog.get_logger("default")


# OTP expiry configuration per purpose
OTP_EXPIRY_MINUTES: dict[str, int] = {
    OTPPurpose.EMAIL_VERIFICATION: 10,
    OTPPurpose.PASSWORD_RESET: 15,
    OTPPurpose.LOGIN_FALLBACK: 5,
}


def log_otp_to_console(email: str, mobile: str | None, otp: str, purpose: str) -> None:
    """
    Log OTP to console (fake email/SMS sending).
    Used until real email provider is configured.

    Args:
        email: Email address to send to
        mobile: Mobile number to send to (optional)
        otp: The OTP code
        purpose: Purpose of the OTP
    """
    recipient = email or mobile
    logger.info(
        "=" * 70,
    )
    logger.info(
        f"📧 OTP EMAIL (FAKE) - {purpose}",
        recipient=recipient,
        otp=otp,
        purpose=purpose,
    )
    logger.info(
        "=" * 70,
    )
    logger.info(
        f"To: {recipient}",
    )
    logger.info(
        f"Subject: Your OTP Code - {purpose}",
    )
    logger.info(
        "",
    )
    logger.info(
        f"Your verification code is: {otp}",
    )
    logger.info(
        f"This code will expire in {OTP_EXPIRY_MINUTES.get(purpose, 10)} minutes.",
    )
    logger.info(
        "=" * 70,
    )


# def create_otp(
#     email: str | None = None,
#     mobile: str | None = None,
#     user_id: str | None = None,
#     purpose: str = OTPPurpose.EMAIL_VERIFICATION,
#     device_id: str | None = None,
#     country_code: str | None = None,
#     digits: int = 6,
# ) -> OTP:
#     """
#     Create a new OTP with purpose-based expiry time.
#
#     Args:
#         email: Email address
#         mobile: Mobile number
#         user_id: User ID (optional, nullable for new users)
#         purpose: Purpose of OTP (affects expiry time)
#         device_id: Device identifier
#         country_code: Country code for mobile
#         digits: Number of OTP digits (default: 6)
#
#     Returns:
#         OTP object
#
#     Raises:
#         ValueError: If neither email nor mobile is provided
#     """
#     if not email and not mobile:
#         raise ValueError("Either email or mobile must be provided")
#
#     # Generate OTP code
#     otp_code = str(generate_otp(digits=digits))
#
#     # Calculate expiry time based on purpose
#     expiry_minutes = OTP_EXPIRY_MINUTES.get(purpose, 10)
#     expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
#
#     # Create OTP record
#     otp_obj = OTP.objects.create(
#         user_id=user_id,
#         email=email,
#         mobile=mobile,
#         otp=otp_code,
#         purpose=purpose,
#         expires_at=expires_at,
#         device_id=device_id,
#         country_code=country_code,
#         retry_count=0,
#         is_used=False,
#     )
#
#     # Log OTP to console (fake email)
#     log_otp_to_console(email, mobile, otp_code, purpose)
#
#     logger.info(
#         "OTP created successfully",
#         otp_id=str(otp_obj.id),
#         email=email,
#         mobile=mobile,
#         purpose=purpose,
#         expires_at=expires_at.isoformat(),
#     )
#
#     return otp_obj


# def verify_otp(
#     email: str | None = None,
#     mobile: str | None = None,
#     otp: str = None,
#     purpose: str = OTPPurpose.EMAIL_VERIFICATION,
# ) -> tuple[bool, str, OTP | None]:
#     """
#     Verify OTP with retry count protection.
#
#     Args:
#         email: Email address
#         mobile: Mobile number
#         otp: OTP code to verify
#         purpose: Purpose of OTP
#
#     Returns:
#         Tuple of (is_valid, error_message, otp_object)
#
#     Example:
#         is_valid, error_msg, otp_obj = verify_otp(
#             email="user@example.com",
#             otp="123456",
#             purpose=OTPPurpose.EMAIL_VERIFICATION,
#         )
#         if is_valid:
#             # OTP is valid, proceed
#             otp_obj.is_used = True
#             otp_obj.save()
#     """
#     if not email and not mobile:
#         return (False, "Either email or mobile must be provided", None)
#
#     if not otp:
#         return (False, "OTP is required", None)
#
#     # Find the most recent OTP for this identifier and purpose
#     query = OTP.objects.filter(purpose=purpose, is_used=False)
#
#     if email:
#         query = query.filter(email=email)
#     else:
#         query = query.filter(mobile=mobile)
#
#     otp_obj = query.order_by("-created_at").first()
#
#     if not otp_obj:
#         logger.warning(
#             "OTP not found",
#             email=email,
#             mobile=mobile,
#             purpose=purpose,
#         )
#         return (False, "Invalid OTP or OTP not found", None)
#
#     # Check if OTP has expired
#     if timezone.now() > otp_obj.expires_at:
#         logger.warning(
#             "OTP has expired",
#             otp_id=str(otp_obj.id),
#             expires_at=otp_obj.expires_at.isoformat(),
#         )
#         return (False, "OTP has expired", otp_obj)
#
#     # Check retry count
#     if otp_obj.retry_count >= 10:
#         logger.warning(
#             "OTP retry limit exceeded",
#             otp_id=str(otp_obj.id),
#             retry_count=otp_obj.retry_count,
#         )
#         return (False, "Too many failed attempts. Please request a new OTP", otp_obj)
#
#     # Verify OTP code
#     if otp_obj.otp != otp:
#         # Increment retry count
#         otp_obj.retry_count += 1
#         otp_obj.save(update_fields=["retry_count", "updated_at"])
#
#         logger.warning(
#             "Invalid OTP code",
#             otp_id=str(otp_obj.id),
#             retry_count=otp_obj.retry_count,
#         )
#         return (
#             False,
#             f"Invalid OTP. {10 - otp_obj.retry_count} attempts remaining",
#             otp_obj,
#         )
#
#     # OTP is valid
#     logger.info(
#         "OTP verified successfully",
#         otp_id=str(otp_obj.id),
#         email=email,
#         mobile=mobile,
#         purpose=purpose,
#     )
#
#     return True, "", otp_obj


# def invalidate_previous_otps(
#     email: str | None = None,
#     mobile: str | None = None,
#     purpose: str = OTPPurpose.EMAIL_VERIFICATION,
# ) -> int:
#     """
#     Mark all previous OTPs as used for security.
#     Useful when generating a new OTP to invalidate old ones.
#
#     Args:
#         email: Email address
#         mobile: Mobile number
#         purpose: Purpose of OTP
#
#     Returns:
#         Number of OTPs invalidated
#     """
#     query = OTP.objects.filter(purpose=purpose, is_used=False)
#
#     if email:
#         query = query.filter(email=email)
#     elif mobile:
#         query = query.filter(mobile=mobile)
#     else:
#         return 0
#
#     count = query.update(is_used=True)
#
#     logger.info(
#         "Invalidated previous OTPs",
#         count=count,
#         email=email,
#         mobile=mobile,
#         purpose=purpose,
#     )
#
#     return count

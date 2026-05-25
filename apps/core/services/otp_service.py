from datetime import timedelta

import structlog
from django.conf import settings
from django.utils.timezone import now

from apps.core.models.user import OTP
from shared.utils.otp import generate_otp

logger = structlog.get_logger("default")

MAX_OTP_RETRIES = 5
_OTP_EXPIRY_MINUTES = 10
_OTP_COOLDOWN_SECONDS = 60
_OTP_MAX_PER_HOUR = 5


class OTPNotFoundError(Exception):
    """No active (unused) OTP record exists for the given email and purpose."""


class OTPExpiredError(Exception):
    """The OTP record exists but its expiry time has passed."""


class MaxRetriesExceededError(Exception):
    """The OTP has been attempted too many times and cannot be retried."""


class OTPInvalidError(Exception):
    """The supplied value does not match the stored OTP."""

    def __init__(self, attempts_remaining: int) -> None:
        self.attempts_remaining = attempts_remaining
        super().__init__(f"Invalid OTP. {attempts_remaining} attempts remaining.")


class OTPCooldownError(Exception):
    """A new OTP was requested too soon after the previous one."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Please wait {retry_after} seconds before requesting a new OTP.")


class OTPRateLimitError(Exception):
    """Too many OTPs have been requested for this email within the last hour."""


class OTPService:
    @staticmethod
    def create(email: str, purpose: str, length: int = 6) -> OTP:
        """Create and persist a new OTP for the given email and purpose."""
        if not settings.DEBUG:
            one_hour_ago = now() - timedelta(hours=1)

            latest = OTP.objects.filter(email=email, purpose=purpose).order_by("-created_at").first()
            if latest is not None:
                elapsed = (now() - latest.created_at).total_seconds()
                if elapsed < _OTP_COOLDOWN_SECONDS:
                    raise OTPCooldownError(retry_after=int(_OTP_COOLDOWN_SECONDS - elapsed))

            hourly_count = OTP.objects.filter(email=email, purpose=purpose, created_at__gte=one_hour_ago).count()
            if hourly_count >= _OTP_MAX_PER_HOUR:
                raise OTPRateLimitError()

        if settings.DEBUG:
            otp_value = "".join(str((i + 1) % 10) for i in range(length))
        else:
            otp_value = str(generate_otp(digits=length))

        return OTP.objects.create(
            email=email,
            otp=otp_value,
            purpose=purpose,
            expires_at=now() + timedelta(minutes=_OTP_EXPIRY_MINUTES),
        )

    @staticmethod
    def verify(email: str, purpose: str, otp_input: str) -> OTP:
        """
        Verify an OTP. Marks it as used on success.

        Raises:
            OTPNotFound        — no unused OTP for this email + purpose
            MaxRetriesExceeded — retry count exhausted
            OTPExpired         — OTP has passed its expiry time
            OTPInvalid         — wrong value; retry count incremented before raising
        """
        otp_obj = OTP.objects.filter(email=email, purpose=purpose, is_used=False).order_by("-created_at").first()
        if not otp_obj:
            raise OTPNotFoundError()

        if otp_obj.retry_count >= MAX_OTP_RETRIES:
            raise MaxRetriesExceededError()

        if otp_obj.expires_at < now():
            raise OTPExpiredError()

        if otp_obj.otp != otp_input:
            otp_obj.retry_count += 1
            otp_obj.save(update_fields=["retry_count"])
            raise OTPInvalidError(attempts_remaining=MAX_OTP_RETRIES - otp_obj.retry_count)

        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])
        return otp_obj

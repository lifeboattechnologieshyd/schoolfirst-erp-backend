from dataclasses import dataclass
from datetime import timedelta

import structlog
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import InvitationCode, SignupSession, UserMaster
from apps.core.services.otp_service import OTPService
from apps.core.services.post_signup_service import PostSignupService
from shared.enums import InviteCodeType, OTPPurpose
from shared.helpers.email import send_otp_email, send_password_reset_email

logger = structlog.get_logger("default")

_SESSION_EXPIRY_MINUTES = 10


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class AuthenticatedUserTokens:
    user: UserMaster
    tokens: TokenPair


class UserAlreadyRegisteredError(Exception):
    """A UserMaster record already exists for this email."""


class InvalidInviteCodeError(Exception):
    """The invite code does not exist or is no longer active."""


class InviteEmailMismatchError(Exception):
    """A targeted invite code was supplied but the email does not match."""


class SignupSessionExpiredError(Exception):
    """The SignupSession has expired or does not exist for this email/code."""


class AuthService:
    @staticmethod
    def issue_tokens(user: UserMaster) -> TokenPair:
        refresh = RefreshToken.for_user(user)
        return TokenPair(
            access_token=str(refresh.access_token),
            refresh_token=str(refresh),
        )

    @staticmethod
    def initiate_signup(email: str, invite_code: str) -> None:
        """
        Step 1 of signup: validate invite code, create OTP + session, send email.

        Raises:
            UserAlreadyRegisteredError
            InvalidInviteCodeError
            InviteEmailMismatchError
        """
        if UserMaster.objects.filter(email=email).exists():
            raise UserAlreadyRegisteredError()

        valid_code = InvitationCode.objects.filter(code=invite_code, is_active=True).first()
        if not valid_code:
            raise InvalidInviteCodeError()

        if valid_code.code_type == InviteCodeType.TARGETED and valid_code.target_email.lower() != email.lower():
            raise InviteEmailMismatchError()

        otp_obj = OTPService.create(email=email, purpose=OTPPurpose.EMAIL_VERIFICATION)
        SignupSession.objects.create(
            email=email,
            invite_code=valid_code.code,
            expires_at=timezone.now() + timedelta(minutes=_SESSION_EXPIRY_MINUTES),
        )
        send_otp_email(to_email=email, otp=otp_obj.otp)

    @staticmethod
    @transaction.atomic
    def complete_signup(email: str, otp_input: str, invite_code: str) -> AuthenticatedUserTokens:
        """
        Step 2 of signup: verify OTP, create account, resolve pending invites.

        Returns the created user and issued token pair.

        Raises:
            UserAlreadyRegisteredError
            SignupSessionExpiredError
            OTPNotFoundError, OTPExpiredError, OTPInvalidError, MaxRetriesExceededError
        """
        if UserMaster.objects.filter(email=email).exists():
            raise UserAlreadyRegisteredError()

        OTPService.verify(email=email, purpose=OTPPurpose.EMAIL_VERIFICATION, otp_input=otp_input)

        session = SignupSession.objects.filter(invite_code=invite_code, email=email).first()
        if not session or session.expires_at < timezone.now():
            raise SignupSessionExpiredError()

        invite = session.invite_code
        user = UserMaster.objects.create_user(email=email, signup_invite_code=invite)
        PostSignupService.resolve_pending_invites(email=email, user=user)
        InvitationCode.objects.filter(code=invite, code_type=InviteCodeType.TARGETED).update(is_active=False)

        return AuthenticatedUserTokens(user=user, tokens=AuthService.issue_tokens(user))

    @staticmethod
    def initiate_password_reset(email: str) -> bool:
        """
        Step 1 of password reset: send OTP if an account exists for this email.

        Returns True if the email was sent, False if the user was not found.
        The caller should not reveal which case occurred.
        """
        user = UserMaster.objects.filter(email=email).first()
        if not user:
            return False

        otp_obj = OTPService.create(email=email, purpose=OTPPurpose.PASSWORD_RESET)
        send_password_reset_email(to_email=email, otp=otp_obj.otp)
        return True

    @staticmethod
    def verify_password_reset(email: str, otp_input: str) -> AuthenticatedUserTokens:
        """
        Step 2 of password reset: verify OTP and return tokens.

        Returns the authenticated user and issued token pair.

        Raises:
            OTPNotFoundError, OTPExpiredError, OTPInvalidError, MaxRetriesExceededError
        """
        OTPService.verify(email=email, purpose=OTPPurpose.PASSWORD_RESET, otp_input=otp_input)

        user = UserMaster.objects.filter(email=email).first()
        if user is None:
            raise RuntimeError(f"Password reset user not found for email {email}")

        return AuthenticatedUserTokens(user=user, tokens=AuthService.issue_tokens(user))

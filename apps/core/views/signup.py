"""
Signup views with invitation code validation.
"""

from typing import Any

import structlog
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.models.user import UserMaster
from apps.core.serializers.user import UserProfileSerializer
from apps.core.services.auth_service import (
    AuthService,
    InvalidInviteCodeError,
    InviteEmailMismatchError,
    SignupSessionExpiredError,
    UserAlreadyRegisteredError,
)
from apps.core.services.otp_service import (
    MaxRetriesExceededError,
    OTPCooldownError,
    OTPExpiredError,
    OTPInvalidError,
    OTPNotFoundError,
    OTPRateLimitError,
)
from shared.mixins.drf_views import CustomResponse

logger = structlog.get_logger("default")


class InviteCodeValidateView(APIView, CustomResponse):
    """
    Validate an invitation code before signup.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        invite_code = request.data.get("invite_code")
        if not email or not invite_code:
            return self.build_response(
                success=False,
                message="Email and invite code are required.",
                error={"code": "REQUIRED", "message": "Email and invite code are required."},
                status=400,
            )

        try:
            AuthService.initiate_signup(email=email, invite_code=invite_code)
        except UserAlreadyRegisteredError:
            return self.build_response(
                success=False,
                message="User already registered.",
                error={"code": "ALREADY_REGISTERED", "message": "User already registered."},
                status=400,
            )
        except InvalidInviteCodeError:
            return self.build_response(
                success=False,
                message="Invalid invite code.",
                error={"code": "INVALID_CODE", "message": "Invalid invite code."},
                status=400,
            )
        except InviteEmailMismatchError:
            return self.build_response(
                success=False,
                message="Invite not valid for this email.",
                error={"code": "INVALID_EMAIL", "message": "Invite not valid for this email."},
                status=400,
            )
        except OTPCooldownError as e:
            return self.build_response(
                success=False,
                message=f"You already have a pending OTP. Please try again in {e.retry_after} seconds.",
                error={
                    "code": "OTP_COOLDOWN",
                    "message": f"Please try again in {e.retry_after} seconds.",
                    "retry_after": e.retry_after,
                },
                status=429,
            )
        except OTPRateLimitError:
            return self.build_response(
                success=False,
                message="Too many OTP requests. Please try again after 1 hour.",
                error={
                    "code": "OTP_RATE_LIMIT",
                    "message": "Too many OTP requests. Please try again after 1 hour.",
                },
                status=429,
            )
        return self.build_response(success=True, message="OTP sent successfully.", status=200)


class EmailVerifyView(APIView, CustomResponse):
    """
    Step 2 (and final) of signup: verify OTP → create account → return JWT.
    Use POST /api/v1/auth/set-password/ to set the password after signup.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        otp_input = request.data.get("otp")
        invite_code = request.data.get("invite_code")

        if not email or not otp_input or not invite_code:
            return self.build_response(
                success=False,
                message="Email, OTP and invite code are required.",
                error={"code": "REQUIRED", "message": "Email, OTP and invite code are required."},
                status=400,
            )

        try:
            signup_result = AuthService.complete_signup(email=email, otp_input=otp_input, invite_code=invite_code)
        except UserAlreadyRegisteredError:
            return self.build_response(
                success=False,
                message="User already registered.",
                error={"code": "ALREADY_REGISTERED", "message": "User already registered."},
                status=400,
            )
        except OTPNotFoundError:
            return self.build_response(
                success=False,
                message="No active OTP found for this email.",
                error={"code": "INVALID_OTP", "message": "No active OTP found for this email."},
                status=400,
            )
        except MaxRetriesExceededError:
            return self.build_response(
                success=False,
                message="Too many failed attempts. Please request a new OTP.",
                error={"code": "TOO_MANY_RETRIES", "message": "Too many failed attempts."},
                status=400,
            )
        except OTPExpiredError:
            return self.build_response(
                success=False,
                message="OTP expired.",
                error={"code": "OTP_EXPIRED", "message": "OTP expired."},
                status=400,
            )
        except OTPInvalidError as e:
            return self.build_response(
                success=False,
                message=f"Invalid OTP. {e.attempts_remaining} attempts remaining.",
                error={"code": "INVALID_OTP", "message": "Invalid OTP."},
                status=400,
            )
        except SignupSessionExpiredError:
            return self.build_response(
                success=False,
                message="Signup request expired. Please restart signup.",
                error={"code": "SESSION_EXPIRED", "message": "Signup request expired."},
                status=400,
            )
        except Exception:
            logger.exception("Account creation failed", email=email)
            return self.build_response(
                success=False,
                message="Something went wrong while creating account.",
                error={"code": "SERVER_ERROR", "message": "Something went wrong while creating account."},
                status=500,
            )

        return self.build_response(
            success=True,
            data={
                "access_token": signup_result.tokens.access_token,
                "refresh_token": signup_result.tokens.refresh_token,
                "user": UserProfileSerializer(signup_result.user).data,
            },
            message="Account created successfully.",
            status=201,
        )


class SetPasswordView(APIView, CustomResponse):
    """
    Set or change the authenticated user's password.
    Used after signup (email verify) or after password-reset OTP verification.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        if request.user.is_password_updated:
            return self.build_response(
                success=False,
                message="Password has already been set.",
                error={"code": "PASSWORD_ALREADY_SET", "message": "Password has already been set."},
                status=403,
            )
        password = request.data.get("password")
        if not password:
            return self.build_response(
                success=False,
                message="Password is required.",
                error={"code": "REQUIRED", "message": "Password is required."},
                status=400,
            )
        request.user.set_password(password)
        request.user.is_password_updated = True
        request.user.save(update_fields=["password", "is_password_updated"])
        return self.build_response(
            success=True,
            message="Password set successfully.",
            status=200,
        )


class LoginView(APIView, CustomResponse):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return self.build_response(
                success=False,
                message="Email and password are required.",
                error={"code": "REQUIRED", "message": "Email and password are required."},
                status=200,
            )

        # Since you're using custom user model
        user = UserMaster.objects.filter(email=email).first()

        if not user:
            return self.build_response(
                success=False,
                message="Invalid credentials.",
                error={"code": "INVALID_CREDENTIALS", "message": "Invalid credentials."},
                status=200,
            )

        if not user.is_active:
            return self.build_response(
                success=False,
                message="Account is inactive.",
                error={"code": "INACTIVE_ACCOUNT", "message": "Account is inactive."},
                status=200,
            )

        # 🔐 Check password (secure hash comparison)
        if not user.check_password(password):
            return self.build_response(
                success=False,
                message="Invalid credentials.",
                error={"code": "INVALID_CREDENTIALS", "message": "Invalid credentials."},
                status=200,
            )

        # ✅ Generate JWT
        token_pair = AuthService.issue_tokens(user)

        return self.build_response(
            success=True,
            message="Logged in successfully.",
            data={
                "access_token": token_pair.access_token,
                "refresh_token": token_pair.refresh_token,
                "user": UserProfileSerializer(user).data,
            },
            status=200,
        )


class CustomTokenRefreshView(TokenRefreshView, CustomResponse):
    permission_classes = [AllowAny]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Support both 'refresh' (standard) and 'refresh_token' (test)
        refresh_token = request.data.get("refresh_token") or request.data.get("refresh")

        if not refresh_token:
            return self.build_response(
                success=False,
                message="Refresh token is required.",
                error={"code": "REQUIRED", "message": "Refresh token is required."},
                status=200,
            )

        # Map back to 'refresh' for the base class if needed
        # Or just handle it here
        try:
            refresh = RefreshToken(refresh_token)
            data = {"access": str(refresh.access_token), "refresh": str(refresh)}
            return self.build_response(success=True, data=data, message="Token refreshed successfully.")
        except (TokenError, InvalidToken) as e:
            return self.build_response(
                success=False, message=str(e), error={"code": "INVALID_TOKEN", "message": str(e)}, status=200
            )


class PasswordResetRequestView(APIView, CustomResponse):
    """
    Step 1 of password reset: send a 6-digit OTP to the user's email.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        if not email:
            return self.build_response(
                success=False,
                message="Email is required.",
                error={"code": "REQUIRED", "message": "Email is required."},
                status=400,
            )

        try:
            AuthService.initiate_password_reset(email=email)
        except OTPCooldownError as e:
            return self.build_response(
                success=False,
                message=f"A reset code was already sent. Please try again in {e.retry_after} seconds.",
                error={
                    "code": "OTP_COOLDOWN",
                    "message": f"Please try again in {e.retry_after} seconds.",
                    "retry_after": e.retry_after,
                },
                status=429,
            )
        except OTPRateLimitError:
            return self.build_response(
                success=False,
                message="Too many reset code requests. Please try again after 1 hour.",
                error={
                    "code": "OTP_RATE_LIMIT",
                    "message": "Too many reset code requests. Please try again after 1 hour.",
                },
                status=429,
            )
        return self.build_response(
            success=True,
            message="If that email is registered, a reset code has been sent.",
            status=200,
        )


class PasswordResetVerifyView(APIView, CustomResponse):
    """
    Step 2 of password reset: verify OTP and return JWT tokens.
    Use POST /api/v1/auth/set-password/ (authenticated) to set the new password.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        otp_input = request.data.get("otp")

        if not email or not otp_input:
            return self.build_response(
                success=False,
                message="Email and OTP are required.",
                error={"code": "REQUIRED", "message": "Email and OTP are required."},
                status=400,
            )

        try:
            password_reset_result = AuthService.verify_password_reset(email=email, otp_input=otp_input)
            user = password_reset_result.user
            user.is_password_updated = False  # ty: ignore[invalid-assignment]
            user.save(update_fields=["is_password_updated"])
        except OTPNotFoundError:
            return self.build_response(
                success=False,
                message="No active reset code found for this email.",
                error={"code": "INVALID_OTP", "message": "No active reset code found for this email."},
                status=400,
            )
        except MaxRetriesExceededError:
            return self.build_response(
                success=False,
                message="Too many failed attempts. Please request a new reset code.",
                error={"code": "TOO_MANY_RETRIES", "message": "Too many failed attempts."},
                status=400,
            )
        except OTPExpiredError:
            return self.build_response(
                success=False,
                message="Reset code has expired.",
                error={"code": "OTP_EXPIRED", "message": "Reset code has expired."},
                status=400,
            )
        except OTPInvalidError as e:
            return self.build_response(
                success=False,
                message=f"Invalid code. {e.attempts_remaining} attempts remaining.",
                error={"code": "INVALID_OTP", "message": "Invalid code."},
                status=400,
            )

        return self.build_response(
            success=True,
            message="OTP verified. Use the returned token to set your new password.",
            data={
                "access_token": password_reset_result.tokens.access_token,
                "refresh_token": password_reset_result.tokens.refresh_token,
                "user": UserProfileSerializer(password_reset_result.user).data,
            },
            status=200,
        )

from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
)
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from shared.enums import ApplicationStatus, InviteCodeType, OTPPurpose, UserStatus
from shared.mixins.base_model import AuditModel


class UserManager(BaseUserManager):
    def create_user(
        self,
        email: str | None = None,
        mobile: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> UserMaster:
        user = self.model(email=email, mobile=mobile, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str | None = None,
        mobile: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> UserMaster:
        extra_fields.setdefault("is_staff", True)
        if not password:
            raise ValueError("Superusers must have a password.")
        return self.create_user(email=email, mobile=mobile, password=password, **extra_fields)


class UserMaster(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    mobile = models.CharField(max_length=20, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    status = models.CharField(max_length=50, choices=UserStatus.choices, default=UserStatus.ACTIVE)
    signup_invite_code = models.CharField(max_length=50, null=True, blank=True)  # Track which invite code was used
    first_name = models.CharField(max_length=100, null=True)
    last_name = models.CharField(max_length=100, null=True)
    date_of_birth = models.DateField(null=True)
    gender = models.CharField(max_length=255, null=True)
    profile_image = models.CharField(max_length=500, null=True)
    is_profile_updated = models.BooleanField(default=False)
    is_password_updated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return str(self.email or self.mobile or self.id)

    class Meta:
        db_table = "user_master"
        verbose_name = "UserMaster"
        verbose_name_plural = "UserMasters"

    # Type declarations for static analysis
    objects: UserManager = UserManager()


class OTP(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mobile = models.CharField(max_length=20, null=True)
    email = models.EmailField(max_length=100, null=True)
    otp = models.CharField(max_length=8)
    purpose = models.CharField(max_length=30, choices=OTPPurpose.choices, default=OTPPurpose.EMAIL_VERIFICATION)
    expires_at = models.DateTimeField()
    retry_count = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    device_id = models.CharField(max_length=255, null=True)
    country_code = models.CharField(max_length=10, null=True)
    device_registered = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"OTP for {self.email or self.mobile}"

    # Type declarations for static analysis
    objects: models.Manager[OTP] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

    class Meta:
        db_table = "otp"
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["mobile", "expires_at", "otp"]),
            models.Index(fields=["email", "expires_at", "otp"]),
            models.Index(fields=["purpose", "email", "expires_at"]),
        ]


class InvitationCode(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=6,
        unique=True,
        validators=[RegexValidator(r"^\d{6}$", "Invitation code must be exactly 6 digits.")],
    )
    code_type = models.CharField(max_length=20, choices=InviteCodeType.choices, default=InviteCodeType.GENERIC)
    target_email = models.EmailField(null=True)  # For targeted invites
    max_uses = models.PositiveIntegerField(default=1)
    current_uses = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=True)
    created_by_user_id = models.UUIDField(null=True)

    def __str__(self) -> str:
        return f"{self.code} ({self.code_type})"

    # Type declarations for static analysis
    objects: models.Manager[InvitationCode] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

    class Meta:
        db_table = "invitation_code"
        verbose_name = "InvitationCode"
        verbose_name_plural = "InvitationCodes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]


class SignupSession(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    invite_code = models.CharField(max_length=50)
    otp_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "signup_session"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["invite_code"]),
        ]

    # Type declarations for static analysis
    objects: models.Manager[SignupSession] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class MembershipApplication(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, null=True)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=20, null=True)
    source = models.CharField(max_length=100, null=True)
    remarks = models.TextField(null=True)
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING)

    def __str__(self) -> str:
        return f"{self.name} - {self.email}"

    # Type declarations for static analysis
    objects: models.Manager[MembershipApplication] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

    class Meta:
        db_table = "membership_application"
        verbose_name = "MembershipApplication"
        verbose_name_plural = "MembershipApplications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
        ]

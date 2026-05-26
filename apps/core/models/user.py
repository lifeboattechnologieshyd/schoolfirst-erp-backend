from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


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
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        PENDING = "pending", "Pending"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    mobile = models.CharField(max_length=20, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, null=False)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.ACTIVE)
    signup_invite_code = models.CharField(max_length=50, null=True)  # Track which invite code was used
    first_name = models.CharField(max_length=100, null=True)
    last_name = models.CharField(max_length=100, null=True)
    date_of_birth = models.DateField(null=True)
    gender = models.CharField(max_length=255, null=True)
    profile_image = models.CharField(max_length=500, null=True)
    is_profile_updated = models.BooleanField(default=False, null=False)
    is_password_updated = models.BooleanField(default=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)

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
    DoesNotExist: type[ObjectDoesNotExist]

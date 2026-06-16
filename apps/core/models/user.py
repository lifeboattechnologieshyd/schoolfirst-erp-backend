from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
)
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
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
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        PENDING = "pending", "Pending"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=30, unique=True)

    email = models.EmailField(max_length=255, null=True)
    mobile = models.CharField(max_length=20, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, null=False)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.ACTIVE)
    first_name = models.CharField(max_length=100, null=True)
    last_name = models.CharField(max_length=100, null=True)
    date_of_birth = models.DateField(null=True)
    gender = models.CharField(max_length=255, null=True)
    profile_image = models.CharField(max_length=500, null=True)
    # occupation = models.CharField(max_length=100,blank=True,null=True)
    is_profile_updated = models.BooleanField(default=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return str(self.email or self.mobile or self.id)

class UserOTP(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="otps",
        null=True,
        blank=True,
    )
    mobile = models.BigIntegerField(
        null=True, validators=[MinValueValidator(1000000000), MaxValueValidator(9999999999)]
    )
    email = models.EmailField(max_length=100, null=True)
    otp = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "user_otp"
        indexes = [
            models.Index(fields=["mobile", "expires_at", "otp"]),
            models.Index(fields=["email", "expires_at", "otp"]),
        ]

class Modules(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module_name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="sub_modules",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "modules"

    def __str__(self):
        return self.module_name


class Permissions(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    permission_name = models.CharField(max_length=255)
    module = models.ForeignKey(
        Modules,
        on_delete=models.CASCADE,
        related_name="permissions",
    )

    class Meta:
        db_table = "permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["module", "permission_name"],
                name="unique_permission_per_module",
            )
        ]
        indexes = [
            models.Index(fields=["module", "permission_name"]),
        ]

    def __str__(self):
        return f"{self.module.module_name} - {self.permission_name}"


class Roles(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "roles"

    def __str__(self):
        return self.role_name


class RolePermissions(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Roles,
        on_delete=models.CASCADE,
        related_name="role_permissions_for_role",
    )
    permission = models.ForeignKey(
        Permissions,
        on_delete=models.CASCADE,
        related_name="role_permissions_for_permission",
    )

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="unique_role_permission",
            )
        ]
        indexes = [
            models.Index(fields=["role", "permission"]),
        ]

    def __str__(self):
        return f"{self.role.role_name} -> {self.permission.permission_name}"




class UserRoles(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    school = models.ForeignKey(
        "school.School",
        on_delete=models.CASCADE,
        related_name="user_roles",
        null=True,
        blank=True,
    )
    role = models.ForeignKey(
        Roles,
        on_delete=models.CASCADE,
        related_name="role_users",
    )

    class Meta:
        db_table = "user_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "school", "role"],
                name="unique_user_school_role",
            )
        ]
        indexes = [
            models.Index(fields=["user", "school"]),
            models.Index(fields=["school", "role"]),
        ]

    def __str__(self):
        school_code = self.school.code if self.school else "GLOBAL"
        return f"{self.user.username} - {school_code} - {self.role.role_name}"


class UserPermissions(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="user_direct_permissions",
    )
    school = models.ForeignKey(
        "school.School",
        on_delete=models.CASCADE,
        related_name="user_direct_permissions",
        null=True,
        blank=True,
    )
    permission = models.ForeignKey(
        Permissions,
        on_delete=models.CASCADE,
        related_name="user_permissions",
    )

    class Meta:
        db_table = "user_permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "school", "permission"],
                name="unique_user_school_permission",
            )
        ]
        indexes = [
            models.Index(fields=["user", "school"]),
            models.Index(fields=["school", "permission"]),
        ]

    def __str__(self):
        school_code = self.school.code if self.school else "GLOBAL"
        return f"{self.user.username} - {school_code} - {self.permission.permission_name}"

import random
import string
import uuid

from django.db import models

from shared.mixins.base_model import AuditModel

class Organization(AuditModel):

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    name = models.CharField(max_length=255,unique=True,)
    code = models.CharField(max_length=50,unique=True,)

    email = models.EmailField(

        unique=True,

    )

    phone_number = models.CharField(

        max_length=20,

        unique=True,

    )

    address = models.TextField(

        blank=True,

        null=True,

    )

    website = models.URLField(

        blank=True,

        null=True,

    )

    logo = models.URLField(

        blank=True,

        null=True,

    )

    status = models.CharField(

        max_length=20,

        choices=Status.choices,

        default=Status.ACTIVE,

    )

    class Meta:

        db_table = "organizations"

        ordering = ["-created_at"]

    def __str__(self):

        return self.name


# class School(AuditModel):
#     class BoardType(models.TextChoices):
#         CBSE = "CBSE", "CBSE"
#         ICSE = "ICSE", "ICSE"
#         STATE = "STATE", "State Board"
#         INTERNATIONAL = "INTERNATIONAL", "International"
#         OTHER = "OTHER", "Other"
#
#     class Status(models.TextChoices):
#         ACTIVE = "ACTIVE", "Active"
#         INACTIVE = "INACTIVE", "Inactive"
#
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False,
#     )
#
#     name = models.CharField(max_length=255)
#
#     code = models.CharField(
#         max_length=50,
#         blank=True,
#         null=True,
#     )
#
#     board = models.CharField(
#         max_length=30,
#         choices=BoardType.choices,
#         default=BoardType.OTHER,
#     )
#
#     email = models.CharField(max_length=50,
#         unique=True
#     )
#
#     phone_number = models.CharField(
#         max_length=20,
#         unique=True,
#     )
#
#     principal_name = models.CharField(
#         max_length=255,
#         blank=True,
#         null=True,
#     )
#
#     total_students = models.PositiveIntegerField(
#         default=0,
#     )
#
#     total_staff = models.PositiveIntegerField(
#         default=0,
#     )
#
#     established_year = models.PositiveIntegerField(
#         blank=True,
#         null=True,
#     )
#
#     address = models.TextField()
#
#     city = models.CharField(max_length=100)
#
#     state = models.CharField(max_length=100)
#
#     country = models.CharField(
#         max_length=100,
#         default="India",
#     )
#
#     pincode = models.CharField(
#         max_length=20,
#         blank=True,
#         null=True,
#     )
#
#     website = models.URLField(
#         blank=True,
#         null=True,
#     )
#
#     logo = models.URLField(
#         blank=True,
#         null=True,
#     )
#
#     is_email_verified = models.BooleanField(default=False)
#
#     is_phone_verified = models.BooleanField(default=False)
#
#     status = models.CharField(
#         max_length=20,
#         choices=Status.choices,
#         default=Status.ACTIVE,
#     )
#
#     class Meta:
#         db_table = "schools"
#         ordering = ["-created_at"]
#         indexes = [
#             models.Index(fields=["code"]),
#             models.Index(fields=["email"]),
#             models.Index(fields=["phone_number"]),
#         ]
#
#     def __str__(self):
#         return f"{self.name} ({self.code})"

class School(AuditModel):

    class BoardType(models.TextChoices):

        CBSE = "CBSE", "CBSE"

        ICSE = "ICSE", "ICSE"

        STATE = "STATE", "State Board"

        INTERNATIONAL = "INTERNATIONAL", "International"

        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(

        primary_key=True,

        default=uuid.uuid4,

        editable=False,

    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="schools",
        null=True,
        blank=True,
    )

    name = models.CharField(

        max_length=255,

    )

    code = models.CharField(

        max_length=50,

        unique=True,

    )

    board = models.CharField(

        max_length=30,

        choices=BoardType.choices,

        default=BoardType.OTHER,

    )

    email = models.EmailField(

        unique=True,

    )

    phone_number = models.CharField(

        max_length=20,

        unique=True,

    )

    principal_name = models.CharField(

        max_length=255,

        blank=True,

        null=True,

    )

    principal_email = models.CharField(

        blank=True,

        null=True,

    )

    principal_mobile = models.CharField(

        max_length=20,

        blank=True,

        null=True,

    )

    established_year = models.PositiveIntegerField(

        blank=True,

        null=True,

    )

    address = models.TextField()

    city = models.CharField(

        max_length=100,

    )

    state = models.CharField(

        max_length=100,

    )

    country = models.CharField(

        max_length=100,

        default="India",

    )

    pincode = models.CharField(

        max_length=20,

        blank=True,

        null=True,

    )

    website = models.URLField(

        blank=True,

        null=True,

    )

    logo = models.URLField(

        blank=True,

        null=True,

    )

    is_email_verified = models.BooleanField(

        default=False,

    )

    is_phone_verified = models.BooleanField(

        default=False,

    )

    status = models.CharField(

        max_length=20,

        choices=Status.choices,

        default=Status.ACTIVE,

    )

    class Meta:

        db_table = "schools"

        ordering = ["-created_at"]

        indexes = [

            models.Index(fields=["code"]),

            models.Index(fields=["organization"]),

        ]

    def __str__(self):

        return self.name



class Branch(AuditModel):

    class Status(models.TextChoices):

        ACTIVE = "ACTIVE", "Active"

        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(

        primary_key=True,

        default=uuid.uuid4,

        editable=False,

    )

    school = models.ForeignKey(

        School,

        on_delete=models.CASCADE,

        related_name="branches",

    )

    name = models.CharField(

        max_length=255,

    )

    code = models.CharField(

        max_length=50,

        unique=True,

    )

    email = models.EmailField(

        blank=True,

        null=True,

    )

    phone_number = models.CharField(

        max_length=20,

        blank=True,

        null=True,

    )

    address = models.TextField()

    city = models.CharField(

        max_length=100,

    )

    state = models.CharField(

        max_length=100,

    )

    country = models.CharField(

        max_length=100,

        default="India",

    )

    pincode = models.CharField(

        max_length=20,

        blank=True,

        null=True,

    )

    branch_head_name = models.CharField(

        max_length=255,

        blank=True,

        null=True,

    )

    status = models.CharField(

        max_length=20,

        choices=Status.choices,

        default=Status.ACTIVE,

    )

    class Meta:

        db_table = "school_branches"

        ordering = ["-created_at"]

        indexes = [

            models.Index(fields=["school"]),

            models.Index(fields=["code"]),

        ]

    def __str__(self):

        return f"{self.school.name} - {self.name}"
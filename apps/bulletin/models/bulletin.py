import uuid

from django.db import models

from apps.school.models import School
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class BulletinCategory(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="bulletin_categories",
    )

    name = models.CharField(max_length=100)

    description = models.TextField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bulletin_categories"

        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_bulletin_category_per_school",
            )
        ]

        indexes = [
            models.Index(fields=["school", "is_active"]),
        ]

    def __str__(self):
        return self.name


class Bulletin(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="bulletins",
    )
    category = models.ForeignKey(
        BulletinCategory,
        on_delete=models.CASCADE,
        related_name="bulletins",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=100,
    )

    summary = models.TextField(
        null=True,
        blank=True,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "bulletins"

        indexes = [
            models.Index(
                fields=["school", "is_active"]
            ),
        ]

    def __str__(self):
        return self.name


class BulletinBanner(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class BannerColor(models.TextChoices):
        INDIGO = "INDIGO", "Indigo"
        AMBER = "AMBER", "Amber"
        GREEN = "GREEN", "Green"
        PURPLE = "PURPLE", "Purple"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bulletin = models.OneToOneField(
        "Bulletin",
        on_delete=models.CASCADE,
        related_name="banner",
    )

    label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    headline = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    sub_text = models.CharField(
        max_length=300,
        null=True,
        blank=True,
    )

    banner_color = models.CharField(
        max_length=20,
        choices=BannerColor.choices,
        default=BannerColor.INDIGO,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "bulletin_banners"

        indexes = [
            models.Index(
                fields=["bulletin", "is_active"]
            ),
        ]

    def __str__(self):
        return self.headline or self.label or str(self.id)

class BulletinAttachment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bulletin = models.ForeignKey(
        "BulletinBanner",
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    pdf = models.CharField(max_length=500, null=True, blank=True)

    name = models.CharField(
        max_length=255,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "bulletin_attachments"

        indexes = [
            models.Index(
                fields=[
                    "bulletin",
                    "is_active",
                ]
            ),

        ]

        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return self.name

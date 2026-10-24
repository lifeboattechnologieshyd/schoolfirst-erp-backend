import uuid

from django.db import models

from apps.core.models import UserMaster
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

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        SCHEDULED = "SCHEDULED", "Scheduled"



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

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="bulletins",
    )

    # Category
    category = models.ForeignKey(
        "BulletinCategory",
        on_delete=models.PROTECT,
        related_name="bulletins",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # CONTENT
    # ------------------------------------------------------------------

    title = models.CharField(
        max_length=200,null=True,
        blank=True,
    )

    summary = models.CharField(
        max_length=90,
        null=True,
        blank=True,
    )

    message_body = models.TextField(
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # BANNER
    # ------------------------------------------------------------------

    banner_label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    banner_headline = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    banner_sub_text = models.CharField(
        max_length=300,
        null=True,
        blank=True,
    )

    banner_color = models.CharField(
        max_length=20,
        choices=BannerColor.choices,
        default=BannerColor.INDIGO,
    )


    is_pinned = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        UserMaster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bulletins",
    )



    class Meta:
        db_table = "bulletins"

        indexes = [
            models.Index(
                fields=["school", "is_active"],
            ),
            models.Index(
                fields=["school", "category", "is_active"],
            ),
            models.Index(
                fields=["school", "is_pinned", "is_active"],
            ),

        ]

        ordering = ["-created_at"]

    def __str__(self):
        return self.title



class BulletinAttachment(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bulletin = models.ForeignKey(
        "Bulletin",
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    pdf = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

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
                fields=["bulletin", "is_active"],
            ),
        ]

        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class BulletinRead(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bulletin = models.ForeignKey(
        "Bulletin",
        on_delete=models.CASCADE,
        related_name="reads",
    )

    parent = models.ForeignKey(
        UserMaster,
        on_delete=models.CASCADE,
        related_name="bulletin_reads",
    )

    read_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "bulletin_reads"

        constraints = [
            models.UniqueConstraint(
                fields=["bulletin", "parent"],
                name="unique_bulletin_parent_read",
            ),
        ]

        indexes = [
            models.Index(
                fields=["parent", "bulletin"],
            ),
            models.Index(
                fields=["parent", "read_at"],
            ),
        ]

    def __str__(self):
        return f"{self.parent_id} - {self.bulletin_id}"


class BulletinAudience(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class AudienceType(models.TextChoices):
        ALL_PARENTS = "ALL_PARENTS", "All Parents"
        GRADE = "GRADE", "Grade"
        SECTION = "SECTION", "Section"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bulletin = models.ForeignKey(
        "Bulletin",
        on_delete=models.CASCADE,
        related_name="audiences",
    )

    audience_type = models.CharField(
        max_length=30,
        choices=AudienceType.choices,
    )

    grade = models.ForeignKey(
        "school.Grade",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bulletin_audiences",
    )

    section = models.ForeignKey(
        "school.Section",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bulletin_audiences",
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "bulletin_audiences"

        indexes = [
            models.Index(
                fields=["bulletin", "audience_type"],
            ),
            models.Index(
                fields=["grade", "is_active"],
            ),
            models.Index(
                fields=["section", "is_active"],
            ),
        ]

    def __str__(self):
        if self.audience_type == self.AudienceType.ALL_PARENTS:
            return "All Parents"

        if self.audience_type == self.AudienceType.GRADE:
            return f"Grade: {self.grade}"

        if self.audience_type == self.AudienceType.SECTION:
            return f"Section: {self.section}"

        return str(self.id)

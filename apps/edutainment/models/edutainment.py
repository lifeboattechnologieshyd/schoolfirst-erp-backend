import uuid

from django.db import models

from shared.mixins import AuditModel
from django.contrib.postgres.fields import ArrayField

class Feed(AuditModel):

    class FeedType(models.TextChoices):
        TEXT = "Text", "Text"
        IMAGE = "Image", "Image"
        VIDEO = "Video", "Video"
        YOUTUBE = "Youtube video", "Youtube video"
        AUDIO = "Audio", "Audio"

    class FeedStatus(models.TextChoices):
        DRAFT = "Draft", "Draft"
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"
        PUBLISHED = "Published", "Published"

    class FeedCategory(models.TextChoices):
        DIY = "Diy", "DIY"
        PTIPS = "Ptips", "Parent Tips"
        FTIPS = "Ftips", "Family Tips"
        STORIES = "Stories", "Stories"

    class Language(models.TextChoices):
        TELUGU = "Telugu", "Telugu"
        HINDI = "Hindi", "Hindi"
        ENGLISH = "English", "English"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    feed_type = models.CharField(
        max_length=20,
        choices=FeedType.choices,
        default=FeedType.TEXT,
    )

    trending = models.BooleanField(
        default=True,
    )

    heading = models.CharField(
        max_length=100,
    )

    image = models.CharField(
        max_length=300,
        null=True,
        blank=True,
    )

    video = models.CharField(
        max_length=300,
        null=True,
        blank=True,
    )

    youtube_video = models.CharField(
        max_length=400,
        null=True,
        blank=True,
    )

    audio_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    school_id = models.UUIDField(
        null=True,
        blank=True,
    )

    rejected_school_ids = ArrayField(
        models.CharField(max_length=50),
        null=True,
        blank=True,
    )

    f_category = models.CharField(
        max_length=20,
        choices=FeedCategory.choices,
        default=FeedCategory.DIY,
    )

    categories = ArrayField(
        models.CharField(max_length=50),
        null=True,
        blank=True,
    )

    grade_id = models.UUIDField(
        null=True,
        blank=True,
    )

    subject = models.CharField(
        max_length=400,
        null=True,
        blank=True,
    )

    lesson = models.CharField(
        max_length=400,
        null=True,
        blank=True,
    )

    skill_tested = models.CharField(
        max_length=400,
        null=True,
        blank=True,
    )

    description = models.TextField(
        max_length=5000,
        null=True,
        blank=True,
    )

    description_2 = models.TextField(
        max_length=5000,
        null=True,
        blank=True,
    )

    likes_count = models.PositiveIntegerField(
        default=0,
    )

    comments_count = models.PositiveIntegerField(
        default=0,
    )

    whatsapp_share_count = models.PositiveIntegerField(
        default=0,
    )

    language = models.CharField(
        max_length=20,
        choices=Language.choices,
        default=Language.TELUGU,
    )

    duration = models.PositiveIntegerField(
        default=0,
    )

    remarks = models.TextField(
        null=True,
        blank=True,
    )

    posting_date = models.DateField()

    approved_by = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    approved_time = models.DateTimeField(
        null=True,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=FeedStatus.choices,
        default=FeedStatus.DRAFT,
    )

    serial_number = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "feed"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["f_category", "serial_number"],
                name="unique_feed_category_serial",
            ),
        ]

        indexes = [
            models.Index(
                fields=["heading"],
                name="feed_heading_idx",
            ),
            models.Index(
                fields=["description"],
                name="feed_description_idx",
            ),
            models.Index(
                fields=["f_category"],
                name="feed_category_idx",
            ),
            models.Index(
                fields=["status"],
                name="feed_status_idx",
            ),
            models.Index(
                fields=["trending"],
                name="feed_trending_idx",
            ),
        ]

    def __str__(self):
        return self.heading


class FeedCategories(AuditModel):

    class CategoryStatus(models.TextChoices):
        ACTIVE = "Active", "Active"
        INACTIVE = "Inactive", "Inactive"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    display_name = models.CharField(
        max_length=255,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=CategoryStatus.choices,
        default=CategoryStatus.ACTIVE,
    )

    class Meta:
        db_table = "feed_categories"
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name

class FeedComments(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    feed_id = models.UUIDField()

    user_id = models.UUIDField()

    parent_id = models.UUIDField(
        null=True,
        blank=True,
    )

    comment = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    image = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    likes_count = models.PositiveIntegerField(
        default=0,
    )

    comments_count = models.PositiveIntegerField(
        default=0,
    )

    profile_pic = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    user_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "feed_comments"
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["feed_id"],
                name="feed_comment_feed_idx",
            ),
            models.Index(
                fields=["parent_id"],
                name="feed_comment_parent_idx",
            ),
            models.Index(
                fields=["user_id"],
                name="feed_comment_user_idx",
            ),
        ]

    def __str__(self):
        return str(self.id)

class FeedLikes(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    feed_id = models.UUIDField()

    user_id = models.UUIDField()

    class Meta:
        db_table = "feed_likes"

        constraints = [
            models.UniqueConstraint(
                fields=["feed_id", "user_id"],
                name="unique_feed_user_like",
            ),
        ]

        indexes = [
            models.Index(
                fields=["feed_id"],
                name="feed_likes_feed_idx",
            ),
            models.Index(
                fields=["user_id"],
                name="feed_likes_user_idx",
            ),
        ]

    def __str__(self):
        return f"{self.feed_id} - {self.user_id}"


class DIYMaterials(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    feed = models.ForeignKey(
        Feed,
        on_delete=models.CASCADE,
        related_name="diy_materials",
    )

    material_name = models.CharField(
        max_length=255,
    )

    quantity = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        db_table = "diy_materials"
        ordering = ["display_order"]

        indexes = [
            models.Index(
                fields=["feed", "display_order"],
                name="diy_material_order_idx",
            ),
        ]

    def __str__(self):
        return self.material_name

class DIYSteps(AuditModel):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    feed = models.ForeignKey(
        Feed,
        on_delete=models.CASCADE,
        related_name="diy_steps",
    )

    step_number = models.PositiveIntegerField()

    heading = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    description = models.TextField()

    image = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "diy_steps"
        ordering = ["step_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["feed", "step_number"],
                name="unique_diy_feed_step",
            ),
        ]

    def __str__(self):
        return f"{self.feed.heading} - Step {self.step_number}"
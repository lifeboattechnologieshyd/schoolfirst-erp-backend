import uuid

from django.db import models

from apps.school.models import School
from apps.school.models.school import AcademicYear, Staff, Grade
from shared.managers import SoftDeleteManager
from shared.mixins import AuditModel


class GalleryCategory(AuditModel):
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
        related_name="gallery_categories",
    )

    name = models.CharField(max_length=100)

    description = models.TextField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "gallery_categories"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_gallery_category_per_school",
            )
        ]

    def __str__(self):
        return self.name



class Gallery(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Visibility(models.TextChoices):
        SCHOOL = "SCHOOL", "Entire School"
        STAFF = "STAFF", "Selected Staff"
        GRADE = "GRADE", "Selected Grades"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="galleries",
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="galleries",
    )

    category = models.ForeignKey(
        GalleryCategory,
        on_delete=models.PROTECT,
        related_name="galleries",
    )

    title = models.CharField(max_length=200)

    description = models.TextField(
        null=True,
        blank=True,
    )

    event_date = models.DateField(
        null=True,
        blank=True,
    )

    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.SCHOOL,
    )

    allow_downloads = models.BooleanField(default=True)

    is_published = models.BooleanField(default=False)

    class Meta:
        db_table = "galleries"
        ordering = ["-event_date", "-created_at"]

    def __str__(self):
        return self.title



class GalleryImage(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name="images",
    )

    image = models.ImageField(
        upload_to="gallery/",
    )

    caption = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "gallery_images"
        ordering = ["display_order", "created_at"]

    def __str__(self):
        return f"{self.gallery.title} - Image"


class GalleryVideo(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name="videos",
    )

    video = models.FileField(
        upload_to="gallery/videos/",
    )

    caption = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "gallery_videos"
        ordering = ["display_order", "created_at"]

    def __str__(self):
        return f"{self.gallery.title} - Video"


class GalleryStaff(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name="visible_staff",
    )

    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="visible_galleries",
    )

    class Meta:
        db_table = "gallery_staff"
        constraints = [
            models.UniqueConstraint(
                fields=["gallery", "staff"],
                name="unique_gallery_staff",
            )
        ]

class GalleryGrade(AuditModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name="visible_grades",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="visible_galleries",
    )

    class Meta:
        db_table = "gallery_grades"
        constraints = [
            models.UniqueConstraint(
                fields=["gallery", "grade"],
                name="unique_gallery_grade",
            )
        ]
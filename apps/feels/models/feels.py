import uuid

from django.db import models

from shared.mixins import AuditModel


class Feels(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youtube_video = models.CharField(max_length=300, null=True)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=1000, null=True)
    thumbnail_image= models.CharField(max_length=300, null=True)
    likes_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=50,default="NA")
    serial_number = models.PositiveIntegerField(unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.serial_number:
            last_serial = Feels.objects.aggregate(
                models.Max("serial_number")
            )["serial_number__max"] or 0

            self.serial_number = last_serial + 1

        super().save(*args, **kwargs)


    class Meta:
        db_table ="feels"
        ordering = ["-created_at"]

class FeelViews(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feel_id = models.UUIDField()
    user_id = models.UUIDField()
    duration = models.PositiveIntegerField(default=0)
    time = models.TimeField()
    ip_address = models.CharField(max_length=50, null=True)
    device_id = models.CharField(max_length=50,null=True)

    class Meta:
        db_table ="feel_views"
        ordering = ["-created_at"]



class FeelLikes(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feel_id = models.UUIDField()
    user_id = models.UUIDField()

    class Meta:
        db_table ="feel_likes"

        indexes = [
            models.Index(fields=["feel_id"]),
            models.Index(fields=["user_id"]),
        ]
        unique_together = [["feel_id", "user_id"]]
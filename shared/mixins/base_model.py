from typing import Any, cast

from crum import get_current_request
from django.db import models
from django.utils import timezone

class TimeAuditModel(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        verbose_name="Created At",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At",
    )

    class Meta:
        abstract = True


class UserAuditModel(models.Model):
    created_by = models.CharField(max_length=255, null=True, editable=False)
    updated_by = models.CharField(max_length=255, null=True)

    class Meta:
        abstract = True

class DeleteAuditModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.CharField(max_length=255, null=True, blank=True)
    class Meta:
        abstract = True

    def soft_delete(self, user):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = str(user.id)
        self.save(
            update_fields=["is_deleted","deleted_at","deleted_by",]
        )

class AuditModel(TimeAuditModel, UserAuditModel, DeleteAuditModel):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        request = get_current_request()
        if request and hasattr(request, "user") and request.user.is_authenticated:
            current_user_id = str(request.user.id)
            if not self.created_by:
                self.created_by = cast(Any, current_user_id)
            self.updated_by = cast(Any, current_user_id)
        super().save(*args, **kwargs)

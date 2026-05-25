from typing import Any, cast

from crum import get_current_request
from django.db import models


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


class AuditModel(TimeAuditModel, UserAuditModel):
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

from django.db import models

from apps.calendar.enums import AccessType


class AccessControlMixin(models.Model):
    """
    Reusable abstract mixin for 3-tier access control.

    access_type             — which tier applies
    access_family_ids       — Family UUIDs; used when access_type=all/mixed
    access_close_group_ids  — CloseGroup UUIDs; used when access_type=all/mixed
    access_user_ids         — UserMaster UUIDs; usable with all/mixed
    """

    access_type = models.CharField(
        max_length=20,
        choices=AccessType.choices,
        default=AccessType.ONLY_ME,
    )
    access_family_ids = models.JSONField(default=list, null=True)
    access_close_group_ids = models.JSONField(default=list, null=True)
    access_user_ids = models.JSONField(default=list, null=True)

    class Meta:
        abstract = True

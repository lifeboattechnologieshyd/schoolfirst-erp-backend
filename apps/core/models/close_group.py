from __future__ import annotations

import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from shared.mixins.base_model import AuditModel

from .user import UserMaster


class CloseGroup(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="close_groups")
    name = models.CharField(max_length=100)
    member_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "close_group"
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return f"{self.owner}'s Close Group — {self.name}"

    # Type declarations for static analysis
    objects: models.Manager[CloseGroup] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]


class CloseGroupMember(AuditModel):
    class Status(models.TextChoices):
        INVITED = "INVITED", "Invited"
        JOINED = "JOINED", "Joined"
        REMOVED = "REMOVED", "Removed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    close_group = models.ForeignKey(CloseGroup, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(UserMaster, null=True, on_delete=models.CASCADE, related_name="close_group_memberships")
    email = models.EmailField(max_length=100)
    added_by = models.ForeignKey(
        UserMaster, on_delete=models.SET_NULL, null=True, related_name="close_group_invites_sent"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED)

    class Meta:
        db_table = "close_group_member"
        unique_together = [("close_group", "email")]
        indexes = [
            models.Index(fields=["close_group"]),
            models.Index(fields=["user"]),
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} in {self.close_group}"

    # Type declarations for static analysis
    objects: models.Manager[CloseGroupMember] = models.Manager()
    DoesNotExist: type[ObjectDoesNotExist]

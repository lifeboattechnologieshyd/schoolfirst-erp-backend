from __future__ import annotations

import uuid

from django.db import models

from apps.core.models import UserMaster
from shared.mixins.base_model import AuditModel


class Family(AuditModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects: models.Manager[Family] = models.Manager()
    name = models.CharField(max_length=150)
    family_picture = models.CharField(max_length=500, null=True)
    owner = models.ForeignKey(UserMaster, on_delete=models.CASCADE, related_name="owned_families")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "family"
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return str(self.name)


class FamilyMember(AuditModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        JOINED = "joined", "Joined"
        REMOVED = "removed", "Removed"
        REJECTED = "rejected", "Rejected"

    class Relation(models.TextChoices):
        SPOUSE = "spouse", "Spouse"
        MOTHER = "mother", "Mother"
        FATHER = "father", "Father"
        SON = "son", "Son"
        DAUGHTER = "daughter", "Daughter"
        BROTHER = "brother", "Brother"
        SISTER = "sister", "Sister"
        GRANDFATHER = "grandfather", "Grandfather"
        GRANDMOTHER = "grandmother", "Grandmother"
        GRANDSON = "grandson", "Grandson"
        GRANDDAUGHTER = "granddaughter", "Granddaughter"
        UNCLE = "uncle", "Uncle"
        AUNT = "aunt", "Aunt"
        NEPHEW = "nephew", "Nephew"
        NIECE = "niece", "Niece"
        FATHER_IN_LAW = "father_in_law", "Father-in-law"
        MOTHER_IN_LAW = "mother_in_law", "Mother-in-law"
        SON_IN_LAW = "son_in_law", "Son-in-law"
        DAUGHTER_IN_LAW = "daughter_in_law", "Daughter-in-law"
        BROTHER_IN_LAW = "brother_in_law", "Brother-in-law"
        SISTER_IN_LAW = "sister_in_law", "Sister-in-law"
        STEPFATHER = "stepfather", "Stepfather"
        STEPMOTHER = "stepmother", "Stepmother"
        STEPSON = "stepson", "Stepson"
        STEPDAUGHTER = "stepdaughter", "Stepdaughter"
        STEPBROTHER = "stepbrother", "Stepbrother"
        STEPSISTER = "stepsister", "Stepsister"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects: models.Manager[FamilyMember] = models.Manager()
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(UserMaster, null=True, on_delete=models.CASCADE, related_name="family_memberships")
    email = models.EmailField(max_length=100)
    first_name = models.CharField(max_length=100, null=True)
    last_name = models.CharField(max_length=100, null=True)
    gender = models.CharField(max_length=255, null=True)
    relation = models.CharField(max_length=20, choices=Relation.choices, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED)
    invited_by = models.ForeignKey(UserMaster, on_delete=models.SET_NULL, null=True, related_name="family_invites_sent")

    class Meta:
        db_table = "family_member"
        unique_together = [("family", "email")]
        indexes = [
            models.Index(fields=["family"]),
            models.Index(fields=["user"]),
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} in {self.family.name}"

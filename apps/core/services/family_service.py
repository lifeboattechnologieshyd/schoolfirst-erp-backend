from typing import Any

import structlog
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models.family import Family, FamilyMember
from apps.core.models.user import UserMaster
from shared.helpers.email import send_app_invite_email, send_family_added_email
from shared.helpers.invitation import ensure_targeted_invite
from shared.utils.files import move_file

logger = structlog.get_logger("default")


class FamilyService:
    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @staticmethod
    def _validate_relation(relation: str | None) -> str | None:
        """Normalise and validate the relation, returning the canonical value."""
        if relation is None:
            return None
        normalised = relation.strip().lower().replace(" ", "_")
        if normalised not in FamilyMember.Relation.values:
            valid_values = ", ".join(FamilyMember.Relation.values)
            raise ValidationError({"relation": [f"Invalid relation. Valid values are: {valid_values}"]})
        return normalised

    @staticmethod
    def _get_invited_member_profile(
        existing_user: UserMaster | None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender: str | None = None,
    ) -> dict[str, str | None]:
        if existing_user:
            return {
                "first_name": None,
                "last_name": None,
                "gender": None,
            }

        invited_profile = {
            "first_name": FamilyService._normalize_optional_text(first_name),
            "last_name": FamilyService._normalize_optional_text(last_name),
            "gender": FamilyService._normalize_optional_text(gender),
        }
        missing_fields = [field_name for field_name, field_value in invited_profile.items() if field_value is None]
        if missing_fields:
            raise ValidationError(
                {
                    field_name: ["This field is required when the invited user does not have an account."]
                    for field_name in missing_fields
                }
            )
        return invited_profile

    @staticmethod
    @transaction.atomic
    def create_family(user: UserMaster, name: str, family_picture: str | None = None) -> Family:
        """Create a family and add the creator as OWNER with JOINED status."""
        if Family.objects.filter(owner=user, is_active=True).exists():
            raise ValidationError(
                {"non_field_errors": ["You have already created a family. A user can only create one family."]}
            )

        family = Family.objects.create(
            name=name,
            family_picture=family_picture,
            owner=user,
        )

        if family_picture:
            new_path = move_file(family_picture, f"families/{family.id}")
            if new_path:
                family.family_picture = new_path
                family.save(update_fields=["family_picture"])
        FamilyMember.objects.create(
            family=family,
            user=user,
            email=user.email,
            role=FamilyMember.Role.OWNER,
            status=FamilyMember.Status.JOINED,
            invited_by=user,
        )
        return family

    @staticmethod
    def get_family(family_id: Any, user_id: Any) -> Family:
        """Get family by ID. User must be a JOINED or INVITED member."""
        family = get_object_or_404(Family, id=family_id, is_active=True)
        if not FamilyMember.objects.filter(
            family=family,
            user_id=user_id,
            status__in=[FamilyMember.Status.JOINED, FamilyMember.Status.INVITED],
        ).exists():
            raise PermissionDenied("You are not an active member of this family.")
        return family

    @staticmethod
    @transaction.atomic
    def delete_family(family_id: Any, owner_id: Any) -> bool:
        """Completely delete a family and all its members. Owner-only action."""
        family = get_object_or_404(Family, id=family_id, is_active=True)
        if str(family.owner_id) != str(owner_id):
            raise PermissionDenied("Only the family owner can delete the family.")
        family.delete()
        return True

    @staticmethod
    def list_user_families(user_id: Any) -> QuerySet[Family]:
        """List families where user is a JOINED or INVITED member."""
        family_ids = FamilyMember.objects.filter(
            user_id=user_id,
            status__in=[FamilyMember.Status.JOINED, FamilyMember.Status.INVITED],
        ).values_list("family_id", flat=True)
        return (
            Family.objects.filter(id__in=family_ids, is_active=True)
            .select_related("owner")
            .annotate(
                joined_member_count=Count(
                    "members", filter=Q(members__status=FamilyMember.Status.JOINED), distinct=True
                ),
            )
        )

    @staticmethod
    @transaction.atomic
    def add_member(
        family_id: Any,
        owner_id: Any,
        email: str,
        relation: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        gender: str | None = None,
    ) -> FamilyMember:
        """
        Add a member to a family by email. Owner-only action.
        - If user exists: status=INVITED (must accept), send notification email.
        - If user doesn't exist: status=INVITED, user=None, send 2 emails
          (family notification + targeted app invite code).
        """
        family = get_object_or_404(Family, id=family_id, is_active=True)

        if str(family.owner_id) != str(owner_id):
            raise PermissionDenied("Only the family owner can add members.")

        if (
            FamilyMember.objects.filter(family=family, email=email)
            .exclude(status__in=[FamilyMember.Status.REMOVED, FamilyMember.Status.REJECTED])
            .exists()
        ):
            raise ValidationError({"email": ["This email is already a member or has a pending invite."]})

        relation = FamilyService._validate_relation(relation)
        existing_user = UserMaster.objects.filter(email=email).first()
        invited_profile = FamilyService._get_invited_member_profile(
            existing_user=existing_user,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
        )
        inviter = UserMaster.objects.get(id=owner_id)
        inviter_name = inviter.first_name or inviter.email

        removed = FamilyMember.objects.filter(
            family=family,
            email=email,
            status__in=[FamilyMember.Status.REMOVED, FamilyMember.Status.REJECTED],
        ).first()
        if removed:
            removed.user = existing_user
            removed.first_name = invited_profile["first_name"]
            removed.last_name = invited_profile["last_name"]
            removed.gender = invited_profile["gender"]
            removed.relation = relation
            removed.role = FamilyMember.Role.MEMBER
            removed.status = FamilyMember.Status.INVITED
            removed.invited_by = inviter
            removed.save()
            member = removed
        else:
            member = FamilyMember.objects.create(
                family=family,
                user=existing_user,
                email=email,
                first_name=invited_profile["first_name"],
                last_name=invited_profile["last_name"],
                gender=invited_profile["gender"],
                relation=relation,
                role=FamilyMember.Role.MEMBER,
                status=FamilyMember.Status.INVITED,
                invited_by=inviter,
            )

        if existing_user:
            send_family_added_email(
                to_email=email,
                inviter_name=inviter_name,
                family_name=family.name,
            )
        else:
            send_family_added_email(
                to_email=email,
                inviter_name=inviter_name,
                family_name=family.name,
            )
            code = ensure_targeted_invite(email)

            send_app_invite_email(
                to_email=email,
                inviter_name=inviter_name,
                invite_code=code,
            )

        logger.info(
            "Family member added",
            family_id=str(family_id),
            email=email,
            user_exists=existing_user is not None,
        )
        return member

    @staticmethod
    @transaction.atomic
    def remove_member(family_id: Any, owner_id: Any, member_id: Any) -> bool:
        """Remove a member from a family. Owner-only action. Cannot remove self."""
        family = get_object_or_404(Family, id=family_id, is_active=True)

        if str(family.owner_id) != str(owner_id):
            raise PermissionDenied("Only the family owner can remove members.")

        member = get_object_or_404(FamilyMember, id=member_id, family=family)

        if str(member.user_id) == str(owner_id):
            raise ValidationError({"member": ["Cannot remove yourself as the owner."]})

        member.delete()
        return True

    @staticmethod
    def list_members(family_id: Any, user_id: Any) -> QuerySet[FamilyMember]:
        """List family members. Caller must be a JOINED or INVITED member.

        Visibility rules:
        - Owner sees JOINED + INVITED + REJECTED members.
        - Non-owner JOINED/INVITED members see JOINED + INVITED members.
        """
        family = get_object_or_404(Family, id=family_id, is_active=True)
        caller = FamilyMember.objects.filter(
            family=family,
            user_id=user_id,
            status__in=[FamilyMember.Status.JOINED, FamilyMember.Status.INVITED],
        ).first()
        if not caller:
            raise PermissionDenied("You are not an active member of this family.")

        is_owner = str(family.owner_id) == str(user_id)

        qs = FamilyMember.objects.filter(family=family).select_related("user", "invited_by")

        if is_owner:
            return qs.exclude(status=FamilyMember.Status.REMOVED)
        return qs.filter(status__in=[FamilyMember.Status.JOINED, FamilyMember.Status.INVITED])

    @staticmethod
    def accept_invitation(user_id: Any, family_id: Any) -> FamilyMember:
        member = get_object_or_404(
            FamilyMember,
            family_id=family_id,
            user_id=user_id,
            status=FamilyMember.Status.INVITED,
        )
        member.status = FamilyMember.Status.JOINED
        member.save()
        return member

    @staticmethod
    def decline_invitation(user_id: Any, family_id: Any) -> FamilyMember:
        member = get_object_or_404(
            FamilyMember,
            family_id=family_id,
            user_id=user_id,
            status=FamilyMember.Status.INVITED,
        )
        member.status = FamilyMember.Status.REJECTED
        member.save()
        return member

    @staticmethod
    def exit_family(family_id: Any, user_id: Any) -> bool:
        family = get_object_or_404(Family, id=family_id, is_active=True)

        if str(family.owner_id) == str(user_id):
            raise ValidationError({"family": ["The owner cannot exit the family."]})

        member = get_object_or_404(FamilyMember, family=family, user_id=user_id, status=FamilyMember.Status.JOINED)
        member.status = FamilyMember.Status.REMOVED
        member.save()
        return True

    @staticmethod
    def resolve_pending_invites(email: str, user: UserMaster) -> int:
        updated = FamilyMember.objects.filter(
            email__iexact=email,
            status=FamilyMember.Status.INVITED,
            user__isnull=True,
        ).update(user=user, first_name=None, last_name=None, gender=None)
        if updated:
            logger.info("Resolved family invites on signup", email=email, count=updated)
        return updated

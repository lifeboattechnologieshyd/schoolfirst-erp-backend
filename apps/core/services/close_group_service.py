from typing import Any

import structlog
from django.db import transaction
from django.db.models import F, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models.close_group import CloseGroup, CloseGroupMember
from apps.core.models.user import UserMaster
from shared.helpers.email import send_app_invite_email, send_close_group_added_email
from shared.helpers.invitation import ensure_targeted_invite

logger = structlog.get_logger("default")


class CloseGroupService:
    @staticmethod
    def get_or_create_default_group(user: UserMaster) -> CloseGroup:
        """Get or auto-create the user's default close group."""
        group, _ = CloseGroup.objects.get_or_create(
            owner=user,
            name="Default",
            defaults={"is_active": True},
        )
        return group

    @staticmethod
    def _get_owned_group(user: UserMaster, close_group_id: Any) -> CloseGroup:
        """Fetch a close group by ID and assert ownership. Raises PermissionDenied."""
        group = CloseGroup.objects.filter(id=close_group_id).first()
        if group is None:
            raise PermissionDenied("Close group not found.")
        if group.owner_id != user.id:
            raise PermissionDenied("You do not own this close group.")
        return group

    @staticmethod
    @transaction.atomic
    def add_member(user: UserMaster, email: str, close_group_id: Any) -> CloseGroupMember:
        """
        Add to close group by email. Auto-accept if account exists (like follow).
        - If user exists: status=JOINED immediately, send notification email.
        - If user doesn't exist: status=INVITED, send 2 emails
          (close group notification + targeted app invite).
        """
        group = CloseGroupService._get_owned_group(user, close_group_id)

        # Cannot add yourself
        if email.lower() == str(user.email).lower():
            raise ValidationError({"email": ["Cannot add yourself to your close group."]})

        # Prevent duplicate
        if CloseGroupMember.objects.filter(close_group=group, email=email).exists():
            raise ValidationError({"email": ["This email is already in your close group."]})

        existing_user = UserMaster.objects.filter(email=email).first()
        adder_name = user.first_name or user.email

        if existing_user:
            # User exists — auto-accept, status=JOINED
            member = CloseGroupMember.objects.create(
                close_group=group,
                user=existing_user,
                email=email,
                added_by=user,
                status=CloseGroupMember.Status.JOINED,
            )
            CloseGroup.objects.filter(id=group.id).update(member_count=F("member_count") + 1)
            send_close_group_added_email(
                to_email=email,
                adder_name=adder_name,
            )
        else:
            # User doesn't exist — status=INVITED, send 2 emails
            # member_count NOT incremented until invite converts to JOINED
            member = CloseGroupMember.objects.create(
                close_group=group,
                user=None,
                email=email,
                added_by=user,
                status=CloseGroupMember.Status.INVITED,
            )
            # 1. Close group notification
            send_close_group_added_email(
                to_email=email,
                adder_name=adder_name,
            )
            code = ensure_targeted_invite(email)

            send_app_invite_email(
                to_email=email,
                inviter_name=adder_name,
                invite_code=code,
            )

        logger.info(
            "Close group member added",
            email=email,
            user_exists=existing_user is not None,
            status=member.status,
        )
        return member

    @staticmethod
    @transaction.atomic
    def remove_member(user: UserMaster, member_id: Any, close_group_id: Any) -> bool:
        """Remove a member from close group."""
        group = CloseGroupService._get_owned_group(user, close_group_id)
        member = get_object_or_404(CloseGroupMember, id=member_id, close_group=group)
        was_joined = member.status == CloseGroupMember.Status.JOINED
        member.delete()
        if was_joined:
            CloseGroup.objects.filter(id=group.id).update(member_count=F("member_count") - 1)
        return True

    @staticmethod
    @transaction.atomic
    def list_members(user: UserMaster, close_group_id: Any) -> QuerySet[CloseGroupMember]:
        """List close group members for a specific owned group."""
        group = CloseGroupService._get_owned_group(user, close_group_id)
        return (
            CloseGroupMember.objects.filter(close_group=group)
            .exclude(status=CloseGroupMember.Status.REMOVED)
            .select_related("user", "added_by")
        )

    @staticmethod
    def resolve_pending_invites(email: str, user: UserMaster) -> int:
        """
        Called at signup. Links all INVITED CloseGroupMember rows matching
        this email to the new user AND sets status=JOINED (auto-accept).
        Increments member_count on each affected group.
        """
        pending_group_ids = list(
            CloseGroupMember.objects.filter(
                email__iexact=email,
                status=CloseGroupMember.Status.INVITED,
                user__isnull=True,
            ).values_list("close_group_id", flat=True)
        )
        updated = CloseGroupMember.objects.filter(
            email__iexact=email,
            status=CloseGroupMember.Status.INVITED,
            user__isnull=True,
        ).update(user=user, status=CloseGroupMember.Status.JOINED)
        if updated:
            CloseGroup.objects.filter(id__in=pending_group_ids).update(member_count=F("member_count") + 1)
            logger.info("Resolved close group invites on signup", email=email, count=updated)
        return updated

    @staticmethod
    def list_added_me(user: UserMaster) -> list[UserMaster]:
        """
        Return UserMaster objects for users who have added `user` to their
        close group, but whom `user` has NOT yet added back (i.e. not in
        any of `user`'s own close groups with status != REMOVED).
        """
        # Emails of people the requesting user has already added (across all
        # owned groups)
        my_member_emails = set(
            CloseGroupMember.objects.filter(close_group__owner=user)
            .exclude(status=CloseGroupMember.Status.REMOVED)
            .values_list("email", flat=True)
        )

        # Close groups where I am a (non-removed) member
        my_memberships = (
            CloseGroupMember.objects.filter(user=user)
            .exclude(status=CloseGroupMember.Status.REMOVED)
            .select_related("close_group__owner")
        )

        # Collect owners who have not been added back by me
        owners = []
        seen = set()
        for membership in my_memberships:
            owner = membership.close_group.owner
            if owner.email.lower() not in my_member_emails and owner.pk not in seen:
                owners.append(owner)
                seen.add(owner.pk)

        return owners

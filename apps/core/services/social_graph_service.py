from dataclasses import dataclass
from typing import Any

import structlog

from apps.core.models.close_group import CloseGroup, CloseGroupMember
from apps.core.models.family import FamilyMember
from apps.core.models.user import UserMaster

logger = structlog.get_logger("default")


@dataclass(frozen=True)
class SocialGraphScope:
    family_ids: list[str]
    close_group_membership_ids: list[str]
    access_user_id_candidates: list[str]


class SocialGraphService:
    """
    Cross-app read gateway for social graph membership queries.

    Other apps (e.g. calendar) must call this service instead of importing
    core models directly. This keeps cross-app ORM coupling in one place and
    respects the multi-database routing boundary.

    All methods accept a UserMaster instance and return plain Python lists so
    callers never touch core ORM directly.
    """

    @staticmethod
    def get_user_by_id(user_id: Any) -> UserMaster | None:
        return UserMaster.objects.only("id").filter(id=user_id).first()

    @staticmethod
    def get_user_family_ids(user: UserMaster) -> list[str]:
        """Return UUID strings of Families the user belongs to as a JOINED member."""
        ids = FamilyMember.objects.filter(
            user=user,
            status=FamilyMember.Status.JOINED,
        ).values_list("family_id", flat=True)
        return [str(fid) for fid in ids]

    @staticmethod
    def get_user_family_ids_for_user_id(user_id: Any) -> list[str]:
        user = SocialGraphService.get_user_by_id(user_id)
        if user is None:
            return []
        return SocialGraphService.get_user_family_ids(user)

    @staticmethod
    def get_joined_family_member_user_ids_by_family_id(family_id: Any) -> list[str]:
        user_ids = FamilyMember.objects.filter(
            family_id=family_id,
            status=FamilyMember.Status.JOINED,
            user__isnull=False,
        ).values_list("user_id", flat=True)
        return [str(user_id) for user_id in user_ids]

    @staticmethod
    def get_joined_family_member_user_ids(user: UserMaster) -> list[str]:
        """Return UUID strings of JOINED users across the creator's families."""
        family_ids = SocialGraphService.get_user_family_ids(user)
        if not family_ids:
            return [str(user.id)]

        user_ids = FamilyMember.objects.filter(
            family_id__in=family_ids,
            status=FamilyMember.Status.JOINED,
            user__isnull=False,
        ).values_list("user_id", flat=True)
        return list({str(user_id) for user_id in user_ids} | {str(user.id)})

    @staticmethod
    def get_own_close_group_member_user_ids(user: UserMaster) -> list[str]:
        """Return UUID strings of JOINED users in any of the user's owned
        close groups."""
        user_ids = CloseGroupMember.objects.filter(
            close_group__owner=user,
            status=CloseGroupMember.Status.JOINED,
            user__isnull=False,
        ).values_list("user_id", flat=True)
        return list({str(user_id) for user_id in user_ids} | {str(user.id)})

    @staticmethod
    def get_access_user_id_candidates(user: UserMaster) -> list[str]:
        """
        Return UUID strings the user is allowed to target via access_user_ids.

        A target must either be:
        - a JOINED member of one of the creator's families, or
        - a JOINED member of any of the creator's own close groups.
        """
        return list(
            set(SocialGraphService.get_joined_family_member_user_ids(user))
            | set(SocialGraphService.get_own_close_group_member_user_ids(user))
            | {str(user.id)}
        )

    @staticmethod
    def get_close_group_membership_ids(user: UserMaster) -> list[str]:
        """
        Return CloseGroup UUIDs (as strings) where the requesting user is a
        JOINED CloseGroupMember (i.e. groups owned by others that they belong to).
        """
        memberships = CloseGroupMember.objects.filter(
            user=user,
            status=CloseGroupMember.Status.JOINED,
        ).values_list("close_group_id", flat=True)
        return [str(cg_id) for cg_id in memberships]

    @staticmethod
    def get_owned_close_group_ids(user: UserMaster) -> list[str]:
        """Return UUIDs of CloseGroups owned by this user."""
        ids = CloseGroup.objects.filter(owner=user).values_list("id", flat=True)
        return [str(cg_id) for cg_id in ids]

    @staticmethod
    def build_visibility_scope(user: UserMaster) -> SocialGraphScope:
        return SocialGraphScope(
            family_ids=SocialGraphService.get_user_family_ids(user),
            close_group_membership_ids=SocialGraphService.get_close_group_membership_ids(user),
            access_user_id_candidates=SocialGraphService.get_access_user_id_candidates(user),
        )

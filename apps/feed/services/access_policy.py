from functools import reduce
from operator import or_

from django.db.models import Q

from apps.feed.enums import AccessType


def validate_access_configuration(
    *,
    access_type: str | None,
    access_family_ids: list | None,
    access_close_group_ids: list | None,
    access_user_ids: list | None,
) -> dict | None:
    if access_type == AccessType.ONLY_ME and (access_family_ids or access_close_group_ids or access_user_ids):
        return {"access_type": "All access arrays must be empty for only_me access."}

    if access_type == AccessType.ALL:
        if not (access_family_ids or access_close_group_ids):
            return {"access_type": "At least one family ID or close group ID is required for all access."}
        if access_user_ids:
            return {"access_user_ids": "access_user_ids must be empty for all access."}

    if access_type == AccessType.MIXED and not (access_family_ids or access_close_group_ids or access_user_ids):
        return {"access_type": "At least one ID is required in any access array for mixed access."}

    return None


def validate_access_ids_ownership(
    *,
    access_family_ids: list | None,
    access_close_group_ids: list | None,
    creator_family_ids: list[str],
    creator_close_group_ids: set[str],
) -> dict | None:
    if access_family_ids:
        invalid = sorted({str(i) for i in access_family_ids} - set(creator_family_ids))
        if invalid:
            return {"access_family_ids": f"Family IDs not in creator's families: {invalid}"}
    if access_close_group_ids:
        invalid = sorted({str(i) for i in access_close_group_ids} - creator_close_group_ids)
        if invalid:
            return {"access_close_group_ids": f"Close group IDs not owned or joined: {invalid}"}
    return None


def validate_access_user_ids(
    *,
    access_user_ids: list | None,
    allowed_user_ids: set[str],
) -> dict | None:
    if not access_user_ids:
        return None
    invalid = sorted({str(uid) for uid in access_user_ids} - allowed_user_ids)
    if not invalid:
        return None
    return {
        "access_user_ids": (
            "Specific access users must be joined family members or joined members of your close group. "
            f"Invalid user ids: {', '.join(invalid)}"
        )
    }


class FeedAccessPolicy:
    @staticmethod
    def build_filter(user_id, scope) -> Q:
        user_id_str = str(user_id)

        own = Q(creator_id=user_id)

        shared_conditions = Q(access_user_ids__contains=[user_id_str])

        if scope.family_ids:
            family_qs = [Q(access_family_ids__contains=[fid]) for fid in scope.family_ids]
            shared_conditions |= reduce(or_, family_qs)

        if scope.close_group_membership_ids:
            cg_qs = [Q(access_close_group_ids__contains=[cgid]) for cgid in scope.close_group_membership_ids]
            shared_conditions |= reduce(or_, cg_qs)

        shared = ~Q(access_type=AccessType.ONLY_ME) & shared_conditions

        return own | shared

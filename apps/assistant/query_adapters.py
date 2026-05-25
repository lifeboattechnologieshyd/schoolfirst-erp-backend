from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date
from typing import Any, cast

from django.db.models import Count, Q
from typing_extensions import TypedDict

from apps.assistant.models.thread import Thread
from apps.assistant.serializers.thread_settings import coerce_thread_module_settings
from apps.core.models.close_group import CloseGroup, CloseGroupMember
from apps.core.models.family import Family, FamilyMember
from apps.core.models.user import UserMaster
from apps.docusafe.models import DocusafeFile
from apps.docusafe.services.access_service import DocusafeAccessService


class FamilyMemberMatch(TypedDict):
    name: str
    relation: str
    family: str
    status: str


class FindFamilyMemberMatchesResult(TypedDict):
    joined_family_ids: list[uuid.UUID]
    matches: list[FamilyMemberMatch]


class CloseGroupMemberData(TypedDict):
    name: str
    email: str
    status: str


class UpcomingBirthdayData(TypedDict):
    delta: int
    name: str
    date: str
    display_date: str


class UpcomingBirthdaysResult(TypedDict):
    connected_users: bool
    birthdays: list[UpcomingBirthdayData]


def get_docusafe_file_names(file_ids: list[str | uuid.UUID]) -> list[str]:
    """Return file names for the provided Docusafe File IDs."""
    normalized_ids = [str(file_id) for file_id in file_ids if file_id]
    if not normalized_ids:
        return []

    return list(
        DocusafeFile.objects.filter(id__in=normalized_ids).only("file_name").values_list("file_name", flat=True)
    )


def build_user_network_context(user_id: str) -> str:
    """Build a compact network context string for the default assistant intent."""
    user = UserMaster.objects.filter(id=user_id).only("first_name", "last_name", "is_profile_updated").first()
    if not user:
        return ""

    full_name = " ".join(filter(None, [user.first_name, user.last_name]))

    joined_family_ids = list(
        FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.JOINED).values_list(
            "family_id", flat=True
        )
    )
    family_names = list(Family.objects.filter(id__in=joined_family_ids, is_active=True).values_list("name", flat=True))

    close_group = CloseGroup.objects.filter(owner_id=user_id).first()
    cg_count = 0
    if close_group:
        cg_count = CloseGroupMember.objects.filter(
            close_group=close_group,
            status=CloseGroupMember.Status.JOINED,
        ).count()

    parts = []
    if full_name:
        parts.append(f"User name: {full_name}")
    parts.append(f"Families: {', '.join(family_names)}" if family_names else "Families: none yet")
    parts.append(f"Close group members (joined): {cg_count}")

    return "USER NETWORK CONTEXT: " + " | ".join(parts) + "."


def load_thread(thread_id: str) -> Thread | None:
    return Thread.objects.filter(id=thread_id).first()


def load_attached_docusafe_file_ids(thread: Thread | None) -> list[str]:
    raw_module_settings = thread.module_settings if thread else None
    module_settings = coerce_thread_module_settings(cast(Mapping[str, object] | None, raw_module_settings))
    return list(module_settings.docusafe_file_ids)


def load_accessible_docusafe_file_ids(user_id: str, file_ids: list[str] | None = None) -> list[str]:
    if file_ids is None:
        return list(DocusafeAccessService.get_accessible_file_ids(user_id))
    return list(DocusafeAccessService.get_accessible_file_ids(user_id, file_ids))


def load_user_public_details(user_id: str) -> dict[str, object] | None:
    user = UserMaster.objects.filter(id=user_id).only("first_name", "last_name").first()
    if not user:
        return None

    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "User"
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": full_name,
    }


def load_user_profile(user_id: str) -> dict[str, object] | None:
    user = (
        UserMaster.objects.filter(id=user_id)
        .only(
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "is_profile_updated",
        )
        .first()
    )
    if not user:
        return None

    return {
        "full_name": " ".join(filter(None, [user.first_name, user.last_name])) or "Not set",
        "dob": user.date_of_birth.strftime("%B %d, %Y") if user.date_of_birth else "Not set",
        "gender": user.gender or "Not set",
        "is_profile_complete": user.is_profile_updated,
    }


def load_family_data(user_id: str) -> list[dict[str, Any]]:
    joined_family_ids = FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.JOINED).values_list(
        "family_id", flat=True
    )

    families = (
        Family.objects.filter(id__in=joined_family_ids, is_active=True)
        .select_related("owner")
        .annotate(
            joined_count=Count("members", filter=Q(members__status=FamilyMember.Status.JOINED), distinct=True),
            invited_count=Count("members", filter=Q(members__status=FamilyMember.Status.INVITED), distinct=True),
        )
    )

    family_data = []
    for family in families:
        is_owner = str(family.owner_id) == user_id
        family_data.append(
            {
                "id": str(family.id),
                "name": family.name,
                "role": "Owner" if is_owner else "Member",
                "joined_count": family.joined_count,
                "invited_count": family.invited_count,
            }
        )

    return family_data


def load_family_members(family_id: str, user_id: str) -> dict[str, Any]:
    family = Family.objects.filter(id=family_id, is_active=True).first()
    if not family:
        return {"status": "family_not_found"}

    is_member = FamilyMember.objects.filter(
        family=family,
        user_id=user_id,
        status=FamilyMember.Status.JOINED,
    ).exists()
    if not is_member:
        return {"status": "access_denied"}

    statuses = [FamilyMember.Status.JOINED, FamilyMember.Status.INVITED]
    if str(family.owner_id) != user_id:
        statuses = [FamilyMember.Status.JOINED]

    members = (
        FamilyMember.objects.filter(family=family, status__in=statuses)
        .select_related("user")
        .exclude(status=FamilyMember.Status.REMOVED)
    )

    member_data = []
    for member in members:
        name = (
            " ".join(filter(None, [member.user.first_name, member.user.last_name])) or member.email
            if member.user
            else member.email
        )
        relation_display = member.get_relation_display() if member.relation else ""
        member_data.append(
            {
                "name": name,
                "email": member.email,
                "relation": relation_display,
                "role": member.role.capitalize(),
                "status": member.status.capitalize(),
            }
        )

    return {"status": "ok", "family_name": family.name, "members": member_data}


def load_pending_invitations(user_id: str) -> list[dict[str, Any]]:
    pending = FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.INVITED).select_related(
        "family",
        "invited_by",
    )

    invitation_data = []
    for invitation in pending:
        inviter_name = "Someone"
        if invitation.invited_by:
            inviter_name = (
                " ".join(filter(None, [invitation.invited_by.first_name, invitation.invited_by.last_name]))
                or invitation.invited_by.email
            )

        invitation_data.append(
            {
                "family_id": str(invitation.family_id),
                "family_name": invitation.family.name,
                "invited_by": inviter_name,
                "relation": invitation.get_relation_display() if invitation.relation else None,
            }
        )

    return invitation_data


def find_family_member_matches(user_id: str, query: str) -> FindFamilyMemberMatchesResult:
    joined_family_ids = list(
        FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.JOINED).values_list(
            "family_id",
            flat=True,
        )
    )
    if not joined_family_ids:
        return {"joined_family_ids": [], "matches": []}

    normalized_query = query.lower()
    members = (
        FamilyMember.objects.filter(
            family_id__in=joined_family_ids,
            status__in=[FamilyMember.Status.JOINED, FamilyMember.Status.INVITED],
        )
        .select_related("family", "user")
        .exclude(status=FamilyMember.Status.REMOVED)
    )

    matches = []
    for member in members:
        name = ""
        if member.user:
            name = " ".join(filter(None, [member.user.first_name, member.user.last_name]))

        display_name = name or member.email
        relation_raw = member.relation or ""
        relation_display = member.get_relation_display() if member.relation else ""

        if (
            normalized_query in display_name.lower()
            or normalized_query in relation_raw.lower()
            or normalized_query in relation_display.lower()
            or normalized_query in member.email.lower()
        ):
            matches.append(
                {
                    "name": display_name,
                    "relation": relation_display,
                    "family": member.family.name,
                    "status": member.status.capitalize(),
                }
            )

    return {"joined_family_ids": joined_family_ids, "matches": matches}


def load_close_group_members(user_id: str) -> list[CloseGroupMemberData] | None:
    close_group = CloseGroup.objects.filter(owner_id=user_id).first()
    if not close_group:
        return None

    members = (
        CloseGroupMember.objects.filter(
            close_group=close_group,
            status__in=[CloseGroupMember.Status.JOINED, CloseGroupMember.Status.INVITED],
        )
        .select_related("user")
        .exclude(status=CloseGroupMember.Status.REMOVED)
    )

    member_data = []
    for member in members:
        name = (
            " ".join(filter(None, [member.user.first_name, member.user.last_name])) or member.email
            if member.user
            else member.email
        )
        member_data.append(
            {
                "name": name,
                "email": member.email,
                "status": member.status.capitalize(),
            }
        )

    return member_data


def build_network_summary_data(user_id: str) -> dict[str, Any]:
    user = (
        UserMaster.objects.filter(id=user_id)
        .only("first_name", "last_name", "date_of_birth", "gender", "is_profile_updated")
        .first()
    )
    if not user:
        return {"status": "user_not_found"}

    full_name = " ".join(filter(None, [user.first_name, user.last_name])) or "Not set"
    dob = user.date_of_birth.strftime("%B %d, %Y") if user.date_of_birth else "Not set"

    joined_family_ids = list(
        FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.JOINED).values_list(
            "family_id",
            flat=True,
        )
    )
    families = (
        Family.objects.filter(id__in=joined_family_ids, is_active=True)
        .select_related("owner")
        .only("id", "name", "owner_id")
    )

    family_data = []
    for family in families:
        family_data.append(
            {
                "name": family.name,
                "role": "Owner" if str(family.owner_id) == user_id else "Member",
            }
        )

    close_group = CloseGroup.objects.filter(owner_id=user_id).first()
    close_group_names = []
    if close_group:
        members = (
            CloseGroupMember.objects.filter(close_group=close_group, status=CloseGroupMember.Status.JOINED)
            .select_related("user")
            .only("user__first_name", "user__last_name", "email")
        )
        for member in members:
            close_group_names.append(
                " ".join(filter(None, [member.user.first_name, member.user.last_name])) if member.user else member.email
            )

    return {
        "status": "ok",
        "full_name": full_name,
        "dob": dob,
        "profile_complete": user.is_profile_updated,
        "families": family_data,
        "close_group_names": close_group_names,
    }


def load_network_insights(user_id: str) -> dict:
    user = UserMaster.objects.filter(id=user_id).only("is_profile_updated").first()
    if not user:
        return {"status": "user_not_found"}

    joined_family_ids = list(
        FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.JOINED).values_list(
            "family_id",
            flat=True,
        )
    )
    families_owned = Family.objects.filter(owner_id=user_id, is_active=True).count()
    received_pending = FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.INVITED).count()
    owned_families = Family.objects.filter(owner_id=user_id, is_active=True).values_list("id", flat=True)
    sent_pending = FamilyMember.objects.filter(
        family_id__in=owned_families,
        status=FamilyMember.Status.INVITED,
    ).count()

    close_group = CloseGroup.objects.filter(owner_id=user_id).first()
    close_group_joined = 0
    close_group_pending = 0
    if close_group:
        close_group_joined = CloseGroupMember.objects.filter(
            close_group=close_group,
            status=CloseGroupMember.Status.JOINED,
        ).count()
        close_group_pending = CloseGroupMember.objects.filter(
            close_group=close_group,
            status=CloseGroupMember.Status.INVITED,
        ).count()

    return {
        "status": "ok",
        "profile_complete": user.is_profile_updated,
        "families_joined": len(joined_family_ids),
        "families_owned": families_owned,
        "received_pending_invites": received_pending,
        "sent_pending_invites": sent_pending,
        "close_group_joined": close_group_joined,
        "close_group_pending": close_group_pending,
    }


def load_upcoming_birthdays(user_id: str, days_ahead: int) -> UpcomingBirthdaysResult:
    today = date.today()
    joined_family_ids = list(
        FamilyMember.objects.filter(user_id=user_id, status=FamilyMember.Status.JOINED).values_list(
            "family_id",
            flat=True,
        )
    )
    family_user_ids = set(
        FamilyMember.objects.filter(
            family_id__in=joined_family_ids,
            status=FamilyMember.Status.JOINED,
        )
        .exclude(user_id=user_id)
        .exclude(user_id__isnull=True)
        .values_list("user_id", flat=True)
    )

    close_group = CloseGroup.objects.filter(owner_id=user_id).first()
    close_group_user_ids = set()
    if close_group:
        close_group_user_ids = set(
            CloseGroupMember.objects.filter(close_group=close_group, status=CloseGroupMember.Status.JOINED)
            .exclude(user_id__isnull=True)
            .values_list("user_id", flat=True)
        )

    all_user_ids = family_user_ids | close_group_user_ids
    if not all_user_ids:
        return {"connected_users": False, "birthdays": []}

    users_with_dob = UserMaster.objects.filter(id__in=all_user_ids, date_of_birth__isnull=False).only(
        "first_name",
        "last_name",
        "date_of_birth",
    )

    upcoming = []
    for user in users_with_dob:
        dob = user.date_of_birth
        try:
            birthday_this_year = dob.replace(year=today.year)
        except ValueError:
            birthday_this_year = date(today.year, 3, 1)

        delta = (birthday_this_year - today).days
        if delta < 0:
            try:
                birthday_this_year = dob.replace(year=today.year + 1)
            except ValueError:
                birthday_this_year = date(today.year + 1, 3, 1)
            delta = (birthday_this_year - today).days

        if 0 <= delta <= days_ahead:
            upcoming.append(
                {
                    "delta": delta,
                    "name": " ".join(filter(None, [user.first_name, user.last_name])) or "Unknown",
                    "date": str(birthday_this_year),
                    "display_date": birthday_this_year.strftime("%B %d"),
                }
            )

    upcoming.sort(key=lambda birthday: birthday["delta"])
    return {"connected_users": True, "birthdays": upcoming}

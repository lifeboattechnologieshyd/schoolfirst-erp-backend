from rest_framework import serializers

from apps.calendar.services.access_policy import (
    validate_access_configuration,
    validate_access_ids_ownership,
    validate_access_user_ids,
)
from apps.core.models.family import Family, FamilyMember
from apps.core.services.social_graph_service import SocialGraphService

_MAX_UNIFIED_CALENDAR_RANGE_DAYS = 31


class LocationSerializer(serializers.Serializer):
    """Shared location structure used by EventWriteSerializer and TaskWriteSerializer.
    Owned here so neither event.py nor task.py imports from the other.
    """

    name = serializers.CharField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    place_id = serializers.CharField(required=False, allow_null=True)
    maps_url = serializers.CharField(required=False, allow_null=True)


def validate_access_fields(attrs: dict) -> dict:
    """
    Shared cross-field access-control validation for EventWriteSerializer and
    TaskWriteSerializer.  Raises ValidationError when access_type constraints
    are violated; returns attrs unchanged on success.
    """
    error = validate_access_configuration(
        access_type=attrs.get("access_type"),
        access_family_ids=attrs.get("access_family_ids"),
        access_close_group_ids=attrs.get("access_close_group_ids"),
        access_user_ids=attrs.get("access_user_ids"),
    )
    if error:
        raise serializers.ValidationError(error)
    return attrs


def validate_access_membership(user, attrs: dict) -> None:
    """Verify that access IDs are within the requesting user's permitted scope.

    Step 1 — Ownership: access_family_ids must be families the user is in;
              access_close_group_ids must be close groups the user owns.
    Step 2 — Reachability: access_user_ids must be reachable via the user's
              social graph (families or own close group members).

    Raises ValidationError for any out-of-scope ID.
    """
    family_ids: list[str] = attrs.get("access_family_ids") or []
    close_group_ids: list[str] = attrs.get("access_close_group_ids") or []
    user_ids: list[str] = attrs.get("access_user_ids") or []

    if not family_ids and not close_group_ids and not user_ids:
        return

    # Step 1 — ownership checks
    if family_ids or close_group_ids:
        member_family_ids: set[str] = {
            str(fid)
            for fid in FamilyMember.objects.filter(
                user=user,
                status=FamilyMember.Status.JOINED,
            ).values_list("family_id", flat=True)
        }
        owned_family_ids: set[str] = {
            str(fid) for fid in Family.objects.filter(owner=user).values_list("id", flat=True)
        }
        creator_family_ids = list(member_family_ids | owned_family_ids)
        creator_close_group_ids = list(SocialGraphService.get_owned_close_group_ids(user))

        ownership_error = validate_access_ids_ownership(
            access_family_ids=family_ids,
            access_close_group_ids=close_group_ids,
            creator_family_ids=creator_family_ids,
            creator_close_group_ids=creator_close_group_ids,
        )
        if ownership_error:
            raise serializers.ValidationError(ownership_error)

    # Step 2 — reachability of specific user IDs
    if user_ids:
        scope = SocialGraphService.build_visibility_scope(user)
        allowed: set[str] = set(scope.access_user_id_candidates)
        reachability_error = validate_access_user_ids(
            access_user_ids=user_ids,
            allowed_user_ids=allowed,
        )
        if reachability_error:
            raise serializers.ValidationError(reachability_error)


class CalendarRequestSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["to_date"] < attrs["from_date"]:
            raise serializers.ValidationError({"to_date": "to_date must be on or after from_date."})
        if (attrs["to_date"] - attrs["from_date"]).days + 1 > _MAX_UNIFIED_CALENDAR_RANGE_DAYS:
            raise serializers.ValidationError({"to_date": "Date range cannot exceed 31 days."})
        return attrs


class CalendarDayRequestSerializer(serializers.Serializer):
    date = serializers.DateField()

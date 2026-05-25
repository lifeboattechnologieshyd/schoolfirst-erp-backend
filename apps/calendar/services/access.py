from apps.calendar.services.access_policy import CalendarAccessPolicy, CalendarAccessScope
from apps.core.services.social_graph_service import SocialGraphService


class AccessResolver:
    """
    Resolves the access-control filter for Events and Tasks.

    Usage:
        resolver = AccessResolver(user)
        qs = Event.objects.filter(resolver.build_access_filter())
    """

    def __init__(self, user):
        self.user = user
        self._scope = None

    def _get_scope(self):
        if self._scope is None:
            self._scope = SocialGraphService.build_visibility_scope(self.user)
        return self._scope

    def get_user_family_ids(self) -> list[str]:
        """Return UUID strings of Families the user belongs to as a JOINED member."""
        return self._get_scope().family_ids

    def get_close_group_membership_ids(self) -> list[str]:
        """
        Return UUIDs (as strings) of CloseGroups the requesting user belongs to
        with JOINED status.
        """
        return self._get_scope().close_group_membership_ids

    def get_access_user_id_candidates(self) -> list[str]:
        """Return UUID strings this creator may target with access_user_ids."""
        return self._get_scope().access_user_id_candidates

    def build_access_scope(self) -> CalendarAccessScope:
        return CalendarAccessScope(
            user_id=self.user.id,
            family_ids=tuple(self.get_user_family_ids()),
            close_group_membership_ids=tuple(self.get_close_group_membership_ids()),
            access_user_id_candidates=tuple(self.get_access_user_id_candidates()),
        )

    def build_access_filter(self):
        """
        Return a Q object that, when applied to an Event or Task queryset,
        keeps only records visible to the current user.

        Visibility rules:
          - always visible: records the user created
          - only_me: only creator sees it (handled by the creator rule above)
          - all/mixed: family IDs or close group membership IDs overlap,
            OR user is in access_user_ids
        """
        return CalendarAccessPolicy.build_filter(self.build_access_scope())


def assert_is_creator(user, obj, id_field: str = "creator_id") -> None:
    """Raise PermissionError if user is not the creator/owner of obj."""
    if str(getattr(obj, id_field)) != str(user.id):
        raise PermissionError("Only the creator can perform this action.")

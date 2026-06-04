from rest_framework.permissions import BasePermission

from shared.helpers.rbac import (
    get_user_roles,
    has_permission,
)


class HasRole(BasePermission):

    def has_permission(self, request, view):

        required_roles = getattr(
            view,
            "required_roles",
            []
        )

        if not required_roles:
            return True

        user_roles = get_user_roles(request.user)

        return any(
            role in user_roles
            for role in required_roles
        )


class HasPermission(BasePermission):

    def has_permission(self, request, view):

        required_permission = getattr(
            view,
            "required_permission",
            None,
        )

        if not required_permission:
            return True

        return has_permission(
            request.user,
            required_permission,
        )
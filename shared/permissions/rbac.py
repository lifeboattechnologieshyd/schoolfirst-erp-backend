from rest_framework.permissions import BasePermission

from apps.school.models import School
from shared.helpers.rbac import (
    get_user_roles,
    has_permission, get_user_permissions,
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


# class HasPermission(BasePermission):
#
#     def has_permission(self, request, view):
#
#         required_permission = getattr(
#             view,
#             "required_permission",
#             None,
#         )
#
#         if not required_permission:
#             return True
#
#         return has_permission(
#             request.user,
#             required_permission,
#         )

class HasPermission(BasePermission):

    def has_permission(self, request, view):

        school_id = request.headers.get("X-School-Id")

        request.current_school = None

        if school_id:
            request.current_school = School.objects.filter(
                id=school_id,
            ).first()

        request.roles = get_user_roles(
            user=request.user,
            school_id=school_id,
        )

        request.permissions = get_user_permissions(
            user=request.user,
            school_id=school_id,
        )

        required_permission = getattr(
            view,
            "required_permission",
            None,
        )

        if not required_permission:
            return True

        return required_permission in request.permissions
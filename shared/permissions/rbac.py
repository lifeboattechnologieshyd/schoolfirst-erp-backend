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

class HasPermission(BasePermission):

    def has_permission(self, request, view):

        print("=" * 80)
        print("HasPermission Called")
        print("User :", request.user)
        print("School :", getattr(request, "school", None))
        print("School ID :", getattr(request, "school_id", None))

        required_permission = getattr(
            view,
            "required_permission",
            None,
        )

        print("Required Permission :", required_permission)

        result = has_permission(
            user=request.user,
            permission_name=required_permission,
            school_id=request.school_id,
        )

        print("Permission Result :", result)
        print("=" * 80)

        return result

# class HasPermission(BasePermission):
#
#     def has_permission(self, request, view):
#
#         print("=" * 80)
#         print("HasPermission Called")
#         print("User :", request.user)
#         print("Is Authenticated :", request.user.is_authenticated)
#
#         school_id = request.headers.get(
#             "X-School-Id",
#         )
#
#         print("X-School-Id :", school_id)
#
#         request.current_school = None
#
#         if school_id:
#
#             request.current_school = School.objects.filter(
#                 id=school_id,
#             ).first()
#
#         print("Current School :", request.current_school)
#
#         request.roles = get_user_roles(
#             user=request.user,
#             school_id=school_id,
#         )
#
#         print("Roles :", request.roles)
#
#         request.permissions = get_user_permissions(
#             user=request.user,
#             school_id=school_id,
#         )
#
#         print("Permissions :", request.permissions)
#
#         required_permission = getattr(
#             view,
#             "required_permission",
#             None,
#         )
#
#         print("Required Permission :", required_permission)
#
#         if not required_permission:
#
#             print("No Permission Required")
#             print("=" * 80)
#
#             return True
#
#         has_access = (
#             required_permission
#             in request.permissions
#         )
#
#         print("Has Access :", has_access)
#         print("=" * 80)
#
#         return has_access
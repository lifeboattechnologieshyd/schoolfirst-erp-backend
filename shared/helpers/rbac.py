from django.core.cache import cache
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.core.models import (
    UserPermissions,
    UserRoles,
)
from shared.enums.roles import RolesEnum

CACHE_TIMEOUT = 300


def get_user_roles(user, school_id=None):

    print("=" * 80)
    print("get_user_roles() called")
    print("User :", user)
    print("User ID :", user.id)
    print("School ID :", school_id)

    cache_key = f"user_roles:{user.id}:{school_id}"

    print("Cache Key :", cache_key)

    roles = cache.get(cache_key)

    print("Roles From Cache :", roles)

    if roles is None:

        print("Cache Miss")

        queryset = UserRoles.objects.filter(
            user=user,
        )

        print(
            "UserRoles Before Filter :",
            list(
                queryset.values(
                    "role__role_name",
                    "school_id",
                )
            ),
        )

        if school_id:

            print("Applying School Filter")

            queryset = queryset.filter(
                Q(school_id=school_id)
                | Q(school__isnull=True)
            )

        else:

            print("Applying Global Role Filter")

            queryset = queryset.filter(
                school__isnull=True,
            )

        print(
            "UserRoles After Filter :",
            list(
                queryset.values(
                    "role__role_name",
                    "school_id",
                )
            ),
        )

        roles = list(
            queryset.values_list(
                "role__role_name",
                flat=True,
            ).distinct()
        )

        print("Roles Retrieved :", roles)

        cache.set(
            cache_key,
            roles,
            CACHE_TIMEOUT,
        )

        print("Roles Cached")

    else:

        print("Cache Hit")

    print("Returning Roles :", roles)
    print("=" * 80)

    return roles


def has_role(
    user,
    role_name,
    school_id=None,
):

    return role_name in get_user_roles(
        user=user,
        school_id=school_id,
    )


def get_user_permissions(
    user,
    school_id=None,
):
    """
    Returns all permissions assigned to the user.

    Includes:
    - Role permissions
    - Direct permissions

    school_id=None:
        GLOBAL permissions only.

    school_id=<id>:
        GLOBAL permissions + School permissions.
    """

    cache_key = (
        f"user_permissions:{user.id}:{school_id}"
    )

    permissions = cache.get(cache_key)

    if permissions is None:

        role_queryset = UserRoles.objects.filter(
            user=user
        )

        direct_queryset = UserPermissions.objects.filter(
            user=user
        )

        if school_id:

            role_queryset = role_queryset.filter(
                Q(school_id=school_id)
                | Q(school__isnull=True)
            )

            direct_queryset = direct_queryset.filter(
                Q(school_id=school_id)
                | Q(school__isnull=True)
            )

        else:

            role_queryset = role_queryset.filter(
                school__isnull=True
            )

            direct_queryset = direct_queryset.filter(
                school__isnull=True
            )

        role_permissions = (
            role_queryset.values_list(
                "role__role_permissions_for_role__permission__permission_name",
                flat=True,
            )
        )

        direct_permissions = (
            direct_queryset.values_list(
                "permission__permission_name",
                flat=True,
            )
        )

        permissions = list(
            set(
                list(role_permissions)
                + list(direct_permissions)
            )
        )

        cache.set(
            cache_key,
            permissions,
            CACHE_TIMEOUT,
        )

    return permissions


def has_permission(
    user,
    permission_name,
    school_id=None,
):
    """
    Returns True if user has permission.

    SUPERADMIN bypasses all permission checks.
    """

    if has_role(
        user=user,
        role_name=RolesEnum.SUPERADMIN,
        school_id=None,
    ):
        return True

    permissions = get_user_permissions(
        user=user,
        school_id=school_id,
    )

    return permission_name in permissions


def check_permission(
    request,
    permission_name,
    school_id=None,
):
    """
    Raise PermissionDenied if permission is missing.
    """

    if not has_permission(
        request.user,
        permission_name,
        school_id,
    ):
        raise PermissionDenied(
            detail="You don't have permission to perform this action."
        )


def clear_user_access_cache(
    user,
    school_id=None,
):
    """
    Clear RBAC cache.

    Call after:
    - Role assignment
    - Role removal
    - Permission assignment
    - Permission removal
    """

    cache.delete(
        f"user_roles:{user.id}:{school_id}"
    )

    cache.delete(
        f"user_permissions:{user.id}:{school_id}"
    )
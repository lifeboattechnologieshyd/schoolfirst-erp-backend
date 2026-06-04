from django.core.cache import cache

from apps.core.models import (
    UserRoles,
    UserPermissions,
)

CACHE_TIMEOUT = 300


def get_user_roles(user, school_id=None):

    cache_key = f"user_roles:{user.id}:{school_id}"

    roles = cache.get(cache_key)

    if roles is None:

        queryset = UserRoles.objects.filter(
            user=user
        )

        if school_id:
            queryset = queryset.filter(
                school_id=school_id
            )

        roles = list(
            queryset.values_list(
                "role__role_name",
                flat=True,
            )
        )

        cache.set(
            cache_key,
            roles,
            CACHE_TIMEOUT,
        )

    return roles


def has_role(user, role_name, school_id=None):

    return role_name in get_user_roles(
        user=user,
        school_id=school_id,
    )


def get_user_permissions(user, school_id=None):

    cache_key = f"user_permissions:{user.id}:{school_id}"

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
                school_id=school_id,
            )

            direct_queryset = direct_queryset.filter(
                school_id=school_id,
            )

        role_permissions = role_queryset.values_list(
            "role__role_permissions_for_role__permission__permission_name",
            flat=True,
        )

        direct_permissions = direct_queryset.values_list(
            "permission__permission_name",
            flat=True,
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


def has_permission(user, permission_name, school_id=None):

    return permission_name in get_user_permissions(
        user=user,
        school_id=school_id,
    )


def clear_user_access_cache(user, school_id=None):

    cache.delete(
        f"user_roles:{user.id}:{school_id}"
    )

    cache.delete(
        f"user_permissions:{user.id}:{school_id}"
    )
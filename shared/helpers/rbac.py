from django.core.cache import cache
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.core.models import (
    UserPermissions,
    UserRoles,
)
from shared.enums.roles import RolesEnum
from shared.utils.logger import auth_logger

CACHE_TIMEOUT = 300


def get_user_roles(user, school_id=None):

    cache_key = f"user_roles:{user.id}:{school_id}"

    auth_logger.info(
        "user_roles_fetch_started",
        user_id=str(user.id),
        school_id=str(school_id) if school_id else None,
    )

    try:

        roles = cache.get(cache_key)

        if roles is not None:

            auth_logger.info(
                "user_roles_cache_hit",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                role_count=len(roles),
            )

            return roles

        auth_logger.info(
            "user_roles_cache_miss",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
        )

        queryset = UserRoles.objects.filter(user=user)

        if school_id:

            queryset = queryset.filter(
                Q(school_id=school_id)
                | Q(school__isnull=True)
            )

        roles = list(
            queryset.values_list(
                "role__role_name",
                flat=True,
            ).distinct()
        )

        cache.set(
            cache_key,
            roles,
            CACHE_TIMEOUT,
        )

        auth_logger.info(
            "user_roles_fetched",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            role_count=len(roles),
            roles=roles,
        )

        return roles

    except Exception as e:

        auth_logger.exception(
            "user_roles_fetch_failed",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            error=str(e),
        )

        raise


def has_role(user, role_name, school_id=None):

    auth_logger.info(
        "role_check_started",
        user_id=str(user.id),
        school_id=str(school_id) if school_id else None,
        required_role=str(role_name),
    )

    try:

        roles = get_user_roles(
            user=user,
            school_id=school_id,
        )

        result = role_name in roles

        if result:

            auth_logger.info(
                "role_check_allowed",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                required_role=str(role_name),
            )

        else:

            auth_logger.warning(
                "role_check_denied",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                required_role=str(role_name),
                user_roles=roles,
            )

        return result

    except Exception as e:

        auth_logger.exception(
            "role_check_failed",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            required_role=str(role_name),
            error=str(e),
        )

        raise


def get_user_permissions(user, school_id=None):

    cache_key = f"user_permissions:{user.id}:{school_id}"

    auth_logger.info(
        "user_permissions_fetch_started",
        user_id=str(user.id),
        school_id=str(school_id) if school_id else None,
    )

    try:

        permissions = cache.get(cache_key)

        if permissions is not None:

            auth_logger.info(
                "user_permissions_cache_hit",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                permission_count=len(permissions),
            )

            return permissions

        auth_logger.info(
            "user_permissions_cache_miss",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
        )

        role_queryset = UserRoles.objects.filter(user=user)

        direct_queryset = UserPermissions.objects.filter(user=user)

        if school_id:

            role_queryset = role_queryset.filter(
                Q(school_id=school_id)
                | Q(school__isnull=True)
            )

            direct_queryset = direct_queryset.filter(
                Q(school_id=school_id)
                | Q(school__isnull=True)
            )

        role_permissions = role_queryset.values_list(
            "role__role_permissions_for_role__permission__permission_name",
            flat=True,
        )
        auth_logger.info(
            "role_permissions_debug",
            roles=list(role_queryset.values_list("role__role_name", flat=True)),
            permissions=role_permissions,
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

        auth_logger.info(
            "user_permissions_fetched",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            permission_count=len(permissions),
        )

        return permissions

    except Exception as e:

        auth_logger.exception(
            "user_permissions_fetch_failed",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            error=str(e),
        )

        raise


def has_permission(user, permission_name, school_id=None):

    auth_logger.info(
        "user_permission_check_started",
        user_id=str(user.id),
        school_id=str(school_id) if school_id else None,
        required_permission=permission_name,
    )

    try:

        is_superadmin = has_role(
            user=user,
            role_name=RolesEnum.SUPERADMIN,
        )

        if is_superadmin:

            auth_logger.info(
                "user_permission_check_allowed",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                required_permission=permission_name,
                reason="superadmin_bypass",
            )

            return True

        permissions = get_user_permissions(
            user=user,
            school_id=school_id,
        )

        result = permission_name in permissions

        if result:

            auth_logger.info(
                "user_permission_check_allowed",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                required_permission=permission_name,
                reason="permission_assigned",
            )

        else:

            auth_logger.warning(
                "user_permission_check_denied",
                user_id=str(user.id),
                school_id=str(school_id) if school_id else None,
                required_permission=permission_name,
                permission_count=len(permissions),
                reason="permission_not_assigned",
            )

        return result

    except Exception as e:

        auth_logger.exception(
            "user_permission_check_failed",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            required_permission=permission_name,
            error=str(e),
        )

        raise


def check_permission(request, permission_name, school_id=None):

    auth_logger.info(
        "explicit_permission_check_started",
        user_id=str(request.user.id),
        school_id=str(school_id) if school_id else None,
        required_permission=permission_name,
        request_method=request.method,
        request_path=request.path,
    )

    try:

        result = has_permission(
            user=request.user,
            permission_name=permission_name,
            school_id=school_id,
        )

        if not result:

            auth_logger.warning(
                "explicit_permission_check_denied",
                user_id=str(request.user.id),
                school_id=str(school_id) if school_id else None,
                required_permission=permission_name,
                request_method=request.method,
                request_path=request.path,
            )

            raise PermissionDenied(
                detail="You don't have permission to perform this action."
            )

        auth_logger.info(
            "explicit_permission_check_allowed",
            user_id=str(request.user.id),
            school_id=str(school_id) if school_id else None,
            required_permission=permission_name,
        )

        return True

    except PermissionDenied:
        raise

    except Exception as e:

        auth_logger.exception(
            "explicit_permission_check_failed",
            user_id=str(request.user.id),
            school_id=str(school_id) if school_id else None,
            required_permission=permission_name,
            error=str(e),
        )

        raise


def clear_user_access_cache(user, school_id=None):

    role_cache_key = f"user_roles:{user.id}:{school_id}"
    permission_cache_key = f"user_permissions:{user.id}:{school_id}"

    auth_logger.info(
        "user_access_cache_clear_started",
        user_id=str(user.id),
        school_id=str(school_id) if school_id else None,
    )

    try:

        cache.delete_many([
            role_cache_key,
            permission_cache_key,
        ])

        auth_logger.info(
            "user_access_cache_cleared",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
        )

    except Exception as e:

        auth_logger.exception(
            "user_access_cache_clear_failed",
            user_id=str(user.id),
            school_id=str(school_id) if school_id else None,
            error=str(e),
        )

        raise
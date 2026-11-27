from django.core.cache import cache
from rest_framework.permissions import BasePermission

from apps.core.models import UserRoles, UserPermissions, RolePermissions
from apps.school.models import School
from shared.helpers.rbac import (
    get_user_roles,
    has_permission, get_user_permissions, CACHE_TIMEOUT,
)
from shared.utils.logger import auth_logger


class HasRole(BasePermission):

    def has_permission(self, request, view):

        required_roles = getattr(
            view,
            "required_roles",
            [],
        )

        auth_logger.info(
            "role_permission_check_started",
            user_id=str(request.user.id) if request.user.is_authenticated else None,
            required_roles=required_roles,
            view_name=view.__class__.__name__,
            request_method=request.method,
            request_path=request.path,
        )

        if not required_roles:

            auth_logger.info(
                "role_permission_check_allowed",
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                view_name=view.__class__.__name__,
                reason="no_required_roles",
            )

            return True

        try:

            user_roles = get_user_roles(
                request.user
            )

            result = any(
                role in user_roles
                for role in required_roles
            )

            if result:

                auth_logger.info(
                    "role_permission_check_allowed",
                    user_id=str(request.user.id),
                    view_name=view.__class__.__name__,
                    required_roles=required_roles,
                    user_roles=list(user_roles),
                )

            else:

                auth_logger.warning(
                    "role_permission_check_denied",
                    user_id=str(request.user.id),
                    view_name=view.__class__.__name__,
                    required_roles=required_roles,
                    user_roles=list(user_roles),
                    reason="required_role_not_assigned",
                )

            return result

        except Exception as e:

            auth_logger.exception(
                "role_permission_check_failed",
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                view_name=view.__class__.__name__,
                required_roles=required_roles,
                error=str(e),
            )

            return False


class HasPermission(BasePermission):

    def has_permission(self, request, view):

        required_permission = getattr(
            view,
            "required_permission",
            None,
        )

        method_permissions = getattr(
            view,
            "required_permissions",
            None,
        )

        if method_permissions:
            required_permission = method_permissions.get(request.method)

        school = getattr(
            request,
            "school",
            None,
        )

        school_id = getattr(
            request,
            "school_id",
            None,
        )

        auth_logger.info(
            "permission_check_started",
            user_id=str(request.user.id) if request.user.is_authenticated else None,
            school_id=str(school_id) if school_id else None,
            required_permission=required_permission,
            view_name=view.__class__.__name__,
            request_method=request.method,
            request_path=request.path,
        )

        if not required_permission:

            auth_logger.warning(
                "permission_check_denied",
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                view_name=view.__class__.__name__,
                reason="required_permission_not_configured",
            )

            return False

        try:

            is_superadmin = UserRoles.objects.filter(
                user=request.user,
                role__role_name="SUPERADMIN",
            ).exists()

            if is_superadmin:

                auth_logger.info(
                    "permission_check_allowed",
                    user_id=str(request.user.id),
                    required_permission=required_permission,
                    view_name=view.__class__.__name__,
                    reason="superadmin",
                )

                return True

            if school is None or school_id is None:

                auth_logger.warning(
                    "permission_check_denied",
                    user_id=str(request.user.id),
                    required_permission=required_permission,
                    view_name=view.__class__.__name__,
                    reason="school_context_not_found",
                )

                return False

            result = has_permission(
                user=request.user,
                permission_name=required_permission,
                school_id=school_id,
            )

            if result:

                auth_logger.info(
                    "permission_check_allowed",
                    user_id=str(request.user.id),
                    school_id=str(school_id),
                    required_permission=required_permission,
                    view_name=view.__class__.__name__,
                )

            else:

                auth_logger.warning(
                    "permission_check_denied",
                    user_id=str(request.user.id),
                    school_id=str(school_id),
                    required_permission=required_permission,
                    view_name=view.__class__.__name__,
                    reason="permission_not_assigned",
                )

            return result

        except Exception as e:

            auth_logger.exception(
                "permission_check_failed",
                user_id=str(request.user.id) if request.user.is_authenticated else None,
                school_id=str(school_id) if school_id else None,
                required_permission=required_permission,
                view_name=view.__class__.__name__,
                error=str(e),
            )

            return False

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


def get_global_permissions(user):
    """
    Permissions from roles / direct grants NOT tied to a school
    (school = NULL), e.g. CONTENT_MANAGER. Used for global APIs
    and the superadmin panel menu.

    Do NOT use get_user_permissions(user, None) for this: with no
    school_id it returns permissions from ALL roles, including
    school-level ones.
    """

    cache_key = f"user_permissions:{user.id}:global"

    permissions = cache.get(cache_key)

    if permissions is not None:
        return permissions

    role_ids = UserRoles.objects.filter(
        user=user,
        school__isnull=True,
        is_deleted=False,
    ).values("role_id")

    role_permissions = RolePermissions.objects.filter(
        role_id__in=role_ids,
        is_deleted=False,
    ).values_list(
        "permission__permission_name",
        flat=True,
    )

    direct_permissions = UserPermissions.objects.filter(
        user=user,
        school__isnull=True,
        is_deleted=False,
    ).values_list(
        "permission__permission_name",
        flat=True,
    )

    permissions = list(
        set(role_permissions) | set(direct_permissions)
    )

    cache.set(
        cache_key,
        permissions,
        CACHE_TIMEOUT,
    )

    return permissions
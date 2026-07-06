from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.core.models import Modules, Permissions, Roles, RolePermissions, UserMaster, UserRoles, UserPermissions
from shared.mixins import CustomResponse
from shared.permissions import HasRole
from shared.enums.roles import RolesEnum
from shared.utils.logger import application_logger, audit_logger


class ModuleListCreateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        application_logger.info(
            "modules_list_started",
            user_id=str(request.user.id),
        )

        modules = Modules.objects.all().order_by(
            "module_name"
        )

        data = [
            {
                "id": str(module.id),
                "module_name": module.module_name,
                "parent": (
                    str(module.parent_id)
                    if module.parent_id
                    else None
                ),
            }
            for module in modules
        ]

        application_logger.info(
            "modules_list_fetched",
            user_id=str(request.user.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data
        )

    def post(self, request):

        module_name = request.data.get(
            "module_name"
        )

        parent_id = request.data.get(
            "parent_id"
        )

        audit_logger.info(
            "module_create_started",
            performed_by=str(request.user.id),
            module_name=module_name,
            parent_id=parent_id,
        )

        if not module_name:

            audit_logger.warning(
                "module_create_failed",
                performed_by=str(request.user.id),
                reason="module_name_required",
            )

            return CustomResponse.errorResponse(
                description="module_name is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent = None

        if parent_id:

            parent = Modules.objects.filter(
                id=parent_id
            ).first()

            if not parent:

                audit_logger.warning(
                    "module_create_failed",
                    performed_by=str(request.user.id),
                    reason="parent_module_not_found",
                    parent_id=parent_id,
                )

                return CustomResponse.errorResponse(
                    description="Parent module not found.",
                    status=status.HTTP_404_NOT_FOUND,
                )

        module, created = Modules.objects.get_or_create(
            module_name=module_name,
            defaults={
                "parent": parent,
            },
        )

        if not created:

            audit_logger.warning(
                "module_create_failed",
                performed_by=str(request.user.id),
                reason="module_already_exists",
                module_id=str(module.id),
                module_name=module_name,
            )

            return CustomResponse.errorResponse(
                description="Module already exists.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        audit_logger.info(
            "module_created",
            performed_by=str(request.user.id),
            module_id=str(module.id),
            module_name=module.module_name,
            parent_id=(
                str(module.parent_id)
                if module.parent_id
                else None
            ),
        )

        return CustomResponse.successResponse(
            data={
                "id": str(module.id),
            },
            description="Module created successfully.",
            status=status.HTTP_201_CREATED,
        )
class PermissionListCreateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        application_logger.info(
            "permissions_list_started",
            user_id=str(request.user.id),
        )

        permissions = Permissions.objects.select_related(
            "module"
        )

        data = [
            {
                "id": str(permission.id),
                "permission_name": permission.permission_name,
                "module_id": str(permission.module.id),
                "module_name": permission.module.module_name,
            }
            for permission in permissions
        ]

        application_logger.info(
            "permissions_list_fetched",
            user_id=str(request.user.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data
        )

    def post(self, request):

        module_id = request.data.get(
            "module_id"
        )

        permission_name = request.data.get(
            "permission_name"
        )

        audit_logger.info(
            "permission_create_started",
            performed_by=str(request.user.id),
            module_id=module_id,
            permission_name=permission_name,
        )

        if not module_id or not permission_name:

            audit_logger.warning(
                "permission_create_failed",
                performed_by=str(request.user.id),
                reason="required_fields_missing",
                module_id=module_id,
            )

            return CustomResponse.errorResponse(
                description="module_id and permission_name are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        module = Modules.objects.filter(
            id=module_id
        ).first()

        if not module:

            audit_logger.warning(
                "permission_create_failed",
                performed_by=str(request.user.id),
                reason="module_not_found",
                module_id=module_id,
            )

            return CustomResponse.errorResponse(
                description="Module not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        permission, created = Permissions.objects.get_or_create(
            module=module,
            permission_name=permission_name,
        )

        if not created:

            audit_logger.warning(
                "permission_create_failed",
                performed_by=str(request.user.id),
                reason="permission_already_exists",
                permission_id=str(permission.id),
                module_id=str(module.id),
            )

            return CustomResponse.errorResponse(
                description="Permission already exists.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        audit_logger.info(
            "permission_created",
            performed_by=str(request.user.id),
            permission_id=str(permission.id),
            permission_name=permission.permission_name,
            module_id=str(module.id),
            module_name=module.module_name,
        )

        return CustomResponse.successResponse(
            data={
                "id": str(permission.id),
            },
            description="Permission created successfully.",
            status=status.HTTP_201_CREATED,
        )


class RoleListCreateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        application_logger.info(
            "roles_list_started",
            user_id=str(request.user.id),
        )

        roles = Roles.objects.all().order_by(
            "role_name"
        )

        data = [
            {
                "id": str(role.id),
                "role_name": role.role_name,
                "description": role.description,
            }
            for role in roles
        ]

        application_logger.info(
            "roles_list_fetched",
            user_id=str(request.user.id),
            total_count=len(data),
        )

        return CustomResponse.successResponse(
            data=data
        )

    def post(self, request):

        role_name = request.data.get(
            "role_name"
        )

        description = request.data.get(
            "description",
            "",
        )

        audit_logger.info(
            "role_create_started",
            performed_by=str(request.user.id),
            role_name=role_name,
        )

        if not role_name:

            audit_logger.warning(
                "role_create_failed",
                performed_by=str(request.user.id),
                reason="role_name_required",
            )

            return CustomResponse.errorResponse(
                description="role_name is required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        role, created = Roles.objects.get_or_create(
            role_name=role_name,
            defaults={
                "description": description,
            },
        )

        if not created:

            audit_logger.warning(
                "role_create_failed",
                performed_by=str(request.user.id),
                reason="role_already_exists",
                role_id=str(role.id),
                role_name=role_name,
            )

            return CustomResponse.errorResponse(
                description="Role already exists.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        audit_logger.info(
            "role_created",
            performed_by=str(request.user.id),
            role_id=str(role.id),
            role_name=role.role_name,
        )

        return CustomResponse.successResponse(
            data={
                "id": str(role.id),
            },
            description="Role created successfully.",
            status=status.HTTP_201_CREATED,
        )
class AssignPermissionsToRoleAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    @transaction.atomic
    def post(self, request, role_id):

        permission_ids = request.data.get(
            "permission_ids",
            [],
        )

        audit_logger.info(
            "role_permissions_assign_started",
            performed_by=str(request.user.id),
            role_id=str(role_id),
            requested_count=len(permission_ids),
        )

        role = Roles.objects.filter(
            id=role_id
        ).first()

        if not role:

            audit_logger.warning(
                "role_permissions_assign_failed",
                performed_by=str(request.user.id),
                reason="role_not_found",
                role_id=str(role_id),
            )

            return CustomResponse.errorResponse(
                description="Role not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        created_count = 0
        invalid_permission_ids = []

        for permission_id in permission_ids:

            permission = Permissions.objects.filter(
                id=permission_id
            ).first()

            if not permission:
                invalid_permission_ids.append(
                    str(permission_id)
                )
                continue

            _, created = RolePermissions.objects.get_or_create(
                role=role,
                permission=permission,
            )

            if created:
                created_count += 1

        audit_logger.info(
            "role_permissions_assigned",
            performed_by=str(request.user.id),
            role_id=str(role.id),
            role_name=role.role_name,
            requested_count=len(permission_ids),
            created_count=created_count,
            invalid_permission_ids=invalid_permission_ids,
        )

        return CustomResponse.successResponse(
            data={
                "created_count": created_count,
            },
            description="Permissions assigned successfully.",
        )

class AssignRoleToUserAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    @transaction.atomic
    def post(self, request):

        user_id = request.data.get(
            "user_id"
        )

        role_id = request.data.get(
            "role_id"
        )

        school_id = request.data.get(
            "school_id"
        )

        audit_logger.info(
            "user_role_assign_started",
            performed_by=str(request.user.id),
            target_user_id=user_id,
            role_id=role_id,
            school_id=school_id,
        )

        user = UserMaster.objects.filter(
            id=user_id
        ).first()

        if not user:

            audit_logger.warning(
                "user_role_assign_failed",
                performed_by=str(request.user.id),
                reason="user_not_found",
                target_user_id=user_id,
            )

            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        role = Roles.objects.filter(
            id=role_id
        ).first()

        if not role:

            audit_logger.warning(
                "user_role_assign_failed",
                performed_by=str(request.user.id),
                reason="role_not_found",
                target_user_id=str(user.id),
                role_id=role_id,
            )

            return CustomResponse.errorResponse(
                description="Role not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        user_role, created = UserRoles.objects.get_or_create(
            user=user,
            role=role,
            school_id=school_id,
        )

        from shared.helpers.rbac import clear_user_access_cache

        clear_user_access_cache(user)

        audit_logger.info(
            "user_role_assigned",
            performed_by=str(request.user.id),
            target_user_id=str(user.id),
            user_role_id=str(user_role.id),
            role_id=str(role.id),
            role_name=role.role_name,
            school_id=(
                str(school_id)
                if school_id
                else None
            ),
            created=created,
        )

        return CustomResponse.successResponse(
            data={
                "id": str(user_role.id),
                "created": created,
            },
            description="Role assigned successfully.",
        )
class RBACDashboardAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        application_logger.info(
            "rbac_dashboard_started",
            user_id=str(request.user.id),
        )

        data = {
            "users_count": UserMaster.objects.count(),
            "roles_count": Roles.objects.count(),
            "permissions_count": Permissions.objects.count(),
            "user_roles_count": UserRoles.objects.count(),
            "role_permissions_count": RolePermissions.objects.count(),
        }

        application_logger.info(
            "rbac_dashboard_fetched",
            user_id=str(request.user.id),
            **data,
        )

        return CustomResponse.successResponse(
            data=data,
            description="RBAC dashboard fetched successfully.",
        )

class UserAccessAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request, user_id):

        application_logger.info(
            "user_access_fetch_started",
            requested_by=str(request.user.id),
            target_user_id=str(user_id),
        )

        user = UserMaster.objects.filter(
            id=user_id
        ).first()

        if not user:

            application_logger.warning(
                "user_access_fetch_failed",
                requested_by=str(request.user.id),
                target_user_id=str(user_id),
                reason="user_not_found",
            )

            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        user_roles = UserRoles.objects.select_related(
            "role",
            "school",
        ).filter(
            user=user,
        )

        role_data = []

        permissions = set()

        for user_role in user_roles:

            role_data.append({
                "role_id": str(user_role.role.id),
                "role_name": user_role.role.role_name,
                "school_id": (
                    str(user_role.school.id)
                    if user_role.school
                    else None
                ),
                "school_name": (
                    user_role.school.name
                    if user_role.school
                    else None
                ),
            })

            role_permissions = RolePermissions.objects.filter(
                role=user_role.role
            ).values_list(
                "permission__permission_name",
                flat=True,
            )

            permissions.update(
                role_permissions
            )

        direct_permissions = UserPermissions.objects.filter(
            user=user
        ).values_list(
            "permission__permission_name",
            flat=True,
        )

        permissions.update(
            direct_permissions
        )

        application_logger.info(
            "user_access_fetched",
            requested_by=str(request.user.id),
            target_user_id=str(user.id),
            roles_count=len(role_data),
            permissions_count=len(permissions),
        )

        return CustomResponse.successResponse(
            data={
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "mobile": user.mobile,
                },
                "roles": role_data,
                "permissions": sorted(
                    list(permissions)
                ),
            },
            description="User access fetched successfully.",
        )



class RolesAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        role_id = request.query_params.get(
            "role_id"
        )

        role_name = request.query_params.get(
            "role_name"
        )

        application_logger.info(
            "roles_fetch_started",
            requested_by=str(request.user.id),
            role_id=role_id,
            role_name=role_name,
        )

        queryset = Roles.objects.all()

        if role_id:

            queryset = queryset.filter(
                id=role_id
            )

        if role_name:

            queryset = queryset.filter(
                role_name__icontains=role_name
            )

        data = [
            {
                "id": str(role.id),
                "role_name": role.role_name,
                "description": role.description,
            }
            for role in queryset
        ]

        application_logger.info(
            "roles_fetched",
            requested_by=str(request.user.id),
            total_count=len(data),
            role_id=role_id,
            role_name=role_name,
        )

        return CustomResponse.successResponse(
            data=data,
            description="Roles fetched successfully.",
        )



class RoleAccessAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request, role_id):

        application_logger.info(
            "role_access_fetch_started",
            requested_by=str(request.user.id),
            role_id=str(role_id),
        )

        role = Roles.objects.filter(
            id=role_id
        ).first()

        if not role:

            application_logger.warning(
                "role_access_fetch_failed",
                requested_by=str(request.user.id),
                role_id=str(role_id),
                reason="role_not_found",
            )

            return CustomResponse.errorResponse(
                description="Role not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        permissions = RolePermissions.objects.select_related(
            "permission",
            "permission__module",
        ).filter(
            role=role
        )

        data = [
            {
                "permission_id": str(
                    item.permission.id
                ),
                "permission_name": item.permission.permission_name,
                "module": item.permission.module.module_name,
            }
            for item in permissions
        ]

        application_logger.info(
            "role_access_fetched",
            requested_by=str(request.user.id),
            role_id=str(role.id),
            role_name=role.role_name,
            permissions_count=len(data),
        )

        return CustomResponse.successResponse(
            data={
                "role": {
                    "id": str(role.id),
                    "role_name": role.role_name,
                },
                "permissions": data,
            },
            description="Role access fetched successfully.",
        )



class ModulesAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        module_id = request.query_params.get(
            "module_id"
        )

        module_name = request.query_params.get(
            "module_name"
        )

        application_logger.info(
            "modules_fetch_started",
            requested_by=str(request.user.id),
            module_id=module_id,
            module_name=module_name,
        )

        queryset = Modules.objects.all()

        if module_id:

            queryset = queryset.filter(
                id=module_id
            )

        if module_name:

            queryset = queryset.filter(
                module_name__icontains=module_name
            )

        data = [
            {
                "id": str(module.id),
                "module_name": module.module_name,
            }
            for module in queryset
        ]

        application_logger.info(
            "modules_fetched",
            requested_by=str(request.user.id),
            total_count=len(data),
            module_id=module_id,
            module_name=module_name,
        )

        return CustomResponse.successResponse(
            data=data,
            description="Modules fetched successfully.",
        )


class ModulePermissionsAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request, module_id):

        application_logger.info(
            "module_permissions_fetch_started",
            requested_by=str(request.user.id),
            module_id=str(module_id),
        )

        module = Modules.objects.filter(
            id=module_id
        ).first()

        if not module:

            application_logger.warning(
                "module_permissions_fetch_failed",
                requested_by=str(request.user.id),
                module_id=str(module_id),
                reason="module_not_found",
            )

            return CustomResponse.errorResponse(
                description="Module not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        permissions = Permissions.objects.filter(
            module=module
        )

        data = [
            {
                "id": str(permission.id),
                "permission_name": permission.permission_name,
            }
            for permission in permissions
        ]

        application_logger.info(
            "module_permissions_fetched",
            requested_by=str(request.user.id),
            module_id=str(module.id),
            module_name=module.module_name,
            permissions_count=len(data),
        )

        return CustomResponse.successResponse(
            data={
                "module": {
                    "id": str(module.id),
                    "module_name": module.module_name,
                },
                "permissions": data,
            },
            description="Module permissions fetched successfully.",
        )


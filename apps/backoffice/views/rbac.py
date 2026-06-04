from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.core.models import Modules, Permissions, Roles, RolePermissions, UserMaster, UserRoles
from shared.mixins import CustomResponse
from shared.permissions import HasRole
from shared.enums.roles import RolesEnum


class ModuleListCreateAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
        HasRole,
    ]

    required_roles = [
        RolesEnum.SUPERADMIN,
    ]

    def get(self, request):

        modules = Modules.objects.all().order_by(
            "module_name"
        )

        return CustomResponse.successResponse(
            data=[
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
        )

    def post(self, request):

        module_name = request.data.get(
            "module_name"
        )

        parent_id = request.data.get(
            "parent_id"
        )

        if not module_name:
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
            return CustomResponse.errorResponse(
                description="Module already exists.",
                status=status.HTTP_400_BAD_REQUEST,
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

        permissions = Permissions.objects.select_related(
            "module"
        )

        return CustomResponse.successResponse(
            data=[
                {
                    "id": str(permission.id),
                    "permission_name": permission.permission_name,
                    "module_id": str(permission.module.id),
                    "module_name": permission.module.module_name,
                }
                for permission in permissions
            ]
        )

    def post(self, request):

        module_id = request.data.get(
            "module_id"
        )

        permission_name = request.data.get(
            "permission_name"
        )

        if not module_id or not permission_name:

            return CustomResponse.errorResponse(
                description="module_id and permission_name are required.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        module = Modules.objects.filter(
            id=module_id
        ).first()

        if not module:
            return CustomResponse.errorResponse(
                description="Module not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        permission, created = Permissions.objects.get_or_create(
            module=module,
            permission_name=permission_name,
        )

        if not created:
            return CustomResponse.errorResponse(
                description="Permission already exists.",
                status=status.HTTP_400_BAD_REQUEST,
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

        roles = Roles.objects.all().order_by(
            "role_name"
        )

        return CustomResponse.successResponse(
            data=[
                {
                    "id": str(role.id),
                    "role_name": role.role_name,
                    "description": role.description,
                }
                for role in roles
            ]
        )

    def post(self, request):

        role_name = request.data.get(
            "role_name"
        )

        description = request.data.get(
            "description",
            "",
        )

        if not role_name:
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
            return CustomResponse.errorResponse(
                description="Role already exists.",
                status=status.HTTP_400_BAD_REQUEST,
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

        role = Roles.objects.filter(
            id=role_id
        ).first()

        if not role:
            return CustomResponse.errorResponse(
                description="Role not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        permission_ids = request.data.get(
            "permission_ids",
            [],
        )

        created_count = 0

        for permission_id in permission_ids:

            permission = Permissions.objects.filter(
                id=permission_id
            ).first()

            if not permission:
                continue

            _, created = RolePermissions.objects.get_or_create(
                role=role,
                permission=permission,
            )

            if created:
                created_count += 1

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

        user = UserMaster.objects.filter(
            id=user_id
        ).first()

        if not user:
            return CustomResponse.errorResponse(
                description="User not found.",
                status=status.HTTP_404_NOT_FOUND,
            )

        role = Roles.objects.filter(
            id=role_id
        ).first()

        if not role:
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

        return CustomResponse.successResponse(
            data={
                "id": str(user_role.id),
                "created": created,
            },
            description="Role assigned successfully.",
        )





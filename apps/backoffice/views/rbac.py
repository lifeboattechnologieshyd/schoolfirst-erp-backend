from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.core.models import (
    Modules,
    Permissions,
    Roles,
    RolePermissions,
    UserRoles,
    UserPermissions,
    UserMaster,
)



def is_super_admin(user):
    roles = getattr(user, "user_role", []) or []
    return "SUPER_ADMIN" in roles


class ModuleListCreateAPIView(APIView):
    def get(self, request):
        modules = Modules.objects.all().order_by("module_name")
        return Response(
            {
                "data": [
                    {
                        "id": str(m.id),
                        "module_name": m.module_name,
                        "parent": str(m.parent_id) if m.parent_id else None,
                    }
                    for m in modules
                ]
            }
        )

    def post(self, request):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        module_name = request.data.get("module_name")
        parent_id = request.data.get("parent_id")

        if not module_name:
            return Response({"message": "module_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        parent = Modules.objects.filter(id=parent_id).first() if parent_id else None
        module = Modules.objects.create(module_name=module_name, parent=parent)

        return Response({"message": "Module created", "id": str(module.id)}, status=status.HTTP_201_CREATED)


class PermissionListCreateAPIView(APIView):
    def get(self, request):
        permissions = Permissions.objects.select_related("module").all()
        return Response(
            {
                "data": [
                    {
                        "id": str(p.id),
                        "permission_name": p.permission_name,
                        "module": p.module.module_name,
                        "module_id": str(p.module.id),
                    }
                    for p in permissions
                ]
            }
        )

    def post(self, request):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        module_id = request.data.get("module_id")
        permission_name = request.data.get("permission_name")

        if not module_id or not permission_name:
            return Response(
                {"message": "module_id and permission_name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        module = get_object_or_404(Modules, id=module_id)
        permission = Permissions.objects.create(module=module, permission_name=permission_name)

        return Response({"message": "Permission created", "id": str(permission.id)}, status=status.HTTP_201_CREATED)


class RoleListCreateAPIView(APIView):
    def get(self, request):
        roles = Roles.objects.all().order_by("role_name")
        return Response(
            {
                "data": [
                    {
                        "id": str(role.id),
                        "role_name": role.role_name,
                        "description": role.description,
                    }
                    for role in roles
                ]
            }
        )

    def post(self, request):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        role_name = request.data.get("role_name")
        description = request.data.get("description", "")

        if not role_name:
            return Response({"message": "role_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        role = Roles.objects.create(role_name=role_name, description=description)
        return Response({"message": "Role created", "id": str(role.id)}, status=status.HTTP_201_CREATED)


class RoleDetailAPIView(APIView):
    def get(self, request, role_id):
        role = get_object_or_404(Roles, id=role_id)
        return Response(
            {
                "data": {
                    "id": str(role.id),
                    "role_name": role.role_name,
                    "description": role.description,
                }
            }
        )

    def patch(self, request, role_id):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        role = get_object_or_404(Roles, id=role_id)
        if "role_name" in request.data:
            role.role_name = request.data["role_name"]
        if "description" in request.data:
            role.description = request.data["description"]
        role.save()
        return Response({"message": "Role updated successfully"})

    def delete(self, request, role_id):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        role = get_object_or_404(Roles, id=role_id)
        role.delete()
        return Response({"message": "Role deleted successfully"})


class AssignPermissionsToRoleAPIView(APIView):
    """
    POST body:
    {
        "permission_ids": ["uuid1", "uuid2"]
    }
    """

    def post(self, request, role_id):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        role = get_object_or_404(Roles, id=role_id)
        permission_ids = request.data.get("permission_ids", [])

        if not permission_ids:
            return Response({"message": "permission_ids is required"}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        for permission_id in permission_ids:
            permission = get_object_or_404(Permissions, id=permission_id)
            obj, was_created = RolePermissions.objects.get_or_create(role=role, permission=permission)
            if was_created:
                created += 1

        return Response(
            {"message": "Permissions assigned", "created": created},
            status=status.HTTP_200_OK,
        )


class AssignRoleToUserAPIView(APIView):
    """
    POST body:
    {
        "user_id": "uuid",
        "school_id": "uuid",
        "role_id": "uuid"
    }
    """

    def post(self, request):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get("user_id")
        school_id = request.data.get("school_id")
        role_id = request.data.get("role_id")

        if not user_id or not school_id or not role_id:
            return Response(
                {"message": "user_id, school_id, and role_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = get_object_or_404(UserMaster, id=user_id)
        # school = get_object_or_404(School, id=school_id)
        role = get_object_or_404(Roles, id=role_id)

        user_role, created = UserRoles.objects.get_or_create(
            user=user,
            school_id=school_id,
            role=role,
        )

        return Response(
            {
                "message": "Role assigned to user",
                "created": created,
                "id": str(user_role.id),
            },
            status=status.HTTP_200_OK,
        )


class AssignPermissionToUserAPIView(APIView):
    """
    POST body:
    {
        "user_id": "uuid",
        "school_id": "uuid",
        "permission_id": "uuid"
    }
    """

    def post(self, request):
        if not request.user.is_authenticated or not is_super_admin(request.user):
            return Response({"message": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get("user_id")
        school_id = request.data.get("school_id")
        permission_id = request.data.get("permission_id")

        if not user_id or not school_id or not permission_id:
            return Response(
                {"message": "user_id, school_id, and permission_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = get_object_or_404(UserMaster, id=user_id)
        permission = get_object_or_404(Permissions, id=permission_id)

        user_perm, created = UserPermissions.objects.get_or_create(
            user=user,
            school_id=school_id,
            permission=permission,
        )

        return Response(
            {
                "message": "Permission assigned to user",
                "created": created,
                "id": str(user_perm.id),
            },
            status=status.HTTP_200_OK,
        )
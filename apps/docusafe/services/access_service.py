from dataclasses import dataclass
from typing import Any

import structlog
from django.db import transaction
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.services.social_graph_service import SocialGraphService
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.file_access import DocusafeFileAccess
from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.services.folder_scope_service import DocusafeFolderScopeService
from shared.enums import DocusafeAccessType, DocusafeStatus

logger = structlog.getLogger("default")


@dataclass(frozen=True)
class GrantAccessRequest:
    owner_id: str
    file_ids: tuple[str, ...]
    access_type: str
    family_id: str
    user_ids: tuple[str, ...] = ()

    @classmethod
    def from_validated_data(cls, owner_id: Any, validated_data: dict) -> GrantAccessRequest:
        return cls(
            owner_id=str(owner_id),
            file_ids=tuple(str(file_id) for file_id in validated_data["file_ids"]),
            access_type=str(validated_data["access_type"]),
            family_id=str(validated_data["family_id"]),
            user_ids=tuple(str(user_id) for user_id in validated_data.get("user_ids") or []),
        )


@dataclass(frozen=True)
class GrantAccessResult:
    grants: tuple[DocusafeFileAccess, ...]

    @property
    def count(self) -> int:
        return len(self.grants)


@dataclass(frozen=True)
class RevokeAccessRequest:
    user_id: str
    access_ids: tuple[str, ...]

    @classmethod
    def from_validated_data(cls, user_id: Any, validated_data: dict) -> RevokeAccessRequest:
        return cls(
            user_id=str(user_id),
            access_ids=tuple(str(access_id) for access_id in validated_data["access_ids"]),
        )


@dataclass(frozen=True)
class RevokeAccessResult:
    count: int


class DocusafeAccessService:
    """
    Service layer for managing file access grants and permissions.
    """

    @staticmethod
    @transaction.atomic
    def grant_access(request: GrantAccessRequest) -> GrantAccessResult:
        """
        Grant read-only access to one or more files.
        """
        files = DocusafeFolderScopeService.get_owned_files(request.owner_id, list(request.file_ids), folder_status=None)

        # 2. If access_type is USER, validate user_ids are approved members
        if request.access_type == DocusafeAccessType.USER and request.user_ids:
            valid_member_ids = set(SocialGraphService.get_joined_family_member_user_ids_by_family_id(request.family_id))
            invalid_ids = set(request.user_ids) - valid_member_ids
            if invalid_ids:
                raise ValidationError(f"Users {invalid_ids} are not approved members of family {request.family_id}")

        results = []
        for file in files:
            if request.access_type == DocusafeAccessType.FAMILY:
                # Upgrade to FAMILY: deactivate redundant USER grants for this family
                DocusafeFileAccess.objects.filter(
                    file_id=file.id,
                    family_id=request.family_id,
                    access_type=DocusafeAccessType.USER,
                ).update(is_active=False)

                # Upsert FAMILY grant
                obj, created = DocusafeFileAccess.objects.update_or_create(
                    file_id=file.id,
                    access_type=request.access_type,
                    family_id=request.family_id,
                    user_id=None,
                    defaults={"owner_id": request.owner_id, "is_active": True},
                )
                results.append(obj)
            else:
                # USER access
                # Check if FAMILY access already exists
                if DocusafeFileAccess.objects.filter(
                    file_id=file.id,
                    family_id=request.family_id,
                    access_type=DocusafeAccessType.FAMILY,
                    is_active=True,
                ).exists():
                    logger.info(
                        "Skipping USER grant as FAMILY grant already exists",
                        file_id=file.id,
                        family_id=request.family_id,
                    )
                    continue

                for uid in request.user_ids:
                    obj, created = DocusafeFileAccess.objects.update_or_create(
                        file_id=file.id,
                        access_type=request.access_type,
                        family_id=request.family_id,
                        user_id=uid,
                        defaults={"owner_id": request.owner_id, "is_active": True},
                    )
                    results.append(obj)

        return GrantAccessResult(grants=tuple(results))

    @staticmethod
    def revoke_access(request: RevokeAccessRequest) -> RevokeAccessResult:
        """
        Revoke access grants. User must be the owner of the files.
        """
        # Find grants where the owner of the file is user_id
        grants = DocusafeFileAccess.objects.filter(id__in=request.access_ids, owner_id=request.user_id)
        count = grants.update(is_active=False)
        return RevokeAccessResult(count=count)

    @staticmethod
    def get_file_access_list(user_id: Any, file_id: Any) -> QuerySet[DocusafeFileAccess]:
        """
        List all active access grants for a file.
        Only the owner can see this.
        """
        # Ownership check
        file = get_object_or_404(DocusafeFile, id=file_id)

        if not DocusafeFolderScopeService.user_owns_folder(user_id, file.folder_id, status=None):
            raise PermissionDenied("You do not have permission to view access logs for this file.")

        return DocusafeFileAccess.objects.filter(file_id=file_id, is_active=True)

    @staticmethod
    def validate_folder_access(user_id: str, folder_id: str) -> None:
        """
        Assert that user_id owns folder_id (active).
        Raises ValidationError if not found or not owned.

        Use this instead of replicating the owner ORM query at call sites.
        """
        if not DocusafeFolderScopeService.user_owns_folder(user_id, folder_id):
            raise ValidationError("Folder not found or you do not have access.")

    @staticmethod
    def has_access(user_id: Any, file_id: Any) -> bool:
        """
        Check if a user has access to a file.
        Checks: Owner, FAMILY grant, or USER grant.
        """
        file = DocusafeFile.objects.filter(id=file_id, status=DocusafeStatus.ACTIVE).values("folder_id").first()
        if not file:
            return False

        # 1. Owner check
        if DocusafeFolderScopeService.user_owns_folder(user_id, file["folder_id"]):
            return True

        # 2. Check for active grants
        # Family membership check (needed for FAMILY grants)
        user_families = SocialGraphService.get_user_family_ids_for_user_id(user_id)

        access_q = Q(file_id=file_id, is_active=True) & (
            Q(access_type=DocusafeAccessType.FAMILY, family_id__in=user_families)
            | Q(access_type=DocusafeAccessType.USER, user_id=user_id)
        )

        return DocusafeFileAccess.objects.filter(access_q).exists()

    @staticmethod
    def get_accessible_file_ids(user_id: str, candidate_file_ids: list[str] | None = None) -> list[str]:
        """Return active Docusafe file IDs the user owns or can access."""
        normalized_candidate_ids = [str(file_id) for file_id in candidate_file_ids] if candidate_file_ids else None

        owned_file_filters: dict[str, Any] = {
            "folder_id__in": DocusafeFolderScopeService.get_owned_folder_ids(user_id),
            "status": DocusafeStatus.ACTIVE,
        }
        if normalized_candidate_ids is not None:
            owned_file_filters["id__in"] = normalized_candidate_ids

        accessible_ids = {
            str(file_id) for file_id in DocusafeFile.objects.filter(**owned_file_filters).values_list("id", flat=True)
        }

        user_families = SocialGraphService.get_user_family_ids_for_user_id(user_id)
        access_q = Q(is_active=True) & (
            Q(access_type=DocusafeAccessType.FAMILY, family_id__in=user_families)
            | Q(access_type=DocusafeAccessType.USER, user_id=user_id)
        )
        if normalized_candidate_ids is not None:
            access_q &= Q(file_id__in=normalized_candidate_ids)

        granted_file_ids = DocusafeFileAccess.objects.filter(access_q).values_list("file_id", flat=True)
        granted_files = DocusafeFile.objects.filter(id__in=granted_file_ids, status=DocusafeStatus.ACTIVE)
        accessible_ids.update(str(file_id) for file_id in granted_files.values_list("id", flat=True))

        if normalized_candidate_ids is not None:
            return [file_id for file_id in normalized_candidate_ids if file_id in accessible_ids]

        return list(accessible_ids)

    @staticmethod
    def get_shared_folders(user_id: Any) -> QuerySet[DocusafeFolder]:
        """
        Return folders with files shared *specifically* with this user
        (USER grant), excluding folders owned by the user.
        """
        shared_file_ids = DocusafeFileAccess.objects.filter(
            user_id=user_id, access_type=DocusafeAccessType.USER, is_active=True
        ).values_list("file_id", flat=True)

        user_folders = DocusafeFolder.objects.filter(owner_id=user_id).values_list("id", flat=True)

        folder_ids = (
            DocusafeFile.objects.filter(id__in=shared_file_ids)
            .exclude(folder_id__in=user_folders)
            .values_list("folder_id", flat=True)
            .distinct()
        )

        return DocusafeFolder.objects.filter(id__in=folder_ids, status=DocusafeStatus.ACTIVE).only(
            "id", "name", "file_count", "total_size", "is_shared", "status", "created_at"
        )

    @staticmethod
    def get_shared_files_in_folder(user_id: Any, folder_id: Any) -> QuerySet[DocusafeFile]:
        """
        Return files shared with the user (USER grant) in a specific folder.
        """
        shared_file_ids = DocusafeFileAccess.objects.filter(
            user_id=user_id, access_type=DocusafeAccessType.USER, is_active=True
        ).values_list("file_id", flat=True)

        return DocusafeFile.objects.filter(
            id__in=shared_file_ids, folder_id=folder_id, status=DocusafeStatus.ACTIVE
        ).only("id", "file_name", "file_size", "mime_type", "is_shared", "status", "created_at")

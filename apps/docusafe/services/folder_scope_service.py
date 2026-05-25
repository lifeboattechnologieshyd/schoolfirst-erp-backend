from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.folder import DocusafeFolder
from shared.enums import DocusafeStatus


class DocusafeFolderScopeService:
    """
    Resolve folder and file ownership checks for Docusafe modules.
    """

    @staticmethod
    def get_owned_folder_ids(user_id: Any, status: str | None = DocusafeStatus.ACTIVE) -> QuerySet:
        filters: dict[str, Any] = {"owner_id": user_id}
        if status is not None:
            filters["status"] = status
        return DocusafeFolder.objects.filter(**filters).values_list("id", flat=True)

    @staticmethod
    def get_owned_folder(user_id: Any, folder_id: Any, status: str | None = DocusafeStatus.ACTIVE) -> DocusafeFolder:
        filters: dict[str, Any] = {"id": folder_id, "owner_id": user_id}
        if status is not None:
            filters["status"] = status
        return get_object_or_404(DocusafeFolder, **filters)

    @staticmethod
    def user_owns_folder(user_id: Any, folder_id: Any, status: str | None = DocusafeStatus.ACTIVE) -> bool:
        filters: dict[str, Any] = {"id": folder_id, "owner_id": user_id}
        if status is not None:
            filters["status"] = status
        return DocusafeFolder.objects.filter(**filters).exists()

    @staticmethod
    def get_owned_files(
        user_id: Any,
        file_ids: list[Any],
        *,
        folder_status: str | None = DocusafeStatus.ACTIVE,
        file_status: str | None = None,
        error_message: str = "One or more files do not exist or you do not have permission to share them.",
    ) -> QuerySet[DocusafeFile]:
        filters: dict[str, Any] = {
            "id__in": file_ids,
            "folder_id__in": DocusafeFolderScopeService.get_owned_folder_ids(user_id, status=folder_status),
        }
        if file_status is not None:
            filters["status"] = file_status

        files = DocusafeFile.objects.filter(**filters)
        if files.count() != len(file_ids):
            raise ValidationError(error_message)
        return files

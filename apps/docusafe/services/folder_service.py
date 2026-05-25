from typing import Any

import structlog
from django.db import IntegrityError, models, transaction
from django.db.models import QuerySet, Sum
from rest_framework.exceptions import ValidationError

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.services.folder_scope_service import DocusafeFolderScopeService
from shared.enums import DocusafeStatus

logger = structlog.getLogger("default")


class DocusafeFolderService:
    """
    Service layer for managing Docusafe folders.
    """

    @staticmethod
    def list_folders(user_id: Any) -> QuerySet[DocusafeFolder]:
        """
        List folders owned by the user.
        """
        return DocusafeFolder.objects.filter(owner_id=user_id, status=DocusafeStatus.ACTIVE).only(
            "id", "name", "file_count", "total_size", "is_shared", "status", "created_at"
        )

    @staticmethod
    def create_folder(user_id: Any, name: str, description: str | None = None) -> DocusafeFolder:
        """
        Create a new Docusafe folder.
        """
        try:
            folder = DocusafeFolder.objects.create(
                owner_id=user_id,
                name=name,
                description=description,
            )
            return folder
        except IntegrityError as e:
            if "name" in str(e).lower() or "unique" in str(e).lower():
                raise ValidationError(
                    {"name": [f"A folder with name '{name}' already exists for this user."]}
                ) from None
            logger.exception("Database integrity error during folder creation", user_id=user_id, folder_name=name)
            raise ValidationError("A database error occurred while creating the folder.") from None

    @staticmethod
    def get_folder(user_id: Any, folder_id: Any) -> DocusafeFolder:
        """
        Retrieve a folder by ID, ensuring ownership.
        """
        return DocusafeFolderScopeService.get_owned_folder(user_id, folder_id)

    @staticmethod
    def update_folder(user_id: Any, folder_id: Any, **data: Any) -> DocusafeFolder:
        """
        Update folder details.
        """
        folder = DocusafeFolderService.get_folder(user_id, folder_id)

        # Restricted fields that cannot be updated via this method
        restricted_fields = {"id", "owner_id", "file_count", "total_size", "is_shared"}
        for field in restricted_fields:
            data.pop(field, None)

        for field, value in data.items():
            setattr(folder, field, value)

        try:
            folder.save()
        except IntegrityError as e:
            if "name" in str(e).lower() or "unique" in str(e).lower():
                raise ValidationError(
                    {"name": [f"A folder with name '{data.get('name')}' already exists for this user."]}
                ) from None
            logger.exception("Database integrity error during folder update", user_id=user_id, folder_id=folder_id)
            raise ValidationError("A database error occurred while updating the folder.") from None

        return folder

    @staticmethod
    @transaction.atomic
    def delete_folder(user_id: Any, folder_id: Any) -> bool:
        """
        Soft-delete a folder and its contents.
        """
        folder = DocusafeFolderService.get_folder(user_id, folder_id)

        # 1. Collect active file IDs before any status change.
        active_file_ids = list(
            DocusafeFile.objects.filter(folder_id=folder_id, status=DocusafeStatus.ACTIVE).values_list("id", flat=True)
        )

        # 2. Sync temporary shares before the files are marked deleted so share
        #    counts and empty-share cleanup stay consistent.
        from apps.docusafe.services.share_projection_service import (  # noqa: PLC0415
            DocusafeShareProjectionService,
        )

        DocusafeShareProjectionService.remove_files(active_file_ids)

        # 3. Batch soft-delete all active files in a single query instead of a per-file
        #    loop that would trigger N stat-recalculations.
        DocusafeFile.objects.filter(id__in=active_file_ids).update(status=DocusafeStatus.DELETED)

        # 4. Recalculate folder stats exactly once after the batch delete.
        DocusafeFolderService.recalculate_folder_stats(folder_id)

        # 5. Mark the folder itself as deleted.
        folder.status = DocusafeStatus.DELETED
        folder.save()

        logger.info("Soft-deleted folder and its contents", folder_id=folder_id)
        return True

    @staticmethod
    def recalculate_folder_stats(folder_id: Any) -> None:
        """
        Recalculate file_count and total_size for a folder.
        """
        with transaction.atomic():
            folder = DocusafeFolder.objects.select_for_update().only("id").get(id=folder_id)
            stats = DocusafeFile.objects.filter(folder_id=folder_id, status=DocusafeStatus.ACTIVE).aggregate(
                count=models.Count("id"),
                total_size=Sum("file_size", default=0),
            )

            folder.file_count = stats["count"]
            folder.total_size = stats["total_size"]
            folder.save(update_fields=["file_count", "total_size"])

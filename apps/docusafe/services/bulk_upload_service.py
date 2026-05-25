from typing import Any

import structlog
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.docusafe.constants import MAX_FILES_PER_FOLDER, MAX_FOLDER_SIZE
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.services.folder_scope_service import DocusafeFolderScopeService
from apps.docusafe.services.folder_service import DocusafeFolderService

logger = structlog.getLogger("default")


class DocusafeBulkUploadService:
    """
    Dedicated service for handling Bulk Uploads with Partial Success architecture.
    """

    @staticmethod
    def upload_files_bulk(
        user_id: Any,
        folder_id: Any,
        file_objs: list[UploadedFile],
        descriptions: list[str | None] | None = None,
    ) -> tuple[list[DocusafeFile], list[dict[str, str]]]:
        """
        Upload multiple files with partial success support (Multi-Status).
        Rolls back individual file S3 orphans if DB fails.
        """
        from apps.docusafe.services.file_service import DocusafeFileService  # noqa: PLC0415

        # 1. Ownership & Folder existence check
        folder = DocusafeFolderScopeService.get_owned_folder(user_id, folder_id)

        # 2. Pre-check Aggregate Limits
        total_bulk_size = sum(f.size for f in file_objs)
        if folder.file_count + len(file_objs) > MAX_FILES_PER_FOLDER:
            rem = MAX_FILES_PER_FOLDER - folder.file_count
            raise ValidationError(
                f"Bulk upload would exceed folder limit of {MAX_FILES_PER_FOLDER} files. Remaining: {rem}"
            )

        if folder.total_size + total_bulk_size > MAX_FOLDER_SIZE:
            limit_mb = MAX_FOLDER_SIZE / (1024 * 1024)
            raise ValidationError(f"Bulk upload would exceed folder size limit of {limit_mb} MB.")

        created_files = []
        failed_files = []

        for i, file_obj in enumerate(file_objs):
            desc = descriptions[i] if descriptions and i < len(descriptions) else None
            try:
                # Process each upload in its own savepoint so one failure does not
                # abort the whole bulk operation.
                with transaction.atomic():
                    file_rec = DocusafeFileService._process_single_upload(
                        user_id=user_id,
                        folder_id=folder_id,
                        file_obj=file_obj,
                        description=desc,
                        recalculate_stats=False,
                        folder_instance=folder,
                    )
                    created_files.append(file_rec)
            except Exception as e:
                logger.exception("Bulk upload failed for file", file_name=file_obj.name, error=str(e))
                # Store the failure reason without aborting the loop
                failed_files.append({"file_name": file_obj.name, "error": str(e)})

        # 3. Final Recalculate once for the whole folder
        if created_files:
            DocusafeFolderService.recalculate_folder_stats(folder_id)

        return created_files, failed_files

from typing import Any

import structlog
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.docusafe.constants import MAX_FILE_SIZE, MAX_FILES_PER_FOLDER, MAX_FOLDER_SIZE
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.services.access_service import DocusafeAccessService
from apps.docusafe.services.bulk_upload_service import DocusafeBulkUploadService
from apps.docusafe.services.file_storage_service import DocusafeFileStorageService
from apps.docusafe.services.folder_scope_service import DocusafeFolderScopeService
from apps.docusafe.services.folder_service import DocusafeFolderService
from shared.enums import DocusafeStatus

logger = structlog.getLogger("default")


class DocusafeFileService:
    """
    Service layer for managing Docusafe files.
    """

    @staticmethod
    def upload_file(
        user_id: Any, folder_id: Any, file_obj: UploadedFile, description: str | None = None
    ) -> DocusafeFile:
        """
        Upload file to S3 and create DB record.
        """
        return DocusafeFileService._process_single_upload(
            user_id=user_id, folder_id=folder_id, file_obj=file_obj, description=description, recalculate_stats=True
        )

    @staticmethod
    def upload_files_bulk(
        user_id: Any,
        folder_id: Any,
        file_objs: list[UploadedFile],
        descriptions: list[str | None] | None = None,
    ) -> tuple[list[DocusafeFile], list[dict[str, str]]]:
        """
        Upload multiple files with partial success support (Multi-Status).
        Delegated to DocusafeBulkUploadService.
        """
        return DocusafeBulkUploadService.upload_files_bulk(user_id, folder_id, file_objs, descriptions)

    @staticmethod
    def _process_single_upload(
        user_id: Any,
        folder_id: Any,
        file_obj: UploadedFile,
        description: str | None = None,
        recalculate_stats: bool = True,
        folder_instance: DocusafeFolder | None = None,
    ) -> DocusafeFile:
        """
        Internal helper for core upload logic of a single file.
        """
        # 1. Ownership & Folder existence check
        if not folder_instance:
            folder = DocusafeFolderScopeService.get_owned_folder(user_id, folder_id)
        else:
            folder = folder_instance

        # 2. Validation: Extension & Size
        file_extension = DocusafeFileStorageService.validate_file_type(file_obj.name)
        file_size = file_obj.size

        limit_mb = MAX_FILE_SIZE / (1024 * 1024)
        if file_size > MAX_FILE_SIZE:
            raise ValidationError(f"File '{file_obj.name}' exceeds limit of {limit_mb} MB.")

        # 3. Validation: Folder Limits
        if recalculate_stats:
            if folder.file_count >= MAX_FILES_PER_FOLDER:
                raise ValidationError(f"Folder has reached its limit of {MAX_FILES_PER_FOLDER} files.")

            if folder.total_size + file_size > MAX_FOLDER_SIZE:
                folder_limit_mb = MAX_FOLDER_SIZE / (1024 * 1024)
                raise ValidationError(f"Uploading this file would exceed folder limit of {folder_limit_mb} MB.")

        # 4. Compute metadata
        checksum = DocusafeFileStorageService.compute_sha256(file_obj)
        mime_type = getattr(file_obj, "content_type", "application/octet-stream")

        # 5. Create DB record (Initial Task)
        try:
            with transaction.atomic():
                file_rec = DocusafeFile.objects.create(
                    folder_id=folder_id,
                    owner_id=user_id,
                    file_name=file_obj.name,
                    description=description,
                    file_path="PENDING_UPLOAD",
                    mime_type=mime_type,
                    file_size=file_size,
                    file_extension=file_extension,
                    checksum=checksum,
                )
                file_id = str(file_rec.id)
        except IntegrityError as e:
            # Check if this is a unique constraint violation on file_name
            if "file_name" in str(e).lower() or "unique" in str(e).lower():
                raise ValidationError(
                    {"file_name": [f"A file with name '{file_obj.name}' already exists in this folder."]}
                ) from None
            logger.exception("Database integrity error during file upload", user_id=user_id, folder_id=folder_id)
            raise ValidationError("A database error occurred while creating the file record.") from None

        # 6. S3 Upload Logic with Rollback Safety
        file_path = DocusafeFileStorageService.construct_s3_path(str(user_id), str(folder_id), file_id, file_obj.name)

        try:
            DocusafeFileStorageService.upload_to_s3(file_path, file_obj)
        except ValidationError:
            # S3 failed, rollback the pending DB record
            DocusafeFile.objects.filter(id=file_id).delete()
            raise

        # 7. Update DB record and optionally Folder stats
        with transaction.atomic():
            DocusafeFile.objects.filter(id=file_id).update(file_path=file_path)
            if recalculate_stats:
                DocusafeFolderService.recalculate_folder_stats(folder_id)

        return DocusafeFile.objects.get(id=file_id)

    @staticmethod
    def list_files(user_id: Any, folder_id: Any) -> QuerySet[DocusafeFile]:
        """
        List files in a folder, ensuring ownership.
        """
        DocusafeFolderScopeService.get_owned_folder(user_id, folder_id)
        return DocusafeFile.objects.filter(folder_id=folder_id, status=DocusafeStatus.ACTIVE).only(
            "id", "file_name", "file_size", "mime_type", "is_shared", "status", "created_at"
        )

    @staticmethod
    def get_file(user_id: Any, folder_id: Any, file_id: Any) -> DocusafeFile:
        """
        Retrieve a file, checking permission (owner or shared).

        For owners, the folder URL parameter is used as the authoritative scope —
        the file must belong to *that specific folder* and that folder must be owned
        by the requesting user.  For non-owners with an explicit access grant the
        folder_id from the URL is still validated against the file's actual folder.
        """
        file_rec = get_object_or_404(DocusafeFile, id=file_id, folder_id=folder_id, status=DocusafeStatus.ACTIVE)

        # Fast path: folder ownership check scoped to the URL folder_id.
        if DocusafeFolderScopeService.user_owns_folder(user_id, folder_id):
            return file_rec

        # Fallback: explicit access grant (family or per-user).
        if not DocusafeAccessService.has_access(user_id, file_id):
            raise PermissionDenied("You do not have permission to access this file.")

        return file_rec

    @staticmethod
    def update_file(user_id: Any, folder_id: Any, file_id: Any, **data: Any) -> DocusafeFile:
        """
        Update file metadata.
        """
        file_rec = DocusafeFileService.get_file(user_id, folder_id, file_id)

        updatable_fields = {"file_name", "description"}
        for field in list(data.keys()):
            if field not in updatable_fields:
                data.pop(field)

        new_file_name = data.get("file_name")
        if new_file_name and new_file_name != file_rec.file_name:
            duplicate_exists = DocusafeFile.objects.filter(folder_id=folder_id, file_name=new_file_name).exclude(
                id=file_rec.id
            )
            if duplicate_exists.exists():
                raise ValidationError(
                    {"file_name": [f"A file with name '{new_file_name}' already exists in this folder."]}
                )

        for field, value in data.items():
            setattr(file_rec, field, value)

        try:
            file_rec.save()
        except IntegrityError as e:
            if "folder_id" in str(e).lower() and "file_name" in str(e).lower():
                failed_name = data.get("file_name", file_rec.file_name)
                raise ValidationError(
                    {"file_name": [f"A file with name '{failed_name}' already exists in this folder."]}
                ) from None
            raise
        return file_rec

    @staticmethod
    @transaction.atomic
    def delete_file(user_id: Any, folder_id: Any, file_id: Any) -> bool:
        """
        Soft-delete file and sync temporary shares.
        """
        file_rec = DocusafeFileService.get_file(user_id, folder_id, file_id)

        file_rec.status = DocusafeStatus.DELETED
        file_rec.save()

        from apps.docusafe.services.share_projection_service import (  # noqa: PLC0415
            DocusafeShareProjectionService,
        )

        DocusafeShareProjectionService.remove_files([file_id])

        DocusafeFolderService.recalculate_folder_stats(folder_id)

        logger.info("Soft-deleted file", file_id=file_id, folder_id=folder_id)
        return True

    @staticmethod
    def get_public_presigned_url(file_path):
        """
        Generate a pre-signed S3 URL without internal ownership checks.
        Used for public temporary shares.
        """
        return DocusafeFileStorageService.get_presigned_url(file_path)

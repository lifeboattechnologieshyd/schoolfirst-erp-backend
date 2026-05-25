import hashlib
import io
import os
from typing import Any

import structlog
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from rest_framework.exceptions import ValidationError

from apps.docusafe.constants import ALLOWED_EXTENSIONS

logger = structlog.getLogger("default")


class DocusafeFileStorageService:
    """
    Dedicated service for S3 storage operations and file validations.
    """

    @staticmethod
    def validate_file_type(filename: str) -> str:
        """
        Check if file extension is in the whitelist.
        """
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f"File type '{ext}' is not allowed.")
        return ext

    @staticmethod
    def compute_sha256(file_obj: UploadedFile) -> str:
        """
        Compute SHA-256 hash of a file object.
        """
        sha256_hash = hashlib.sha256()
        # Reset file pointer
        file_obj.seek(0)
        for chunk in file_obj.chunks():
            sha256_hash.update(chunk)
        # Reset file pointer again for subsequent use
        file_obj.seek(0)
        return sha256_hash.hexdigest()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitizes a filename for safe S3 storage.
        """
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in filename).lower()

    @staticmethod
    def construct_s3_path(user_id: str, folder_id: str, file_id: str, filename: str) -> str:
        """
        Construct the deterministic S3 path.
        """
        sanitized_name = DocusafeFileStorageService.sanitize_filename(filename)
        return f"docusafe/{user_id}/{folder_id}/{file_id}_{sanitized_name}"

    @staticmethod
    def upload_to_s3(file_path: str, file_obj: Any) -> bool:
        """
        Uploads a file object to S3 at the given path.
        """
        try:
            default_storage.save(file_path, file_obj)
            return True
        except Exception as e:
            logger.exception("S3 upload failed", file_path=file_path, error=str(e))
            raise ValidationError(f"File upload failed for '{file_obj.name}'. Please try again later.") from e

    @staticmethod
    def delete_from_s3(file_path: str) -> bool:
        """
        Deletes a file from S3 if it exists. Used for rollbacks.
        """
        try:
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
            return True
        except Exception as e:
            logger.exception("Failed to delete orphaned S3 object", file_path=file_path, error=str(e))
            return False

    @staticmethod
    def get_presigned_url(file_path: str, expiry: int | None = None) -> str:
        """
        Generate pre-signed S3 URL for download.

        Args:
            file_path: S3 object key.
            expiry: URL lifetime in seconds. None uses the storage backend default.
        """
        if not file_path or file_path == "PENDING_UPLOAD":
            raise ValidationError("File is not currently available.")

        try:
            return default_storage.url(file_path, expire=expiry)
        except Exception as e:
            logger.exception("Failed to generate pre-signed URL", file_path=file_path, error=str(e))
            raise ValidationError("Failed to generate download link.") from e

    @staticmethod
    def read_file_bytes(file_path: str) -> bytes:
        """Read a file from S3 and return its raw bytes."""
        try:
            with default_storage.open(file_path, "rb") as file_obj:
                content = file_obj.read()

            if isinstance(content, io.BytesIO):
                return content.read()
            return content
        except Exception:
            logger.exception("Failed to download file bytes from S3", file_path=file_path)
            raise

    @staticmethod
    def read_file_text(file_path: str) -> str:
        """Read a text file from S3, trying UTF-8 then latin-1."""
        try:
            content = DocusafeFileStorageService.read_file_bytes(file_path)
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content.decode("latin-1")
        except Exception:
            logger.exception("Failed to read text file from S3", file_path=file_path)
            raise

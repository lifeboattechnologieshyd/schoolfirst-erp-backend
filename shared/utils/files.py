"""File handling utilities."""

import mimetypes
import os
import re
import uuid
from typing import Any

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile


def validate_image_temp_path(
    value: str | None,
    user_id: str,
    allowed_extensions: set[str],
) -> str | None:
    """
    Validate that value is a temp path owned by user_id with an allowed extension.

    Returns an error message string on failure, or None on success.
    """
    if value is None:
        return None
    if value.startswith(("http://", "https://")):
        return "Please upload a valid image file."
    expected_prefix = f"temp/{user_id}/"
    if not value.startswith(expected_prefix):
        return "Unable to upload the selected image."
    _, ext = os.path.splitext(value)
    if ext.lower() not in allowed_extensions:
        display = ", ".join(sorted(allowed_extensions))
        return f"Unsupported file type. Allowed types: {display}."
    if not default_storage.exists(value):
        return "The selected image file is no longer available."
    return None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing spaces and special characters,
    and adding a UUID before the extension.

    Args:
        filename: Original filename

    Returns:
        str: Sanitized filename with UUID
    """
    # Split filename and extension
    name, ext = os.path.splitext(filename)

    # Remove spaces and special characters, keep only alphanumeric, underscore, hyphen
    name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    # If name becomes empty, use 'file'
    if not name:
        name = "file"

    # Add UUID before extension
    file_uuid = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID
    sanitized = f"{name}_{file_uuid}{ext}"

    return sanitized


def save_uploaded_file(file: UploadedFile, folder: str = "temp") -> str:
    """
    Save uploaded file to specified folder using default_storage.
    Sanitizes filename by removing spaces and special characters,
    and adds a UUID to ensure uniqueness.

    Args:
        file: Django UploadedFile object
        folder: Folder name (default: 'temp')

    Returns:
        str: Relative path of saved file
    """
    # Sanitize filename
    sanitized_filename = sanitize_filename(file.name)
    file_path = os.path.join(folder, sanitized_filename)

    # Ensure unique filename in case of collision
    counter = 1
    while default_storage.exists(file_path):
        name, ext = os.path.splitext(sanitized_filename)
        file_path = os.path.join(folder, f"{name}_{counter}{ext}")
        counter += 1

    # Save file
    path = default_storage.save(file_path, file)
    return path


def move_file(source_path: str, dest_folder: str) -> str | None:
    """
    Move file from source to destination folder.

    Args:
        source_path: Current file path
        dest_folder: Destination folder name

    Returns:
        str: New file path or None if source doesn't exist
    """
    if not default_storage.exists(source_path):
        return None

    # Get filename from source path
    filename = os.path.basename(source_path)
    dest_path = os.path.join(dest_folder, filename)

    # Ensure unique filename in destination
    counter = 1
    name, ext = os.path.splitext(filename)
    while default_storage.exists(dest_path):
        dest_path = os.path.join(dest_folder, f"{name}_{counter}{ext}")
        counter += 1

    # Read source file
    with default_storage.open(source_path, "rb") as source_file:
        # Save to destination
        dest_path = default_storage.save(dest_path, source_file)

    # Delete source file
    default_storage.delete(source_path)

    return dest_path


def delete_file(file_path: str | None) -> bool:
    """
    Delete file if it exists.

    Args:
        file_path: Path to file to delete

    Returns:
        bool: True if deleted, False if not found
    """
    if file_path and default_storage.exists(file_path):
        default_storage.delete(file_path)
        return True
    return False


def get_file_url(file_path: str | None) -> str | None:
    """
    Get URL for file path.

    Args:
        file_path: Relative file path

    Returns:
        str: URL to access the file
    """
    if not file_path:
        return None
    return default_storage.url(file_path)


def get_public_file_url(file_path: str | None) -> str | None:
    """
    Get public URL for file path without signed tokens.
    Use for files stored in public buckets (e.g., profile pictures).

    Args:
        file_path: Relative file path

    Returns:
        str: Public URL to access the file (without query parameters/tokens)
    """
    if not file_path:
        return None

    # Get the URL from storage backend
    url = default_storage.url(file_path)

    # Remove query parameters (signed tokens) for public files
    if "?" in url:
        url = url.split("?")[0]

    return url


def get_file_info(file_path: str | None) -> dict[str, Any] | None:
    """
    Get metadata information about a file.

    Args:
        file_path: Relative file path

    Returns:
        dict: File metadata (name, size, mime_type) or None if missing
    """
    if not file_path or not default_storage.exists(file_path):
        return None

    try:
        # Get file size
        file_size = default_storage.size(file_path)

        # Get filename from path
        file_name = os.path.basename(file_path)

        # Guess MIME type from file extension
        mime_type, _ = mimetypes.guess_type(file_name)
        if not mime_type:
            mime_type = "application/octet-stream"  # Default for unknown types

        return {
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "file_path": file_path,
        }
    except Exception:
        return None

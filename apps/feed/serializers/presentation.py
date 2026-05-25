from typing import Any, cast
from urllib.parse import urlparse

from apps.core.models import UserMaster
from shared.utils.files import get_public_file_url


def normalize_storage_path(path: str) -> str:
    """Convert a public URL or object key to a storage key."""
    if path.startswith(("http://", "https://")):
        return urlparse(path).path.lstrip("/")
    return path


def resolve_public_storage_url(path: str | None) -> str | None:
    """Return a public S3 URL for a stored object key; pass through absolute URLs."""
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    return get_public_file_url(path)


def resolve_public_storage_urls(paths: list[str] | None) -> list[str]:
    if not paths:
        return []
    return [url for path in cast(list[str], paths) if (url := resolve_public_storage_url(path))]


def build_feed_user_snapshot(user: UserMaster) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "profile_image": resolve_public_storage_url(cast(str | None, user.profile_image)),
    }

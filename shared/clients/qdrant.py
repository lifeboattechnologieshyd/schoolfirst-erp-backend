import structlog
from django.conf import settings
from qdrant_client import QdrantClient

logger = structlog.getLogger("default")

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """
    Return a singleton QdrantClient instance.

    Uses QDRANT_URL (for Qdrant Cloud) if set, otherwise falls back
    to QDRANT_HOST:QDRANT_PORT for local Docker.
    """
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client

    qdrant_url = getattr(settings, "QDRANT_URL", None)
    api_key = getattr(settings, "QDRANT_API_KEY", None)

    if qdrant_url:
        logger.info("Connecting to Qdrant Cloud", url=qdrant_url)
        _client = QdrantClient(url=qdrant_url, api_key=api_key)
    else:
        host = getattr(settings, "QDRANT_HOST", "localhost")
        port = getattr(settings, "QDRANT_PORT", 6333)
        logger.info("Connecting to local Qdrant", host=host, port=port)
        _client = QdrantClient(host=host, port=port, check_compatibility=False)

    return _client

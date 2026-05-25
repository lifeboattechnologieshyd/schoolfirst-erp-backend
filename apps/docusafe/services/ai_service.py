import structlog
from django.conf import settings

from shared.clients.bedrock_embeddings import (
    generate_document_summary,
    generate_embedding,
    generate_embeddings_batch,
)

logger = structlog.getLogger("default")


class DocusafeAIService:
    """
    Wrapper for AI operations (embeddings, summaries).
    Decouples the business logic from the specific AI provider client.
    """

    def generate_embedding(self, text: str) -> list[float]:
        """Generate a single dense embedding."""
        return generate_embedding(text)

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate multiple dense embeddings."""
        return generate_embeddings_batch(texts)

    def generate_summary(self, text: str, file_name: str) -> str:
        """Generate a summary for a document."""
        return generate_document_summary(text, file_name)

    def get_embedding_model_info(self) -> dict[str, object]:
        """Return information about the active embedding model."""
        return {
            "model_id": getattr(settings, "AWS_BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
            "dimensions": getattr(settings, "AWS_BEDROCK_EMBEDDING_DIMENSIONS", 1024),
        }

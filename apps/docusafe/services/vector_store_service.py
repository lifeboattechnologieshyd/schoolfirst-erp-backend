from typing import Protocol, cast

import structlog
from django.conf import settings
from qdrant_client import models

from shared.clients.qdrant import get_qdrant_client

logger = structlog.getLogger("default")


class HybridQueryResponse(Protocol):
    points: list[models.ScoredPoint]


class DocusafeVectorStore:
    """
    Abstraction for Qdrant vector store operations.
    Handles upserts, deletions, and hybrid queries.
    """

    def __init__(self, collection_name: str | None = None):
        self.collection = collection_name or getattr(settings, "QDRANT_COLLECTION", "docusafe_files")
        self.client = get_qdrant_client()

    def upsert_points(self, points: list[models.PointStruct], batch_size: int = 100) -> None:
        """Upsert points into Qdrant in batches."""
        if not points:
            return

        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection,
                points=batch,
            )

        logger.debug("Upserted points to Qdrant", collection=self.collection, count=len(points))

    def delete_by_file_id(self, file_id: str) -> None:
        """Delete all points associated with a specific file_id."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="file_id",
                            match=models.MatchValue(value=file_id),
                        )
                    ]
                )
            ),
        )
        logger.debug("Deleted vectors for file", file_id=file_id)

    def hybrid_search(
        self,
        query_dense: list[float],
        query_sparse: models.SparseVector,
        filter_conditions: list[models.Condition],
        limit: int = 10,
    ) -> HybridQueryResponse:
        """
        Perform hybrid search (dense + sparse) with RRF fusion.
        """
        search_filter = models.Filter(must=filter_conditions)
        prefetch_limit = min(limit * 3, 50)

        return cast(
            HybridQueryResponse,
            self.client.query_points(
                collection_name=self.collection,
                prefetch=[
                    models.Prefetch(
                        query=query_dense,
                        using="text-dense",
                        limit=prefetch_limit,
                        filter=search_filter,
                    ),
                    models.Prefetch(
                        query=query_sparse,
                        using="text-sparse",
                        limit=prefetch_limit,
                        filter=search_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
            ),
        )

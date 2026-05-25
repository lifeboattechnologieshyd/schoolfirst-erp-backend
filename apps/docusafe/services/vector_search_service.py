import structlog
from qdrant_client import models

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.services.access_service import DocusafeAccessService
from apps.docusafe.services.ai_service import DocusafeAIService
from apps.docusafe.services.sparse_encoder import DocusafeSparseEncoder
from apps.docusafe.services.vector_store_service import DocusafeVectorStore
from shared.enums import DocusafeStatus

logger = structlog.getLogger("default")


class DocusafeSearchService:
    """
    Hybrid search service combining dense (semantic) and sparse
    (keyword) search.
    Uses DocusafeAIService, DocusafeSparseEncoder, and DocusafeVectorStore.
    """

    def __init__(self):
        self.ai = DocusafeAIService()
        self.vector_store = DocusafeVectorStore()
        self.sparse_encoder = DocusafeSparseEncoder()

    @classmethod
    def from_adapters(
        cls,
        ai_service: DocusafeAIService,
        vector_store: DocusafeVectorStore,
        sparse_encoder: DocusafeSparseEncoder,
    ):
        instance = cls.__new__(cls)
        instance.ai = ai_service
        instance.vector_store = vector_store
        instance.sparse_encoder = sparse_encoder
        return instance

    def hybrid_search(
        self,
        user_id: str,
        query: str,
        folder_id: str | None = None,
        file_ids: list[str] | None = None,
        accessible_file_ids: list[str] | None = None,
        limit: int = 10,
        deduplicate_by_file: bool = True,
    ) -> list[dict[str, object]]:
        """
        Perform hybrid semantic + keyword search for a user's files.
        """
        normalized_file_ids = [str(file_id) for file_id in file_ids] if file_ids else None
        normalized_accessible_file_ids = (
            [str(file_id) for file_id in accessible_file_ids] if accessible_file_ids else None
        )

        # 1. Prepare Filter
        must_conditions: list[models.Condition] = []
        if normalized_accessible_file_ids:
            must_conditions.append(
                models.FieldCondition(
                    key="file_id",
                    match=models.MatchAny(any=normalized_accessible_file_ids),
                )
            )
        else:
            must_conditions.append(
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                )
            )
            if normalized_file_ids:
                must_conditions.append(
                    models.FieldCondition(
                        key="file_id",
                        match=models.MatchAny(any=normalized_file_ids),
                    )
                )
        if folder_id:
            DocusafeAccessService.validate_folder_access(user_id, folder_id)

            must_conditions.append(
                models.FieldCondition(
                    key="folder_id",
                    match=models.MatchValue(value=folder_id),
                )
            )

        # 2. Generate Query Vectors
        query_dense = self.ai.generate_embedding(query)
        query_sparse = self.sparse_encoder.encode(query)

        # 3. Query Vector Store
        try:
            results = self.vector_store.hybrid_search(
                query_dense=query_dense,
                query_sparse=query_sparse,
                filter_conditions=must_conditions,
                limit=limit,
            )
        except Exception:
            logger.exception("Qdrant hybrid search failed")
            raise

        # 4. Parse & Deduplicate
        ranked_files = self._process_results(results.points, deduplicate_by_file)

        # 5. Enrich with DB metadata
        search_results = self._enrich_metadata(ranked_files, limit)
        if normalized_accessible_file_ids is not None:
            return [
                result for result in search_results if DocusafeAccessService.has_access(user_id, result["file_id"])
            ][:limit]

        return search_results

    def _process_results(
        self, points: list[models.ScoredPoint], deduplicate_by_file: bool = True
    ) -> list[dict[str, object]]:
        """
        Deduplicate results by file_id, keeping the best score.
        Or return all chunks when deduplication is disabled.
        """
        if deduplicate_by_file:
            seen_files = {}
            for point in points:
                payload = point.payload or {}
                file_id = payload.get("file_id", "")
                score = point.score or 0.0

                if file_id not in seen_files or score > seen_files[file_id]["score"]:
                    seen_files[file_id] = {
                        "file_id": file_id,
                        "folder_id": payload.get("folder_id", ""),
                        "score": score,
                        "match_type": payload.get("type", "CHUNK"),
                        "snippet": payload.get("text", "")[:300],
                    }

            return sorted(seen_files.values(), key=lambda x: x["score"], reverse=True)
        else:
            results = []
            for point in points:
                payload = point.payload or {}
                results.append(
                    {
                        "file_id": payload.get("file_id", ""),
                        "folder_id": payload.get("folder_id", ""),
                        "score": point.score or 0.0,
                        "match_type": payload.get("type", "CHUNK"),
                        "snippet": payload.get("text", "")[:700],
                    }
                )
            return sorted(results, key=lambda x: x["score"], reverse=True)

    def _enrich_metadata(self, ranked_files: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
        """Enrich results with metadata from the database."""
        if not ranked_files:
            return []

        file_ids = [r["file_id"] for r in ranked_files]
        files_qs = DocusafeFile.objects.filter(
            id__in=file_ids,
            status=DocusafeStatus.ACTIVE,
        ).only("id", "file_name", "file_extension", "mime_type", "file_size", "folder_id")

        file_map = {str(f.id): f for f in files_qs}

        search_results = []
        for result in ranked_files:
            file_rec = file_map.get(result["file_id"])
            if file_rec:
                result.update(
                    {
                        "file_name": file_rec.file_name,
                        "file_extension": file_rec.file_extension,
                        "mime_type": file_rec.mime_type,
                        "file_size": file_rec.file_size,
                    }
                )
                search_results.append(result)

        return search_results[:limit]

import uuid
from collections.abc import Callable
from typing import cast

import structlog
from qdrant_client import models

from apps.docusafe.constants import (
    EMBEDDABLE_EXTENSIONS,
    EMBEDDING_MAX_FILE_SIZE,
)
from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.services.ai_service import DocusafeAIService
from apps.docusafe.services.parsers import parse_document
from apps.docusafe.services.parsers.document_block import ChunkedDocument, DocumentBlock
from apps.docusafe.services.semantic_chunker import SemanticChunker
from apps.docusafe.services.sparse_encoder import DocusafeSparseEncoder
from apps.docusafe.services.vector_store_service import DocusafeVectorStore
from shared.enums import DocusafeEmbeddingType

logger = structlog.getLogger("default")


class DocusafeEmbeddingService:
    """
    Orchestrates the full embedding pipeline:
    format-aware parsing → semantic chunking → AI processing → Vector Store upsert.

    All five pipeline stages are injectable for testing:
      parse_fn      — replaces the format-aware document parser (reads from S3)
      chunker       — replaces SemanticChunker (pure, but swappable for tests)
      ai_service    — replaces DocusafeAIService (calls Bedrock)
      sparse_encoder— replaces DocusafeSparseEncoder
      vector_store  — replaces DocusafeVectorStore (calls Qdrant)
    """

    def __init__(
        self,
        ai_service: DocusafeAIService | None = None,
        vector_store: DocusafeVectorStore | None = None,
        sparse_encoder: DocusafeSparseEncoder | None = None,
        parse_fn: Callable[..., list[DocumentBlock]] | None = None,
        chunker: type[SemanticChunker] | None = None,
    ):
        self.ai = ai_service or DocusafeAIService()
        self.vector_store = vector_store or DocusafeVectorStore()
        self.sparse_encoder = sparse_encoder or DocusafeSparseEncoder()
        self.parse_fn = parse_fn or parse_document
        self.chunker = chunker or SemanticChunker

    @staticmethod
    def is_embeddable(file_rec: DocusafeFile) -> bool:
        """Check if a file is eligible for embedding."""
        if file_rec.file_extension not in EMBEDDABLE_EXTENSIONS:
            return False
        if file_rec.file_size > EMBEDDING_MAX_FILE_SIZE:
            return False
        return bool(file_rec.file_path) and file_rec.file_path != "PENDING_UPLOAD"

    def process_file(self, file_rec: DocusafeFile, owner_id: str) -> bool:
        """
        Run the full embedding pipeline for a single file.

        Args:
            file_rec: The DocusafeFile record.
            owner_id: Owner UUID string (avoids N+1 folder query).

        Returns:
            True if embeddings were generated and upserted, False if no text.
        """
        file_id = str(file_rec.id)
        file_name = str(file_rec.file_name)
        file_path = str(file_rec.file_path)
        file_extension = str(file_rec.file_extension)
        file_size = cast(int, file_rec.file_size)

        logger.info("Processing file for embeddings", file_id=file_id, file_name=file_name)

        # 1. Parse
        doc_blocks = self.parse_fn(file_path=file_path, file_extension=file_extension, file_size=file_size)
        if not doc_blocks:
            logger.warning("No blocks extracted from file", file_id=file_id)
            return False

        # 2. Extract full text for summary
        total_text = " ".join(b.text for b in doc_blocks).strip()
        if not total_text:
            logger.warning("All blocks are empty", file_id=file_id)
            return False

        # 3. Chunk
        chunks = self.chunker.chunk_blocks(doc_blocks)
        logger.info("Text chunked (semantic)", file_id=file_id, chunk_count=len(chunks))

        # 4. Generate Summary
        summary = self.ai.generate_summary(total_text, file_name)
        model_info = self.ai.get_embedding_model_info()

        # 5. Update DB
        model_id = str(model_info["model_id"])
        self._update_db_record(file_rec, model_id, summary)

        # 6. Build Vector Points
        points = self._build_vector_points(file_rec, owner_id, chunks, summary, model_id)

        # 7. Upsert to Vector Store
        self.vector_store.delete_by_file_id(file_id)
        self.vector_store.upsert_points(points)

        return True

    def _update_db_record(self, file_rec: DocusafeFile, embedding_model: str, summary: str) -> None:
        update_data = {"embedding_model": embedding_model}
        if summary:
            update_data["summary"] = summary
        DocusafeFile.objects.filter(id=file_rec.id).update(**update_data)

    def _build_vector_points(
        self, file_rec: DocusafeFile, owner_id: str, chunks: list[ChunkedDocument], summary: str, embedding_model: str
    ) -> list[models.PointStruct]:
        file_id = str(file_rec.id)
        file_name = str(file_rec.file_name)
        folder_id = getattr(file_rec, "folder_id", None)
        base_metadata = {
            "user_id": owner_id,
            "folder_id": str(folder_id) if folder_id is not None else "",
            "file_id": file_id,
            "embedding_model": embedding_model,
        }
        points: list[models.PointStruct] = []

        # Create point for title
        points.append(
            self._create_point(file_name, file_id, DocusafeEmbeddingType.TITLE, 0, base_metadata, {"text": file_name})
        )

        # Create point for summary
        if summary:
            points.append(
                self._create_point(summary, file_id, DocusafeEmbeddingType.SUMMARY, 0, base_metadata, {"text": summary})
            )

        # Create points for chunks
        if chunks:
            chunk_texts = [c.text for c in chunks]
            chunk_embeddings = self.ai.generate_embeddings_batch(chunk_texts)

            for idx, (chunk, chunk_dense) in enumerate(zip(chunks, chunk_embeddings, strict=True)):
                chunk_sparse = self.sparse_encoder.encode(chunk.text)
                point_id = self._make_point_id(file_id, DocusafeEmbeddingType.CHUNK, idx)
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector={"text-dense": chunk_dense, "text-sparse": chunk_sparse},
                        payload={
                            **base_metadata,
                            "type": DocusafeEmbeddingType.CHUNK,
                            "chunk_index": idx,
                            "text": chunk.text,
                            "page_index": chunk.page_index,
                            "section": chunk.section,
                            "block_types": chunk.block_types,
                        },
                    )
                )

        return points

    def _create_point(
        self,
        text: str,
        file_id: str,
        point_type: str,
        chunk_index: int,
        base_meta: dict[str, str],
        extra_meta: dict[str, object],
    ) -> models.PointStruct:
        dense = self.ai.generate_embedding(text)
        sparse = self.sparse_encoder.encode(text)
        point_id = self._make_point_id(file_id, point_type, chunk_index)
        return models.PointStruct(
            id=point_id,
            vector={"text-dense": dense, "text-sparse": sparse},
            payload={**base_meta, "type": point_type, "chunk_index": chunk_index, **extra_meta},
        )

    def _make_point_id(self, file_id: str, embedding_type: str, chunk_index: int) -> str:
        namespace = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        key = f"{file_id}:{embedding_type}:{chunk_index}"
        return str(uuid.uuid5(namespace, key))

    def delete_file_vectors(self, file_id: str) -> None:
        """Delete all vectors for a file from the vector store."""
        self.vector_store.delete_by_file_id(file_id)

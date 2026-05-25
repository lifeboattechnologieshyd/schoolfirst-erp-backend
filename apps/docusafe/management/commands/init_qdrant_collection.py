import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from qdrant_client import models

from shared.clients.qdrant import get_qdrant_client

logger = structlog.getLogger("default")


class Command(BaseCommand):
    help = "Initialize the Qdrant collection for Docusafe file embeddings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="Drop and recreate the collection (WARNING: deletes all vectors).",
        )

    def handle(self, *args, **options):
        collection_name = getattr(settings, "QDRANT_COLLECTION", "docusafe_files")
        dimensions = getattr(settings, "EMBEDDING_DIMENSIONS", 1024)
        recreate = options.get("recreate", False)

        client = get_qdrant_client()

        # Check if collection already exists
        existing = [c.name for c in client.get_collections().collections]

        if collection_name in existing:
            if recreate:
                self.stdout.write(self.style.WARNING(f"Dropping existing collection: {collection_name}"))
                client.delete_collection(collection_name)
            else:
                self.stdout.write(self.style.SUCCESS(f"Collection '{collection_name}' already exists. Skipping."))
                return

        # Create collection with named vectors (dense + sparse)
        self.stdout.write(f"Creating collection '{collection_name}' with {dimensions}-dim dense vectors...")

        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "text-dense": models.VectorParams(
                    size=dimensions,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "text-sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False),
                ),
            },
        )

        # Create payload indexes for filtering
        self.stdout.write("Creating payload indexes...")

        for field_name in ["user_id", "folder_id", "file_id", "type"]:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

        self.stdout.write(self.style.SUCCESS(f"Collection '{collection_name}' created successfully."))
        self.stdout.write(
            f"  Dense vectors: {dimensions}-dim, Cosine distance\n"
            f"  Sparse vectors: text-sparse (BM25-style)\n"
            f"  Indexed fields: user_id, folder_id, file_id, type"
        )

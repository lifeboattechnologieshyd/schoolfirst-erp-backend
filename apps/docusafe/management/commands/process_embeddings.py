import structlog
from django.core.management.base import BaseCommand

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.folder import DocusafeFolder
from apps.docusafe.services.embedding_service import DocusafeEmbeddingService
from shared.enums import DocusafeLLMStatus, DocusafeStatus
from shared.helpers.crons import acquire_db_lock, release_db_lock

logger = structlog.getLogger("default")

JOB_NAME = "process_docusafe_embeddings"


class Command(BaseCommand):
    help = "Process pending Docusafe files for vector embeddings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Number of files to process per run (default: 10).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List pending files without processing them.",
        )
        parser.add_argument(
            "--file-id",
            type=str,
            default=None,
            help="Process a specific file by ID (bypasses lock and batch size).",
        )
        parser.add_argument(
            "--reprocess-all",
            action="store_true",
            help=(
                "Reset all COMPLETED and FAILED files back to PENDING, "
                "delete their existing Qdrant vectors, and re-queue them "
                "for processing with the current pipeline."
            ),
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        file_id = options.get("file_id")
        reprocess_all = options.get("reprocess_all", False)

        # Create service instance once — reused across the entire batch
        self.embedding_service = DocusafeEmbeddingService()

        # Process a specific file (for debugging)
        if file_id:
            self._process_single(file_id)
            return

        # Reprocess all completed/failed files
        if reprocess_all:
            self._reprocess_all(dry_run)
            return

        # Acquire lock to prevent overlapping cron runs
        if not acquire_db_lock(JOB_NAME):
            self.stdout.write(self.style.WARNING("Lock not acquired. Another instance is running."))
            return

        try:
            self._process_batch(batch_size, dry_run)
        finally:
            release_db_lock(JOB_NAME)

    def _process_batch(self, batch_size: int, dry_run: bool):
        """Process a batch of pending files."""
        # Query files that need embedding processing, join with folder for owner_id
        pending_files = (
            DocusafeFile.objects.filter(
                llm_status=DocusafeLLMStatus.PENDING,
                status=DocusafeStatus.ACTIVE,
            )
            .exclude(file_path="PENDING_UPLOAD")
            .order_by("created_at")[:batch_size]
        )

        count = pending_files.count()
        if count == 0:
            self.stdout.write("No pending files to process.")
            return

        self.stdout.write(f"Found {count} pending file(s) to process.")

        if dry_run:
            for f in pending_files:
                self.stdout.write(f"  [DRY RUN] {f.id} — {f.file_name} ({f.file_extension}, {f.file_size} bytes)")
            return

        # Pre-fetch folder → owner_id mapping to avoid N+1 queries
        folder_ids = {f.folder_id for f in pending_files}
        owner_map = dict(DocusafeFolder.objects.filter(id__in=folder_ids).values_list("id", "owner_id"))

        processed = 0
        failed = 0

        for file_rec in pending_files:
            owner_id = str(owner_map.get(file_rec.folder_id, ""))
            if not owner_id:
                logger.warning(
                    "Folder not found for file, skipping",
                    file_id=str(file_rec.id),
                    folder_id=str(file_rec.folder_id),
                )
                DocusafeFile.objects.filter(id=file_rec.id).update(llm_status=DocusafeLLMStatus.FAILED)
                failed += 1
                continue

            success = self._process_file(file_rec, owner_id)
            if success:
                processed += 1
            else:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Completed: {processed} processed, {failed} failed out of {count} files.")
        )

    def _process_file(self, file_rec: DocusafeFile, owner_id: str) -> bool:
        """Process a single file through the embedding pipeline."""
        file_id = str(file_rec.id)

        # Check if file is embeddable
        if not DocusafeEmbeddingService.is_embeddable(file_rec):
            self.stdout.write(f"  [{file_id}] Not embeddable — marking as NOT_SUPPORTED")
            DocusafeFile.objects.filter(id=file_rec.id).update(llm_status=DocusafeLLMStatus.NOT_SUPPORTED)
            return True  # Not an error, just unsupported

        # Set status to PROCESSING
        DocusafeFile.objects.filter(id=file_rec.id).update(llm_status=DocusafeLLMStatus.PROCESSING)

        try:
            result = self.embedding_service.process_file(file_rec, owner_id)

            if result:
                DocusafeFile.objects.filter(id=file_rec.id).update(llm_status=DocusafeLLMStatus.COMPLETED)
                self.stdout.write(self.style.SUCCESS(f"  [{file_id}] {file_rec.file_name} — COMPLETED"))
                return True
            else:
                # No text extracted — mark as not supported
                DocusafeFile.objects.filter(id=file_rec.id).update(llm_status=DocusafeLLMStatus.NOT_SUPPORTED)
                self.stdout.write(f"  [{file_id}] {file_rec.file_name} — No text (NOT_SUPPORTED)")
                return True

        except Exception as e:
            logger.exception("Embedding processing failed", file_id=file_id, error=str(e))
            DocusafeFile.objects.filter(id=file_rec.id).update(llm_status=DocusafeLLMStatus.FAILED)
            self.stderr.write(self.style.ERROR(f"  [{file_id}] {file_rec.file_name} — FAILED: {e}"))
            return False

    def _process_single(self, file_id: str):
        """Process a single file by ID (debug mode)."""
        try:
            file_rec = DocusafeFile.objects.get(id=file_id, status=DocusafeStatus.ACTIVE)
        except DocusafeFile.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"File {file_id} not found or not active."))
            return

        # Resolve owner_id for the single file
        try:
            folder = DocusafeFolder.objects.get(id=file_rec.folder_id)
            owner_id = str(folder.owner_id)
        except DocusafeFolder.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Folder {file_rec.folder_id} not found for file {file_id}."))
            return

        self.stdout.write(f"Processing single file: {file_rec.file_name} ({file_rec.file_extension})")
        self._process_file(file_rec, owner_id)

    def _reprocess_all(self, dry_run: bool):
        """
        Reset all COMPLETED and FAILED files back to PENDING.

        Deletes existing Qdrant vectors for each file so they get
        re-processed with the current (improved) pipeline.
        """
        reprocessable_statuses = [DocusafeLLMStatus.COMPLETED, DocusafeLLMStatus.FAILED]

        files_to_reset = DocusafeFile.objects.filter(
            llm_status__in=reprocessable_statuses,
            status=DocusafeStatus.ACTIVE,
        ).exclude(file_path="PENDING_UPLOAD")

        count = files_to_reset.count()

        if count == 0:
            self.stdout.write("No files to reprocess.")
            return

        self.stdout.write(f"Found {count} file(s) to reprocess (COMPLETED + FAILED → PENDING).")

        if dry_run:
            dry_run_preview_limit = 50
            for f in files_to_reset[:dry_run_preview_limit]:
                self.stdout.write(f"  [DRY RUN] {f.id} — {f.file_name} ({f.file_extension}, status={f.llm_status})")
            if count > dry_run_preview_limit:
                self.stdout.write(f"  ... and {count - dry_run_preview_limit} more files.")
            return

        # Delete existing Qdrant vectors for each file
        deleted_vectors = 0
        for file_rec in files_to_reset.only("id"):
            try:
                self.embedding_service.delete_file_vectors(str(file_rec.id))
                deleted_vectors += 1
            except Exception as e:
                logger.warning(
                    "Failed to delete vectors during reprocess",
                    file_id=str(file_rec.id),
                    error=str(e),
                )

        # Bulk reset all statuses to PENDING
        updated = files_to_reset.update(llm_status=DocusafeLLMStatus.PENDING)

        self.stdout.write(
            self.style.SUCCESS(
                f"Reprocess complete: {updated} files reset to PENDING, "
                f"{deleted_vectors} vector sets deleted from Qdrant. "
                f"Files will be re-processed on the next cron run."
            )
        )

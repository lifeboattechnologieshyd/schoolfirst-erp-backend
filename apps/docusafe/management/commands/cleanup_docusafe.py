import structlog
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.docusafe.models.file import DocusafeFile
from apps.docusafe.models.folder import DocusafeFolder
from shared.enums import DocusafeStatus

logger = structlog.getLogger("default")


class Command(BaseCommand):
    help = "Permanently delete Docusafe files from S3 and hard-delete rows marked as DELETED."

    def handle(self, *args, **options):
        self.stdout.write("Starting Docusafe cleanup...")

        # 1. Process DELETED files
        deleted_files = DocusafeFile.objects.filter(status=DocusafeStatus.DELETED)
        file_count = deleted_files.count()

        for file_rec in deleted_files:
            file_id = file_rec.id
            file_path = file_rec.file_path

            try:
                with transaction.atomic():
                    # Delete vectors from Qdrant
                    try:
                        from apps.docusafe.services.embedding_service import (  # noqa: PLC0415
                            DocusafeEmbeddingService,
                        )

                        embedding_service = DocusafeEmbeddingService()
                        embedding_service.delete_file_vectors(str(file_id))
                        self.stdout.write(f"Deleted Qdrant vectors for file: {file_id}")
                    except Exception as ve:
                        logger.warning("Failed to delete vectors (non-fatal)", file_id=file_id, error=str(ve))

                    # Delete from S3 if path exists and isn't a placeholder
                    if file_path and file_path != "PENDING_UPLOAD" and default_storage.exists(file_path):
                        default_storage.delete(file_path)
                        self.stdout.write(f"Deleted S3 object: {file_path}")

                    # Hard delete DB row
                    file_rec.delete()
                    self.stdout.write(f"Hard-deleted File record: {file_id}")
            except Exception as e:
                logger.exception("Failed to cleanup Docusafe file", file_id=file_id, error=str(e))
                self.stderr.write(f"Error cleaning up file {file_id}: {str(e)}")

        self.stdout.write(self.style.SUCCESS(f"Successfully processed {file_count} files."))

        # 2. Process DELETED folders
        # A folder can be deleted if its status is DELETED and
        # it has no ACTIVE or DELETED files left in DB
        deleted_folders = DocusafeFolder.objects.filter(status=DocusafeStatus.DELETED)
        folder_count = 0

        for folder in deleted_folders:
            folder_id = folder.id
            # Check if any files still reference this folder
            # (including ACTIVE ones for safety)
            if not DocusafeFile.objects.filter(folder_id=folder_id).exists():
                try:
                    folder.delete()
                    folder_count += 1
                    self.stdout.write(f"Hard-deleted Folder record: {folder_id}")
                except Exception as e:
                    logger.exception("Failed to cleanup Docusafe folder", folder_id=folder_id, error=str(e))
                    self.stderr.write(f"Error cleaning up folder {folder_id}: {str(e)}")
            else:
                self.stdout.write(f"Folder {folder_id} still has files. Skipping.")

        self.stdout.write(self.style.SUCCESS(f"Successfully processed {folder_count} folders."))
        self.stdout.write("Docusafe cleanup complete.")

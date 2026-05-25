"""
Cleanup temporary files older than 24 hours from object storage.
Run daily to remove uploaded files that were never attached to messages.
"""

from datetime import timedelta

import structlog
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone

from shared.helpers.crons import acquire_db_lock, release_db_lock

logger = structlog.get_logger("default")


class Command(BaseCommand):
    help = "Cleanup temporary files older than 24 hours from temp folder"

    def _delete_if_expired(self, file_path, cutoff_time):
        """Delete file if older than cutoff_time. Returns (deleted, errored)."""
        try:
            try:
                modified_time = default_storage.get_modified_time(file_path)
                if timezone.is_naive(modified_time):
                    modified_time = timezone.make_aware(modified_time)
                if modified_time < cutoff_time:
                    default_storage.delete(file_path)
                    age_hours = (timezone.now() - modified_time).total_seconds() / 3600
                    logger.debug("Deleted old temp file", file=file_path, age_hours=age_hours)
                    return True, False
            except NotImplementedError:
                logger.warning("Storage backend does not support get_modified_time", file=file_path)
                return False, True
        except Exception as e:
            logger.exception("Error processing temp file", file=file_path, error=str(e))
            return False, True
        return False, False

    def _collect_scopes(self, temp_folder):
        """Return list of (folder, files) tuples covering temp/ and all user subdirs."""
        user_directories, root_files = default_storage.listdir(temp_folder)
        scopes = [(temp_folder, root_files)]
        for user_dir in user_directories:
            user_folder = f"{temp_folder}/{user_dir}"
            try:
                _, user_files = default_storage.listdir(user_folder)
                scopes.append((user_folder, user_files))
            except Exception as e:
                logger.exception("Error listing user temp folder", folder=user_folder, error=str(e))
        return scopes

    def handle(self, *args, **options):
        """
        Clean up temporary files:
        1. Iterate temp/{user_id}/ subdirectories
        2. Check each file's modification time
        3. Delete files older than 24 hours
        """
        job_name = "cleanup_temp_files"

        if not acquire_db_lock(job_name):
            self.stdout.write(
                self.style.WARNING(f"Could not acquire lock for job '{job_name}'. Another instance may be running.")
            )
            logger.warning("Could not acquire lock for cleanup_temp_files job")
            return

        try:
            self.stdout.write("Starting temporary files cleanup...")
            logger.info("Starting temporary files cleanup")

            temp_folder = "temp"
            deleted_count = 0
            error_count = 0
            total_checked = 0
            cutoff_time = timezone.now() - timedelta(hours=24)

            try:
                scopes = self._collect_scopes(temp_folder)

                for folder, files in scopes:
                    for filename in files:
                        file_path = f"{folder}/{filename}"
                        total_checked += 1
                        deleted, errored = self._delete_if_expired(file_path, cutoff_time)
                        if deleted:
                            deleted_count += 1
                        if errored:
                            error_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nCleanup Summary:"
                        f"\n  - Files deleted: {deleted_count}"
                        f"\n  - Errors: {error_count}"
                        f"\n  - Total files checked: {total_checked}"
                    )
                )
                logger.info(
                    "Temporary files cleanup completed",
                    deleted_count=deleted_count,
                    error_count=error_count,
                    total_files=total_checked,
                )

                self.stdout.write(self.style.SUCCESS("\nTemporary files cleanup completed successfully!"))

            except FileNotFoundError:
                self.stdout.write(self.style.WARNING("Temp folder not found - nothing to clean"))
                logger.info("Temp folder not found")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error accessing temp folder: {str(e)}"))
                logger.exception("Error accessing temp folder", error=str(e))

        finally:
            # Always release lock
            release_db_lock(job_name)
            logger.debug("Released lock for cleanup_temp_files job")

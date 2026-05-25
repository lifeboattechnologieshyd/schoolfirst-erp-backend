import structlog
from django.core.management.base import BaseCommand

from apps.docusafe.services.share_owner_service import DocusafeShareOwnerService

logger = structlog.getLogger("default")


class Command(BaseCommand):
    help = "Daily cleanup for expired temporary file shares."

    def handle(self, *args, **options):
        self.stdout.write("Starting cleanup of expired temporary shares...")

        try:
            count = DocusafeShareOwnerService.process_expired_shares()
            self.stdout.write(self.style.SUCCESS(f"Successfully expired {count} shares."))
        except Exception as e:
            logger.exception("Cleanup of expired shares failed", error=str(e))
            self.stdout.write(self.style.ERROR(f"Cleanup failed: {str(e)}"))

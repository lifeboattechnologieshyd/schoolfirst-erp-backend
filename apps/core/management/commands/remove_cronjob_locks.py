import structlog
from django.core.management.base import BaseCommand

from apps.core.models import CronJobLocks

logger = structlog.get_logger("default")


class Command(BaseCommand):
    help = "Remove all cron job locks"

    def handle(self, *args, **options):
        try:
            pending_locks = CronJobLocks.objects.filter(acquired=True)
            self.stdout.write(f"Found {pending_locks.count()} acquired cron job locks to remove.")
            pending_locks.update(acquired=False)
            self.stdout.write(self.style.SUCCESS("✅ Successfully removed all acquired cron job locks"))  # pyright: ignore[reportAttributeAccessIssue]
        except Exception:
            self.stdout.write(self.style.ERROR("❌ Error removing cron job locks"))  # pyright: ignore[reportAttributeAccessIssue]
            logger.error("Error removing cron job locks", exc_info=True)

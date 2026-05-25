"""
Cleanup expired authentication data (OTPs and invitation codes).
Run daily to remove old OTPs and mark expired invite codes as inactive.
"""

from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import OTP, InvitationCode

logger = structlog.get_logger("default")


class Command(BaseCommand):
    help = "Cleanup expired OTPs and invitation codes"

    def handle(self, *args, **options):
        """
        Clean up expired authentication data:
        1. Delete OTPs older than 24 hours
        2. Mark expired invitation codes as inactive (preserve for audit)
        """
        self.stdout.write("Starting authentication data cleanup...")
        logger.info("Starting authentication data cleanup")

        # Cleanup expired OTPs (older than 24 hours)
        otp_cutoff = timezone.now() - timedelta(hours=24)
        deleted_otps = OTP.objects.filter(created_at__lt=otp_cutoff).delete()[0]

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_otps} OTP records older than 24 hours"))
        logger.info("OTP cleanup completed", deleted_count=deleted_otps)

        # Mark expired invitation codes as inactive
        now = timezone.now()
        expired_invites = InvitationCode.objects.filter(
            is_active=True,
            expires_at__lt=now,
        )
        expired_count = expired_invites.count()
        expired_invites.update(is_active=False)

        self.stdout.write(self.style.SUCCESS(f"Marked {expired_count} invitation codes as inactive (expired)"))
        logger.info("Invitation code cleanup completed", marked_inactive=expired_count)

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCleanup Summary:\n  - OTPs deleted: {deleted_otps}\n  - Invite codes deactivated: {expired_count}"
            )
        )
        logger.info(
            "Authentication data cleanup completed",
            deleted_otps=deleted_otps,
            expired_invites=expired_count,
        )

        self.stdout.write(self.style.SUCCESS("\nAuthentication data cleanup completed successfully!"))

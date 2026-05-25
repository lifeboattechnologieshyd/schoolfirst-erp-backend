"""
Management command to create an admin user with profile for testing.
"""

from django.core.management.base import BaseCommand

from apps.core.models import UserMaster
from shared.enums import UserStatus


class Command(BaseCommand):
    help = "Create an admin user with profile (email: admin@samsr.us)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="admin@samsr.us",
            help="Email address for the admin user (default: admin@samsr.us)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="Admin@123",
            help="Password for the admin user (default: Admin@123)",
        )
        parser.add_argument(
            "--first-name",
            type=str,
            default="Admin",
            help="First name for the admin user (default: Admin)",
        )
        parser.add_argument(
            "--last-name",
            type=str,
            default="User",
            help="Last name for the admin user (default: User)",
        )

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        first_name = options["first_name"]
        last_name = options["last_name"]

        # Check if user already exists
        if UserMaster.objects.filter(email=email).exists():
            user = UserMaster.objects.get(email=email)
            self.stdout.write(self.style.WARNING(f"User with email {email} already exists!"))
            self.stdout.write(f"User ID: {user.id}")
            self.stdout.write(f"Email: {user.email}")
            self.stdout.write(f"Is Staff: {user.is_staff}")
            self.stdout.write(f"Status: {user.status}")

            # Update details if not set
            updated = False
            if not user.first_name:
                user.first_name = first_name
                updated = True
            if not user.last_name:
                user.last_name = last_name
                updated = True

            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS("✅ User name details updated!"))
                self.stdout.write(f"Name: {user.first_name} {user.last_name}")
            else:
                self.stdout.write(f"Name already set: {user.first_name} {user.last_name}")
            return

        # Create admin user
        user = UserMaster.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.ACTIVE,
            is_active=True,
            is_staff=True,
        )
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("✅ Admin user created successfully!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"User ID: {user.id}")
        self.stdout.write(f"Email: {email}")
        self.stdout.write(f"Password: {password}")
        self.stdout.write(f"Status: {user.status}")
        self.stdout.write(f"Is Staff: {user.is_staff}")
        self.stdout.write(self.style.SUCCESS("-" * 60))
        self.stdout.write(f"Name: {user.first_name} {user.last_name}")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.WARNING("\n⚠️  Please change the password after first login!"))
        self.stdout.write("\nYou can now use this user to:")
        self.stdout.write("  1. Login via email/password")
        self.stdout.write("  2. Generate invitation codes")
        self.stdout.write("  3. Test the full authentication flow")
        self.stdout.write("  4. Access profile endpoints")
        self.stdout.write(self.style.SUCCESS("=" * 60))

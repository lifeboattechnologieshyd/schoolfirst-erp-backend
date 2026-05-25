import os
import sys

import django
from dotenv import load_dotenv

# Setup Django environment
BASE_DIR = "/Users/karthiknarayan/veto/schoolfirst-backend"
sys.path.append(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.development")
django.setup()

import structlog

from apps.core.models.family import Family, FamilyMember
from apps.core.models.user import UserMaster

logger = structlog.get_logger(__name__)


def setup_test_data():
    owner_email = "test@example.com"
    guest_email = "admin@schoolfirst.us"

    owner = UserMaster.objects.filter(email=owner_email).first()
    guest = UserMaster.objects.filter(email=guest_email).first()

    if not owner or not guest:
        logger.error("Users not found", owner_email=owner_email, guest_email=guest_email)
        return

    # 1. Create family for owner if not exists
    family, created = Family.objects.get_or_create(
        owner=owner,
        defaults={"name": "Playwright Test Family", "icon": "🧪", "description": "Family for end-to-end tests"},
    )
    if created:
        logger.info("Created family", family_name=family.name)
    else:
        logger.info("Using existing family", family_name=family.name)

    # 2. Ensure owner is a joined MEMBER/OWNER
    FamilyMember.objects.get_or_create(
        family=family,
        user=owner,
        defaults={
            "role": FamilyMember.Role.OWNER,
            "status": FamilyMember.Status.JOINED,
            "invited_by": owner,
            "f_name": "Test",
            "l_name": "Owner",
            "gender": "Other",
            "email": owner_email,
            "relation": "Self",
        },
    )

    # 3. Ensure guest is a joined member in the SAME family
    guest_member, created = FamilyMember.objects.get_or_create(
        family=family,
        user=guest,
        defaults={
            "role": FamilyMember.Role.MEMBER,
            "status": FamilyMember.Status.JOINED,
            "invited_by": owner,
            "f_name": "Test",
            "l_name": "Guest",
            "gender": "Other",
            "email": guest_email,
            "relation": "Friend",
        },
    )
    if created:
        logger.info("Added guest to family", guest_email=guest_email)
    # If exists but is not joined, update it
    elif guest_member.status != FamilyMember.Status.JOINED:
        guest_member.status = FamilyMember.Status.JOINED
        guest_member.save()
        logger.info("Updated existing guest membership to joined", guest_email=guest_email)
    else:
        logger.info("Guest is already a joined member", guest_email=guest_email)


if __name__ == "__main__":
    setup_test_data()

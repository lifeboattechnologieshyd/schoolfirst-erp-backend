"""
Invitation code helper functions for generating, validating, and managing invite codes.
"""

import secrets
import string
from datetime import timedelta

import structlog
from django.utils.timezone import now

from apps.core.models import InvitationCode

logger = structlog.get_logger("default")


def generate_invite_code(length: int = 6) -> str:
    """
    Generate a cryptographically secure numeric invite code.
    Format: 6 decimal digits (0-9).
    Example: 482019, 739164

    Args:
        length: Length of the code (default: 6)

    Returns:
        Generated invite code (e.g., "482019")
    """
    code = "".join(secrets.choice(string.digits) for _ in range(length))
    return code


def create_invitation_code(
    created_by_user_id=None, code_type="generic", target_email=None, max_uses=1, expires_in_days=30
):
    """
    Create a new invitation code in the database.
    """
    code = generate_invite_code()
    # Ensure uniqueness
    while InvitationCode.objects.filter(code=code).exists():
        code = generate_invite_code()

    expires_at = now() + timedelta(days=expires_in_days)

    return InvitationCode.objects.create(
        code=code,
        code_type=code_type,
        target_email=target_email,
        max_uses=max_uses,
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
        is_active=True,
    )


def validate_invite_code(code, email=None):
    """
    Validate an invitation code.
    Returns (is_valid, error_message, invite_object)
    """
    invite = InvitationCode.objects.filter(code=code).first()

    if not invite:
        return False, "Invalid invitation code", None

    if not invite.is_active:
        return False, "This invitation code is no longer active", invite

    if invite.expires_at and invite.expires_at < now():
        return False, "This invitation code has expired", invite

    if invite.current_uses >= invite.max_uses:
        return False, "This invitation code has reached its usage limit", invite

    if invite.code_type == "targeted" and email and invite.target_email.lower() != email.lower():
        return False, "This invitation code is not valid for your email address", invite

    return True, None, invite


def ensure_targeted_invite(email: str) -> str:
    """
    Return an active targeted invite code for the given email.
    Reuses an existing active code if found; creates a new one otherwise.
    Returns the invite code string.
    """
    existing = InvitationCode.objects.filter(target_email=email, code_type="TARGETED", is_active=True).first()
    if existing:
        return existing.code

    code = generate_invite_code()
    InvitationCode.objects.create(
        code=code,
        code_type="TARGETED",
        target_email=email,
        is_active=True,
    )
    return code

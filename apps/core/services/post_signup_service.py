import structlog

from apps.core.models import UserMaster
from apps.core.services.close_group_service import CloseGroupService
from apps.core.services.family_service import FamilyService

logger = structlog.get_logger("default")


class PostSignupService:
    """
    Resolves all pending membership invitations for a newly-registered user.

    AuthService calls a single hook here instead of importing family and
    close-group services directly. Adding a third invitation type is a single
    addition here — auth_service never needs to change.
    """

    @staticmethod
    def resolve_pending_invites(email: str, user: UserMaster) -> None:
        """
        Run all post-signup invitation resolution steps for *user*.

        Currently resolves:
          - Family invitation codes addressed to *email*
          - Close Group invitation codes addressed to *email*
        """
        FamilyService.resolve_pending_invites(email=email, user=user)
        CloseGroupService.resolve_pending_invites(email=email, user=user)
        logger.info("Post-signup invite resolution complete", user_id=str(user.id))

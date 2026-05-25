"""
Tool to invite a member to a family by email.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models.family import FamilyMember
from apps.core.services.family_service import FamilyService

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

INVITE_FAMILY_MEMBER_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=8, max_timeout_seconds=30)


@tool
def invite_family_member(
    family_id: str,
    email: str,
    relation: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Invite a person to join a family by their email address.

    The current user must be the owner of the family to send an invite.
    An optional relation label can be provided using one of the valid enum
    values: spouse, parent, child, brother, sister, grandparent,
    grandchild, aunt, uncle, cousin, in_law, friend, other.
    If the person already has a SamsR account, they will receive a notification.
    If not, they will receive an invite email to join SamsR.

    Use get_my_families first to get the correct family_id.

    Args:
        family_id (str): The UUID of the family to invite the person to.
        email (str): The email address of the person to invite.
        relation (str): The relationship as one of the valid values,
            e.g. "sister" or "friend". Pass an empty string if no relation
            is specified.

    Returns:
        str: Confirmation or an error message.
    """
    relation_clean = relation.strip() if relation else None
    logger.info(
        "Executing invite_family_member",
        family_id=family_id,
        email=email,
        relation=relation_clean,
        tool_call_id=tool_call_id,
    )
    with ToolExecution(
        "invite_family_member",
        tool_call_id,
        config,
        {"family_id": family_id, "email": email, "relation": relation_clean},
        f"Inviting {email} to family",
        INVITE_FAMILY_MEMBER_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        if not email or not email.strip():
            return "Please provide the email address of the person you want to invite."

        if not family_id or not family_id.strip():
            return "Please provide the family ID. Use get_my_families to find it."

        try:
            execution.run(
                FamilyService.add_member,
                family_id=family_id.strip(),
                owner_id=execution.user_id,
                email=email.strip().lower(),
                relation=relation_clean or None,
            )

            relation_label = None
            if relation_clean:
                normalized_relation = relation_clean.strip().lower().replace(" ", "_")
                relation_label = FamilyMember.Relation(normalized_relation).label

            relation_note = f" as {relation_label}" if relation_label else ""
            return execution.stop(
                {"success": True},
                "Invite sent",
                f"Invitation sent to **{email}**{relation_note}. They will receive an email to join the family.",
            )

        except ToolTimeoutError:
            logger.warning(
                "Inviting family member timed out",
                family_id=family_id,
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Inviting family member timed out",
                "I couldn't finish sending that invite before the request timed out. Please try again.",
            )

        except PermissionDenied as e:
            msg = str(e.detail) if hasattr(e, "detail") else str(e)
            logger.warning("Permission denied in invite_family_member", user_id=execution.user_id, error=msg)
            return execution.fail(
                msg, "Permission denied", f"You don't have permission to invite members to this family: {msg}"
            )

        except ValidationError as e:
            detail = e.detail
            if isinstance(detail, dict):
                msg = " ".join(str(v[0]) if isinstance(v, list) else str(v) for v in detail.values())
            elif isinstance(detail, list):
                msg = str(detail[0])
            else:
                msg = str(detail)

            logger.warning("Validation error in invite_family_member", user_id=execution.user_id, error=msg)
            return execution.fail(msg, "Failed to send invite", f"Could not send the invite: {msg}")

        except Exception as e:
            logger.exception("Failed to invite family member", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to send invite", "An error occurred while sending the invite. Please try again."
            )

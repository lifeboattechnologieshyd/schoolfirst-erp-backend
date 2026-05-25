"""
Tool to add a member to the current user's close group.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from rest_framework.exceptions import ValidationError
from typing_extensions import TypedDict

from apps.core.models.close_group import CloseGroupMember
from apps.core.models.user import UserMaster
from apps.core.services.close_group_service import CloseGroupService

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

ADD_CLOSE_GROUP_MEMBER_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=8, max_timeout_seconds=30)


class AddCloseGroupMemberResult(TypedDict, total=False):
    status: str
    member_status: str


@tool
def add_close_group_member(
    email: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Add a person to the current user's close group by their email address.

    If the person already has a SamsR account they are added immediately with
    JOINED status. If not, they receive an invitation email and are marked as INVITED.

    Args:
        email (str): The email address of the person to add to the close group.

    Returns:
        str: Confirmation or an error message.
    """
    logger.info("Executing add_close_group_member", email=email, tool_call_id=tool_call_id)
    with ToolExecution(
        "add_close_group_member",
        tool_call_id,
        config,
        {"email": email},
        f"Adding {email} to your close group",
        ADD_CLOSE_GROUP_MEMBER_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        if not email or not email.strip():
            return "Please provide an email address."

        try:
            result = execution.run(_add_close_group_member_for_user, str(execution.user_id), email)
            if result["status"] == "user_not_found":
                return execution.stop(
                    {"error": "User not found"},
                    "User not found",
                    "I couldn't find your account. Please try again.",
                )

            if result["member_status"] == CloseGroupMember.Status.JOINED:
                outcome = f"**{email}** has been added to your close group."
            else:
                outcome = f"**{email}** has been invited to your close group. They'll be added once they join SamsR."

            return execution.stop({"success": True, "status": result["member_status"]}, "Member added", outcome)

        except ToolTimeoutError:
            logger.warning(
                "Adding close group member timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Adding close group member timed out",
                "I couldn't finish adding that close-group member before the request timed out. Please try again.",
            )

        except ValidationError as e:
            detail = e.detail
            if isinstance(detail, dict):
                msg = " ".join(str(v[0]) if isinstance(v, list) else str(v) for v in detail.values())
            elif isinstance(detail, list):
                msg = str(detail[0])
            else:
                msg = str(detail)

            logger.warning("Validation error in add_close_group_member", user_id=execution.user_id, error=msg)
            return execution.fail(msg, "Failed to add member", f"Could not add member: {msg}")

        except Exception as e:
            logger.exception("Failed to add close group member", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to add member", "An error occurred while adding the member. Please try again."
            )


def _add_close_group_member_for_user(user_id: str, email: str) -> AddCloseGroupMemberResult:
    user = UserMaster.objects.filter(id=user_id).first()
    if not user:
        return {"status": "user_not_found"}

    member = CloseGroupService.add_member(user=user, email=email.strip().lower())
    return {"status": "ok", "member_status": member.status}

"""
Tool to fetch pending family invitations received by the current user.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_pending_invitations

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_PENDING_INVITATIONS_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_pending_invitations(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch all pending family invitations received by the current user that
    they have not yet accepted.

    Use this tool when the user asks about pending invites, family invitations,
    or whether anyone has invited them to join a family.

    Returns:
        str: A formatted list of pending family invitations with family name
             and who sent the invite.
    """
    logger.info("Executing get_pending_invitations", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_pending_invitations",
        tool_call_id,
        config,
        {},
        "Checking pending invitations",
        GET_PENDING_INVITATIONS_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            pending = execution.run(load_pending_invitations, str(execution.user_id))

            if not pending:
                return execution.stop(
                    {"invitations": []},
                    "No pending invitations",
                    "You have no pending family invitations.",
                )

            invite_data = []
            lines = []
            for invitation in pending:
                relation_note = f" as {invitation['relation']}" if invitation["relation"] else ""
                entry = {
                    "family_id": invitation["family_id"],
                    "family_name": invitation["family_name"],
                    "invited_by": invitation["invited_by"],
                    "relation": invitation["relation"],
                }
                invite_data.append(entry)
                lines.append(
                    f"- **{invitation['family_name']}** — invited by {invitation['invited_by']}{relation_note}"
                )

            return execution.stop(
                {"invitations": invite_data},
                f"Found {len(invite_data)} pending invitation(s)",
                f"You have **{len(invite_data)}** pending family invitation(s):\n" + "\n".join(lines),
            )

        except ToolTimeoutError:
            logger.warning(
                "Fetching pending invitations timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching pending invitations timed out",
                "I couldn't fetch your pending invitations before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch pending invitations", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e),
                "Failed to fetch invitations",
                "An error occurred while fetching your invitations. Please try again.",
            )

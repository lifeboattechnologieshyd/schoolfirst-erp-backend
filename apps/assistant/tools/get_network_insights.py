"""
Tool to surface a high-level insights summary of the user's social network health.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_network_insights

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_NETWORK_INSIGHTS_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_network_insights(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Provide a health and status summary of the user's social network on SamsR.

    Covers:
    - Profile completeness
    - Number of families joined and owned
    - Pending family invitations received
    - Pending invites the user has sent (not yet accepted by recipients)
    - Close group member count and any pending close group invites

    Use this when the user asks for an overview or status of their network,
    asks what needs attention, or wants to know if anything is pending.

    Returns:
        str: A structured insights summary in Markdown.
    """
    logger.info("Executing get_network_insights", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_network_insights",
        tool_call_id,
        config,
        {},
        "Analysing your network",
        GET_NETWORK_INSIGHTS_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            result = execution.run(load_network_insights, str(execution.user_id))
            if result["status"] == "user_not_found":
                return execution.stop(
                    {"error": "User not found"},
                    "User not found",
                    "I couldn't find your account. Please try again.",
                )

            result = {
                "profile_complete": result["profile_complete"],
                "families_joined": result["families_joined"],
                "families_owned": result["families_owned"],
                "received_pending_invites": result["received_pending_invites"],
                "sent_pending_invites": result["sent_pending_invites"],
                "close_group_joined": result["close_group_joined"],
                "close_group_pending": result["close_group_pending"],
            }
            lines = ["## Your Network at a Glance\n"]

            # Profile
            profile_status = "✓ Complete" if result["profile_complete"] else "⚠ Not updated yet"
            lines.append(f"**Profile:** {profile_status}")

            # Families
            lines.append(f"**Families joined:** {result['families_joined']} (you own {result['families_owned']})")

            # Invitations
            if result["received_pending_invites"]:
                lines.append(
                    f"**Pending invitations to you:** {result['received_pending_invites']} — consider accepting them"
                )
            else:
                lines.append("**Pending invitations to you:** None")

            if result["sent_pending_invites"]:
                lines.append(f"**Invites you sent (awaiting response):** {result['sent_pending_invites']}")
            else:
                lines.append("**Invites you sent (awaiting response):** None")

            # Close group
            cg_pending_note = (
                f", {result['close_group_pending']} invite(s) pending" if result["close_group_pending"] else ""
            )
            lines.append(f"**Close group:** {result['close_group_joined']} joined member(s){cg_pending_note}")

            return execution.stop(result, "Insights ready", "\n".join(lines))

        except ToolTimeoutError:
            logger.warning(
                "Fetching network insights timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching network insights timed out",
                "I couldn't finish fetching your network insights before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch network insights", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e),
                "Failed to fetch insights",
                "An error occurred while fetching your network insights. Please try again.",
            )

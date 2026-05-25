"""
Tool to fetch the current user's close group members.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_close_group_members

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_CLOSE_GROUP_MEMBERS_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_close_group_members(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch all members in the current user's close group.

    A close group is the user's personal inner circle. Each user has exactly
    one close group. Returns each member's name (or email), and whether they
    have joined or are still invited.

    Use this tool when the user asks about their close group, inner circle,
    or close friends/contacts.

    Returns:
        str: A formatted list of close group members with their join status.
    """
    logger.info("Executing get_close_group_members", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_close_group_members",
        tool_call_id,
        config,
        {},
        "Fetching your close group",
        GET_CLOSE_GROUP_MEMBERS_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            members = execution.run(load_close_group_members, str(execution.user_id))
            if members is None:
                return execution.stop(
                    {"members": []},
                    "No close group yet",
                    "You haven't added anyone to your close group yet.",
                )

            if not members:
                return execution.stop(
                    {"members": []},
                    "Close group is empty",
                    "Your close group is currently empty.",
                )

            lines = []
            for member in members:
                lines.append(f"- **{member['name']}** — {member['status']}")

            return execution.stop(
                {"members": members},
                f"Found {len(members)} member(s)",
                f"Your close group has **{len(members)}** member(s):\n" + "\n".join(lines),
            )

        except ToolTimeoutError:
            logger.warning(
                "Fetching close group members timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching close group members timed out",
                "I couldn't fetch your close group before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch close group members", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e),
                "Failed to fetch close group",
                "An error occurred while fetching your close group. Please try again.",
            )

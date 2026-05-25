"""
Tool to fetch the current user's families.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_family_data

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_MY_FAMILIES_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_my_families(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch all families the current user belongs to or owns.

    Returns each family's name, the user's role (Owner or Member), the number
    of joined members, and the number of pending invites.

    Use this tool when the user asks about their families, family groups,
    or how many families they are part of.

    Returns:
        str: A formatted list of the user's families with key details.
    """
    logger.info("Executing get_my_families", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_my_families",
        tool_call_id,
        config,
        {},
        "Fetching your families",
        GET_MY_FAMILIES_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            family_data = execution.run(load_family_data, str(execution.user_id))

            if not family_data:
                return execution.stop(
                    {"families": []},
                    "No families found",
                    "You are not a member of any families yet. You can create one or ask someone to invite you.",
                )

            lines = []
            for family in family_data:
                pending_note = f", {family['invited_count']} pending invite(s)" if family["invited_count"] else ""
                lines.append(
                    f"- **{family['name']}** — {family['role']}, "
                    f"{family['joined_count']} joined member(s){pending_note} (ID: `{family['id']}`)"
                )

            return execution.stop(
                {
                    "families": [
                        {
                            "id": family["id"],
                            "name": family["name"],
                            "role": family["role"],
                            "joined_members": family["joined_count"],
                            "pending_invites": family["invited_count"],
                        }
                        for family in family_data
                    ]
                },
                f"Found {len(family_data)} family/families",
                f"You are part of **{len(family_data)}** family/families:\n" + "\n".join(lines),
            )

        except ToolTimeoutError:
            logger.warning(
                "Fetching user families timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching user families timed out",
                "I couldn't fetch your families before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch user families", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to fetch families", "An error occurred while fetching your families. Please try again."
            )

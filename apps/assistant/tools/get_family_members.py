"""
Tool to fetch members of a specific family.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_family_members

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_FAMILY_MEMBERS_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_family_members(
    family_id: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch all members of a specific family by its ID.

    Returns each member's name (or email if no name set), relation label,
    role (Owner/Member), and invite status (Joined/Invited).

    The user must be a joined member of the family to view its members.
    Use get_my_families first to obtain the correct family ID.

    Args:
        family_id (str): The UUID of the family to look up.

    Returns:
        str: A formatted list of family members with their details.
    """
    logger.info("Executing get_family_members", family_id=family_id, tool_call_id=tool_call_id)
    with ToolExecution(
        "get_family_members",
        tool_call_id,
        config,
        {"family_id": family_id},
        "Fetching family members",
        GET_FAMILY_MEMBERS_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            result = execution.run(load_family_members, family_id, str(execution.user_id))
            if result["status"] == "family_not_found":
                return execution.stop(
                    {"error": "Family not found"},
                    "Family not found",
                    f"No family found with ID `{family_id}`. Use get_my_families to see your families.",
                )

            if result["status"] == "access_denied":
                return execution.stop(
                    {"error": "Access denied"},
                    "Access denied",
                    "You are not an active member of this family.",
                )

            lines = []
            for member in result["members"]:
                name = member["name"]
                role_label = member["role"]
                status_label = member["status"]
                relation_note = f" ({member['relation']})" if member["relation"] else ""
                lines.append(f"- **{name}**{relation_note} — {role_label}, {status_label}")

            return execution.stop(
                {"family": result["family_name"], "members": result["members"]},
                f"Found {len(result['members'])} member(s)",
                f"**{result['family_name']}** has {len(result['members'])} member(s):\n" + "\n".join(lines),
            )

        except ToolTimeoutError:
            logger.warning(
                "Fetching family members timed out",
                family_id=family_id,
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching family members timed out",
                "I couldn't fetch the family members before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch family members", family_id=family_id, error=str(e))
            return execution.fail(
                str(e), "Failed to fetch members", "An error occurred while fetching family members. Please try again."
            )

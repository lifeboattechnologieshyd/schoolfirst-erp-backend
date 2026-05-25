"""
Tool to search for family members by name or relation across all of the user's families.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import find_family_member_matches

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

FIND_FAMILY_MEMBER_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def find_family_member(
    query: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Search for a family member by name or relation label across all of the
    user's joined families.

    Useful when the user refers to a relative by name or role such as
    "my sister", "John", "Father", or "Sarah".

    Args:
        query (str): The name or relation to search for. Accepts natural language
                     (e.g. "sister", "John") or enum values (e.g. "sister").

    Returns:
        str: A list of matching members showing their name, relation, family name,
             and join status.
    """
    logger.info("Executing find_family_member", query=query, tool_call_id=tool_call_id)
    with ToolExecution(
        "find_family_member",
        tool_call_id,
        config,
        {"query": query},
        f"Searching family members for '{query}'",
        FIND_FAMILY_MEMBER_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        if not query or not query.strip():
            return "Please provide a name or relation to search for."

        try:
            result = execution.run(find_family_member_matches, str(execution.user_id), query.strip())
            joined_family_ids = result["joined_family_ids"]
            if not joined_family_ids:
                return execution.stop({"matches": []}, "Not in any families", "You are not a member of any families.")

            matches = result["matches"]

            if not matches:
                return execution.stop(
                    {"matches": matches},
                    "Found 0 match(es)",
                    f"No family members found matching '{query}'.",
                )

            lines = [f"Found **{len(matches)}** match(es) for '{query}':\n"]
            for m in matches:
                relation_note = f" ({m['relation']})" if m["relation"] else ""
                lines.append(f"- **{m['name']}**{relation_note} — {m['family']}, {m['status']}")
            return execution.stop({"matches": matches}, f"Found {len(matches)} match(es)", "\n".join(lines))

        except ToolTimeoutError:
            logger.warning(
                "Finding family member timed out",
                user_id=execution.user_id,
                query=query,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Finding family member timed out",
                "I couldn't finish that family-member search before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to search family members", user_id=execution.user_id, query=query, error=str(e))
            return execution.fail(
                str(e), "Search failed", "An error occurred while searching family members. Please try again."
            )

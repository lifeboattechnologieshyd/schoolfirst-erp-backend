"""
Tool to fetch a compact network summary for AI context enrichment.
Combines profile + families + close group in a single efficient call.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import build_network_summary_data

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_MY_NETWORK_SUMMARY_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_my_network_summary(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch a combined summary of the user's profile, all families, and close group
    in a single call.

    Use this tool when the user wants a broad overview of all their connections,
    or when you need to understand the full context of a user's social network
    before answering a more specific question about it.

    Returns:
        str: A structured Markdown summary covering profile, families, and close group.
    """
    logger.info("Executing get_my_network_summary", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_my_network_summary",
        tool_call_id,
        config,
        {},
        "Compiling your network summary",
        GET_MY_NETWORK_SUMMARY_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            summary = execution.run(build_network_summary_data, str(execution.user_id))
            if summary["status"] == "user_not_found":
                return execution.stop({"error": "User not found"}, "User not found", "I couldn't find your account.")

            result = {
                "profile": {
                    "name": summary["full_name"],
                    "dob": summary["dob"],
                    "complete": summary["profile_complete"],
                },
                "families": [{"name": family["name"]} for family in summary["families"]],
                "close_group_member_count": len(summary["close_group_names"]),
            }
            sections = [
                "## Your Network Summary",
                "",
                "### Profile",
                f"- **Name:** {summary['full_name']}",
                f"- **Date of Birth:** {summary['dob']}",
                f"- **Profile complete:** {'Yes' if summary['profile_complete'] else 'No'}",
                "",
                f"### Families ({len(summary['families'])} total)",
            ]
            sections += [f"  - **{family['name']}** ({family['role']})" for family in summary["families"]] or [
                "  - None yet"
            ]
            sections += [
                "",
                f"### Close Group ({len(summary['close_group_names'])} joined member(s))",
            ]
            if summary["close_group_names"]:
                sections += [f"  - {name}" for name in summary["close_group_names"]]
            else:
                sections.append("  - No joined members yet")

            return execution.stop(result, "Summary compiled", "\n".join(sections))

        except ToolTimeoutError:
            logger.warning(
                "Compiling network summary timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Compiling network summary timed out",
                "I couldn't finish compiling your network summary before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to compile network summary", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e),
                "Failed to compile summary",
                "An error occurred while compiling your network summary. Please try again.",
            )

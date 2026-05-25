"""
Tool to surface upcoming birthdays from joined family and close group members.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_upcoming_birthdays

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

_DAYS_AHEAD = 30  # Look 30 days forward by default
GET_BIRTHDAY_REMINDERS_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_birthday_reminders(  # noqa: PLR0912, PLR0915
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Find upcoming birthdays within the next 30 days for joined members of the
    user's families and close group.

    Only includes members who have a SamsR account with a date of birth set.

    Use this tool when the user asks about upcoming birthdays, birthday reminders,
    or whether any family member has a birthday soon.

    Returns:
        str: A list of upcoming birthdays sorted by date, showing name and date.
    """
    logger.info("Executing get_birthday_reminders", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_birthday_reminders",
        tool_call_id,
        config,
        {},
        "Checking upcoming birthdays",
        GET_BIRTHDAY_REMINDERS_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            result = execution.run(load_upcoming_birthdays, str(execution.user_id), _DAYS_AHEAD)
            if not result["connected_users"]:
                return execution.stop(
                    {"birthdays": []},
                    "No connected users with birthdays",
                    "None of your family or close group members have shared their birthday on SamsR yet.",
                )

            if not result["birthdays"]:
                return execution.stop(
                    {"birthdays": []},
                    "Found 0 upcoming birthday(s)",
                    f"No birthdays from your family or close group in the next {_DAYS_AHEAD} days.",
                )

            lines = [f"**Upcoming birthdays in the next {_DAYS_AHEAD} days:**\n"]
            for birthday in result["birthdays"]:
                if birthday["delta"] == 0:
                    when = "Today! 🎂"
                elif birthday["delta"] == 1:
                    when = "Tomorrow"
                else:
                    when = f"In {birthday['delta']} days ({birthday['display_date']})"
                lines.append(f"- **{birthday['name']}** — {when}")

            return execution.stop(
                {"birthdays": [{"name": item["name"], "date": item["date"]} for item in result["birthdays"]]},
                f"Found {len(result['birthdays'])} upcoming birthday(s)",
                "\n".join(lines),
            )

        except ToolTimeoutError:
            logger.warning(
                "Fetching birthday reminders timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching birthday reminders timed out",
                "I couldn't finish checking upcoming birthdays before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch birthday reminders", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to check birthdays", "An error occurred while checking birthdays. Please try again."
            )

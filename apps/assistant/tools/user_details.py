"""
Tool to fetch user details while protecting PII.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_user_public_details

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

FETCH_USER_DETAILS_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def fetch_user_details(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch basic details about the current user, such as their name.

    This tool provides the user's first and last name if available.
    It explicitly excludes sensitive PII like email, mobile number,
    address, and date of birth for privacy and security.

    Returns:
        str: A string containing the user's name or a message if not found.
    """
    logger.info("Executing fetch_user_details", tool_call_id=tool_call_id)
    with ToolExecution(
        "fetch_user_details",
        tool_call_id,
        config,
        {},
        "Fetching your details",
        FETCH_USER_DETAILS_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            user = execution.run(load_user_public_details, str(execution.user_id))
            if not user:
                logger.warning("User not found", user_id=execution.user_id, tool_call_id=tool_call_id)
                return execution.stop(
                    {"error": "User not found"},
                    "User not found",
                    "I couldn't find any information about you in the system.",
                )

            logger.info("User details fetched", user_id=execution.user_id, tool_call_id=tool_call_id)
            full_name = user["full_name"]

            return execution.stop(
                {"first_name": user["first_name"], "last_name": user["last_name"]},
                "Fetched your details",
                f"Your name is {full_name}. "
                "(Note: For your privacy, I do not have access to your email, phone number, "
                "address, or date of birth.)",
            )

        except ToolTimeoutError:
            logger.warning(
                "Fetching user details timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching user details timed out",
                "I couldn't retrieve your details before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception(
                "Failed to fetch user details",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                error=str(e),
            )
            return execution.fail(
                "Database error", "Error fetching details", "I'm sorry, I couldn't retrieve your details right now."
            )

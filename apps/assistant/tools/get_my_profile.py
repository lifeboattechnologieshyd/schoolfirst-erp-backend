"""
Tool to fetch the current user's full profile details.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_user_profile

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

GET_MY_PROFILE_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=5, max_timeout_seconds=30)


@tool
def get_my_profile(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Fetch the current user's full profile information including name, date of birth,
    gender, and profile completion status.

    Use this tool when the user asks about their profile, personal details,
    or whether their profile is complete.

    Returns:
        str: A formatted string with the user's profile details.
    """
    logger.info("Executing get_my_profile", tool_call_id=tool_call_id)
    with ToolExecution(
        "get_my_profile",
        tool_call_id,
        config,
        {},
        "Fetching your profile",
        GET_MY_PROFILE_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            profile = execution.run(load_user_profile, str(execution.user_id))
            if not profile:
                return execution.stop(
                    {"error": "User not found"},
                    "User not found",
                    "I couldn't find your profile. Please try again.",
                )

            result = {
                "full_name": profile["full_name"],
                "dob": profile["dob"],
                "gender": profile["gender"],
                "is_profile_complete": profile["is_profile_complete"],
            }
            lines = [
                f"**Name:** {profile['full_name']}",
                f"**Date of Birth:** {profile['dob']}",
                f"**Gender:** {profile['gender']}",
                "**Profile Complete:** "
                f"{'Yes' if profile['is_profile_complete'] else 'No — profile has not been updated yet'}",
            ]
            return execution.stop(result, "Profile fetched", "\n".join(lines))

        except ToolTimeoutError:
            logger.warning(
                "Fetching user profile timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Fetching user profile timed out",
                "I couldn't fetch your profile before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to fetch user profile", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to fetch profile", "An error occurred while fetching your profile. Please try again."
            )

"""
Tool to update the current user's profile fields via conversation.
"""

from datetime import date
from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.core.models.user import UserMaster

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

UPDATE_MY_PROFILE_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=8, max_timeout_seconds=30)


@tool
def update_my_profile(
    first_name: str,
    last_name: str,
    gender: str,
    date_of_birth: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Update the current user's profile fields.

    Only pass fields the user explicitly asked to change. Pass an empty string
    for fields that should remain unchanged.

    Args:
        first_name (str): New first name, or empty string to leave unchanged.
        last_name (str): New last name, or empty string to leave unchanged.
        gender (str): New gender value, or empty string to leave unchanged.
        date_of_birth (str): New date of birth in YYYY-MM-DD format,
                             or empty string to leave unchanged.

    Returns:
        str: Confirmation of the changes applied, or an error message.
    """
    updates_raw = {
        "first_name": first_name.strip() if first_name else "",
        "last_name": last_name.strip() if last_name else "",
        "gender": gender.strip() if gender else "",
        "date_of_birth": date_of_birth.strip() if date_of_birth else "",
    }
    # Only apply non-empty values
    updates = {k: v for k, v in updates_raw.items() if v}

    logger.info("Executing update_my_profile", updates=updates, tool_call_id=tool_call_id)
    with ToolExecution(
        "update_my_profile",
        tool_call_id,
        config,
        updates_raw,
        "Updating your profile",
        UPDATE_MY_PROFILE_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        if not updates:
            return (
                "No fields to update. Please specify at least one field "
                "(first name, last name, gender, or date of birth)."
            )

        try:
            result = execution.run(_apply_profile_updates, str(execution.user_id), updates)
            if result["status"] == "user_not_found":
                return execution.stop(
                    {"error": "User not found"},
                    "User not found",
                    "I couldn't find your profile. Please try again.",
                )

            if result["status"] == "invalid_date":
                return execution.fail(
                    "Invalid date format",
                    "Failed — invalid date",
                    f"The date '{result['invalid_date']}' is not valid. "
                    "Please use YYYY-MM-DD format (e.g. 1990-03-15).",
                )

            changes = "\n".join(f"- {change}" for change in result["applied"])
            return execution.stop(
                {"updated_fields": result["save_fields"]},
                "Profile updated",
                f"Your profile has been updated:\n{changes}",
            )

        except ToolTimeoutError:
            logger.warning(
                "Updating user profile timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Updating user profile timed out",
                "I couldn't finish updating your profile before the request timed out. Please try again.",
            )

        except Exception as e:
            logger.exception("Failed to update user profile", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to update profile", "An error occurred while updating your profile. Please try again."
            )


def _apply_profile_updates(user_id: str, updates: dict[str, str]) -> dict:
    user = UserMaster.objects.filter(id=user_id).first()
    if not user:
        return {"status": "user_not_found"}

    save_fields = []
    applied = []

    if "first_name" in updates:
        user.first_name = updates["first_name"]
        save_fields.append("first_name")
        applied.append(f"First name → {updates['first_name']}")

    if "last_name" in updates:
        user.last_name = updates["last_name"]
        save_fields.append("last_name")
        applied.append(f"Last name → {updates['last_name']}")

    if "gender" in updates:
        user.gender = updates["gender"]
        save_fields.append("gender")
        applied.append(f"Gender → {updates['gender']}")

    if "date_of_birth" in updates:
        try:
            dob = date.fromisoformat(updates["date_of_birth"])
        except ValueError:
            return {"status": "invalid_date", "invalid_date": updates["date_of_birth"]}

        user.date_of_birth = dob
        save_fields.append("date_of_birth")
        applied.append(f"Date of birth → {dob.strftime('%B %d, %Y')}")

    if not user.is_profile_updated:
        user.is_profile_updated = True
        save_fields.append("is_profile_updated")

    user.save(update_fields=save_fields)
    return {"status": "ok", "save_fields": save_fields, "applied": applied}

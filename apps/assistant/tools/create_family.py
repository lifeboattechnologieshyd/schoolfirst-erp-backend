"""
Tool to create a new family for the current user.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from rest_framework.exceptions import ValidationError

from apps.core.models.family import Family
from apps.core.models.user import UserMaster
from apps.core.services.family_service import FamilyService

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

CREATE_FAMILY_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=8, max_timeout_seconds=30)


@tool
def create_family(
    name: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Create a new family group for the current user.

    The user becomes the owner of the family automatically.
    A user can only own one family — this will fail if they already own one.

    Args:
        name (str): The name for the new family (e.g. "Smith Family").

    Returns:
        str: Confirmation of the created family or an error message.
    """
    logger.info("Executing create_family", name=name, tool_call_id=tool_call_id)
    with ToolExecution(
        "create_family",
        tool_call_id,
        config,
        {"name": name},
        f"Creating family '{name}'",
        CREATE_FAMILY_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        if not name or not name.strip():
            return "Please provide a name for the family."

        try:
            family = execution.run(_create_family_for_user, str(execution.user_id), name.strip())
            if family is None:
                return execution.stop(
                    {"error": "User not found"},
                    "User not found",
                    "I couldn't find your account. Please try again.",
                )

            return execution.stop(
                {"family_id": str(family.id), "family_name": family.name},
                "Family created",
                f"Your family **{family.name}** has been created successfully. You can now invite members to join.",
            )

        except ToolTimeoutError:
            logger.warning(
                "Creating family timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Creating family timed out",
                "I couldn't finish creating the family before the request timed out. Please try again.",
            )

        except ValidationError as e:
            detail = e.detail
            if isinstance(detail, dict):
                msg = " ".join(str(v[0]) if isinstance(v, list) else str(v) for v in detail.values())
            elif isinstance(detail, list):
                msg = str(detail[0])
            else:
                msg = str(detail)

            logger.warning("Validation error in create_family", user_id=execution.user_id, error=msg)
            return execution.fail(msg, "Failed to create family", f"Could not create the family: {msg}")

        except Exception as e:
            logger.exception("Failed to create family", user_id=execution.user_id, error=str(e))
            return execution.fail(
                str(e), "Failed to create family", "An error occurred while creating the family. Please try again."
            )


def _create_family_for_user(user_id: str, name: str) -> Family | None:
    user = UserMaster.objects.filter(id=user_id).first()
    if not user:
        return None

    return FamilyService.create_family(user=user, name=name)

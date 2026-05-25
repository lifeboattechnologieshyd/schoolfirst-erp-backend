"""Tool to search across Docusafe files the current user can access."""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import load_accessible_docusafe_file_ids

from .docusafe_search_helpers import format_docusafe_search_results, search_docusafe_files
from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

SEARCH_ACCESSIBLE_DOCUSAFE_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=10, max_timeout_seconds=30)


@tool
def search_accessible_docusafe(
    query: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Search across the Docusafe files the current user owns or can access.

    Use this tool when the user wants to find a document they have not attached
    to the current Assistant Thread, for example "find my driver's license" or
    "search the files I can access for passport renewal".
    """
    logger.info("Executing search_accessible_docusafe", tool_call_id=tool_call_id)
    with ToolExecution(
        "search_accessible_docusafe",
        tool_call_id,
        config,
        {"query": query},
        "Searching your accessible Docusafe files",
        SEARCH_ACCESSIBLE_DOCUSAFE_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id:
            return execution.no_user()

        try:
            file_ids = execution.run(load_accessible_docusafe_file_ids, str(execution.user_id))
            if not file_ids:
                return execution.stop(
                    {"results": []},
                    "No accessible Docusafe files available",
                    "No Docusafe files are currently available for you to search. "
                    "The user may need to upload documents or gain access to shared ones first.",
                )

            results = execution.run(search_docusafe_files, str(execution.user_id), query, file_ids)
            if not results:
                return execution.stop(
                    {"results": []},
                    "No relevant matches found",
                    "No relevant information was found in the Docusafe files you can access for this query.",
                )

            response_text, unique_files = format_docusafe_search_results(results)
            return execution.stop(
                {"data": unique_files},
                f"Found relevant matches in {len(unique_files)} accessible file(s)",
                response_text,
            )

        except ToolTimeoutError:
            logger.warning(
                "Searching accessible Docusafe files timed out",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Docusafe search timed out",
                "Searching accessible Docusafe files timed out. Please try a narrower document search.",
            )

        except Exception as error:
            logger.exception(
                "Failed to search accessible Docusafe files",
                user_id=execution.user_id,
                tool_call_id=tool_call_id,
                error=str(error),
            )
            return execution.fail(
                "Search failed",
                "Error searching Docusafe files",
                "I encountered an error while searching the Docusafe files you can access.",
            )

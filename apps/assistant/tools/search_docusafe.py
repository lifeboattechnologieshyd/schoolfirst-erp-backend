"""
Tool to search a user's Docusafe documents based on embeddings.
"""

from typing import Annotated

import structlog
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool

from apps.assistant.query_adapters import (
    load_accessible_docusafe_file_ids,
    load_attached_docusafe_file_ids,
    load_thread,
)

from .docusafe_search_helpers import format_docusafe_search_results, search_docusafe_files
from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

SEARCH_DOCUSAFE_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=10, max_timeout_seconds=30)


@tool
def search_docusafe(
    query: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Search across the documents the user has explicitly attached to this chat.
    Use this tool to find information from the user's provided document context.

    Args:
        query: The search query to look for in the documents.
    """
    logger.info("Executing search_docusafe", tool_call_id=tool_call_id)
    with ToolExecution(
        "search_docusafe",
        tool_call_id,
        config,
        {"query": query},
        "Searching your documents",
        SEARCH_DOCUSAFE_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        if not execution.user_id or not execution.thread_id:
            logger.warning(
                "Missing context",
                user_id=execution.user_id,
                thread_id=execution.thread_id,
                tool_call_id=tool_call_id,
            )
            return execution.fail(
                "Context missing",
                "Failed to search documents",
                "System Error: Missing user or thread context to perform document search.",
            )

        try:
            thread = execution.run(load_thread, str(execution.thread_id))
            if not thread:
                return "System Error: Chat thread could not be found."

            file_ids = load_attached_docusafe_file_ids(thread)

            if not file_ids:
                return execution.stop(
                    {"error": "No files attached"},
                    "No files attached",
                    "SYSTEM INTERNAL ERROR: The user has not attached any documents to this thread. "
                    "You MUST inform the user that this chat is specifically for Docusafe "
                    "and they need to attach files to continue chatting.",
                )

            accessible_file_ids = execution.run(load_accessible_docusafe_file_ids, str(execution.user_id), file_ids)
            if not accessible_file_ids:
                return execution.stop(
                    {"error": "No accessible attached files"},
                    "No accessible attached files",
                    "SYSTEM INTERNAL ERROR: The documents attached to this thread are not currently accessible to "
                    "the user. You MUST explain that the attached Docusafe files are unavailable and ask the user "
                    "to attach accessible documents or search across their available files instead.",
                )

            results = execution.run(search_docusafe_files, str(execution.user_id), query, accessible_file_ids)

            if not results:
                return execution.stop(
                    {"results": []},
                    "No relevant matches found",
                    "No relevant information was found in the attached documents for this query.",
                )

            final_response_text, unique_files = format_docusafe_search_results(results)

            return execution.stop(
                {"data": unique_files},
                f"Found relevant matches in {len(unique_files)} file(s)",
                final_response_text,
            )

        except ToolTimeoutError:
            logger.warning(
                "Searching attached Docusafe files timed out",
                user_id=execution.user_id,
                thread_id=execution.thread_id,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Docusafe search timed out",
                "Searching the attached Docusafe files timed out. Please try a narrower question.",
            )

        except Exception as e:
            logger.exception(
                "Failed to search docusafe",
                user_id=execution.user_id,
                thread_id=execution.thread_id,
                error=str(e),
            )
            return execution.fail(
                "Search failed",
                "Error searching documents",
                "I encountered an error while safely searching your documents.",
            )

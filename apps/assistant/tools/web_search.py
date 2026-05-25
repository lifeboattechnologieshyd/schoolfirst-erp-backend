"""
Assistant tool for web search.
"""

import time
from typing import Annotated

import structlog
from django.conf import settings
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from tavily import TavilyClient

from .execution import ToolExecution
from .runtime import ToolTimeoutError, ToolTimeoutPolicy

logger = structlog.get_logger("default")

WEB_SEARCH_TIMEOUT_POLICY = ToolTimeoutPolicy(default_timeout_seconds=12, max_timeout_seconds=30)

# Module-level client cache: a new TavilyClient is only created when the API
# key changes (or on first use).  TavilyClient is stateless/thread-safe so
# sharing a single instance across worker threads is safe.
_tavily_client: TavilyClient | None = None
_tavily_api_key: str = ""


def _get_tavily_client() -> TavilyClient | None:
    """Return a cached TavilyClient, or None when the key is not configured."""
    global _tavily_client, _tavily_api_key  # noqa: PLW0603

    api_key = getattr(settings, "TAVILY_API_KEY", "") or ""
    if not api_key:
        return None

    if _tavily_client is None or api_key != _tavily_api_key:
        _tavily_client = TavilyClient(api_key=api_key)
        _tavily_api_key = api_key

    return _tavily_client


@tool
def web_search(
    query: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    timeout: int | None = None,
) -> str:
    """
    Search the web for information using Tavily.

    This tool provides a simple interface to perform web searches and is useful for
    retrieving up-to-date information, news, or any facts that require an internet
    search. The results will include the title and URL of the top search results.

    Args:
        query (str): The search query string to look up on the web.

    Returns:
        str: A numbered list containing the title and URL of the top search results,
        or an error message if the search fails.
    """
    logger.info("Executing web search", query=query, tool_call_id=tool_call_id)
    with ToolExecution(
        "web_search",
        tool_call_id,
        config,
        {"query": query},
        "Searching the Web",
        WEB_SEARCH_TIMEOUT_POLICY,
        timeout,
    ) as execution:
        client = _get_tavily_client()
        if client is None:
            logger.error("TAVILY_API_KEY is not configured", tool_call_id=tool_call_id)
            return execution.fail(
                "Web search is unavailable", "Search unavailable", "Web search is currently unavailable."
            )

        try:
            response, response_time = execution.run(_perform_web_search, client, query)

            results = response.get("results", [])

            return execution.stop(
                {"query": query, "response_time": response_time, "data": results},
                "Searched the Web",
                "\n\n".join(
                    (
                        f"[{i + 1}] {r['title']}\n"
                        f"URL: {r['url']}\n"
                        f"Favicon: {r.get('favicon', '')}\n"
                        f"{r.get('content', '')}"
                    )
                    for i, r in enumerate(results)
                ),
            )

        except ToolTimeoutError:
            logger.warning(
                "Web search timed out",
                query=query,
                tool_call_id=tool_call_id,
                timeout_seconds=execution.timeout_seconds,
            )
            return execution.timeout(
                "Web search timed out",
                "Web search timed out before a result was available. Please try a narrower query.",
            )

        except Exception as e:
            logger.exception("Web search failed", query=query, tool_call_id=tool_call_id, error=str(e))
            return execution.fail("Web search failed", "Search failed", "Web search is temporarily unavailable.")


def _perform_web_search(client: TavilyClient, query: str) -> tuple[dict, float]:
    start_time = time.monotonic()
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.search(query=query, max_results=5, include_favicon=True)
            break
        except Exception as error:
            if attempt < max_retries:
                logger.warning("Web search attempt failed, retrying", attempt=attempt + 1, error=str(error))
                continue
            raise

    response_time = round(time.monotonic() - start_time, 3)
    return response, response_time

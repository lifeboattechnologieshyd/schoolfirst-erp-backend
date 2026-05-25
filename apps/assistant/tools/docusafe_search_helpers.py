"""Shared helpers for assistant-side Docusafe search tools."""

from apps.docusafe.services.vector_search_service import DocusafeSearchService


def search_docusafe_files(user_id: str, query: str, file_ids: list[str], limit: int = 10) -> list[dict]:
    search_service = DocusafeSearchService()
    return search_service.hybrid_search(
        user_id=user_id,
        query=query,
        file_ids=file_ids,
        accessible_file_ids=file_ids,
        limit=limit,
        deduplicate_by_file=False,
    )


def format_docusafe_search_results(results: list[dict]) -> tuple[str, list[dict]]:
    formatted_chunks = []
    unique_files = {}

    for result in results:
        file_name = result.get("file_name", "Unknown File")
        snippet = result.get("snippet", "").strip()
        if snippet:
            formatted_chunks.append(f"--- From Document: {file_name} ---\n{snippet}")

        file_id = result.get("file_id")
        if file_id and file_id not in unique_files:
            unique_files[file_id] = {
                "file_id": file_id,
                "file_name": file_name,
                "folder_id": result.get("folder_id", ""),
            }

    if not formatted_chunks:
        formatted_chunks = [f"Found relevant matches in **{file['file_name']}**." for file in unique_files.values()]

    return "\n\n".join(formatted_chunks), list(unique_files.values())

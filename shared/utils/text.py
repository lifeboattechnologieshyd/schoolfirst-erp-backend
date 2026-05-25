import re

# Regex to strip <thinking>...</thinking> blocks that some models (e.g. Nova Pro)
# may emit before the actual response text.
_THINKING_BLOCK_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE)


def strip_thinking_blocks(text: str) -> str:
    """Remove <thinking>...</thinking> blocks from a response string."""
    if not text:
        return ""
    return _THINKING_BLOCK_RE.sub("", text).strip()


def chunk_text(text: str, target_chunk_size: int = 48) -> list[str]:
    """Split text into word-boundary chunks for incremental SSE delivery."""
    if not text:
        return []
    if len(text) <= target_chunk_size:
        return [text]

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= target_chunk_size:
            parts.append(remaining)
            break
        split_at = remaining.rfind(" ", 0, target_chunk_size + 1)
        if split_at <= 0:
            split_at = target_chunk_size
        parts.append(remaining[:split_at])
        remaining = remaining[split_at:]

    return [part for part in parts if part]

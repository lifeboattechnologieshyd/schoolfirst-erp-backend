"""
Plain-text file parser.

Handles: .txt, .csv, .md
Reads the file directly from S3 and produces DocumentBlocks.
"""

from __future__ import annotations

import csv
import io
import re

import structlog

from apps.docusafe.services.file_storage_service import DocusafeFileStorageService
from apps.docusafe.services.parsers.document_block import DocumentBlock

logger = structlog.getLogger("default")


def parse_plain_text(file_path: str, file_extension: str) -> list[DocumentBlock]:
    """
    Parse a plain-text file into DocumentBlocks.

    - .txt  → single raw_text block
    - .csv  → one sheet_row block per non-empty row
    - .md   → section-aware heading + paragraph blocks
    """
    content = DocusafeFileStorageService.read_file_text(file_path)
    if not content or not content.strip():
        return []

    ext = file_extension.lower()

    if ext == ".md":
        return _parse_markdown(content)
    if ext == ".csv":
        return _parse_csv(content)

    # Default: .txt and anything else — single raw block
    return [
        DocumentBlock(
            text=content.strip(),
            block_type="raw_text",
            page_index=0,
            section=None,
        )
    ]


def _parse_markdown(content: str) -> list[DocumentBlock]:
    """
    Parse Markdown into section-aware blocks.

    Lines starting with `#` are treated as headings; consecutive
    non-heading lines are grouped into paragraph blocks.
    """
    blocks: list[DocumentBlock] = []
    current_section: str | None = None
    paragraph_lines: list[str] = []

    def _flush_paragraph():
        text = "\n".join(paragraph_lines).strip()
        if text:
            blocks.append(
                DocumentBlock(
                    text=text,
                    block_type="paragraph",
                    page_index=0,
                    section=current_section,
                )
            )
        paragraph_lines.clear()

    for line in content.split("\n"):
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            _flush_paragraph()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            current_section = heading_text
            blocks.append(
                DocumentBlock(
                    text=heading_text,
                    block_type="heading",
                    page_index=0,
                    section=current_section,
                    metadata={"heading_level": level},
                )
            )
        else:
            paragraph_lines.append(line)

    _flush_paragraph()
    return blocks


def _parse_csv(content: str) -> list[DocumentBlock]:
    """
    Parse CSV into one DocumentBlock per non-empty row.

    The first non-empty row is treated as a header and stored in metadata.
    """
    # Handle both CRLF and LF newlines correctly via io.StringIO
    f = io.StringIO(content.strip())
    reader = csv.reader(f)

    blocks: list[DocumentBlock] = []
    header: str | None = None

    try:
        first_row = next(reader)
        # Re-join as CSV string to store as text, or just store as stringified list
        header = ", ".join(first_row)
        blocks.append(
            DocumentBlock(
                text=header,
                block_type="sheet_row",
                page_index=0,
                section=None,
                metadata={"row_index": 0, "header": header},
            )
        )
    except StopIteration:
        return []

    for idx, row in enumerate(reader, start=1):
        if not any(row):  # skip completely empty rows
            continue
        row_text = ", ".join(row)
        blocks.append(
            DocumentBlock(
                text=row_text,
                block_type="sheet_row",
                page_index=0,
                section=None,
                metadata={"row_index": idx, "header": header},
            )
        )

    return blocks

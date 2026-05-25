"""
PDF parser.

Handles: .pdf (both digital and scanned)
Uses AWS Textract with LAYOUT feature to extract structured blocks
(headings, paragraphs, tables, lists) with page boundaries preserved.

Textract automatically handles OCR for scanned PDFs.
"""

from __future__ import annotations

import structlog

from apps.docusafe.services.parsers.document_block import DocumentBlock
from apps.docusafe.services.textract_service import (
    extract_structured_blocks,
)

logger = structlog.getLogger("default")

# Mapping of Textract LAYOUT block types to our block_type values
_LAYOUT_TYPE_MAP = {
    "LAYOUT_TITLE": "heading",
    "LAYOUT_SECTION_HEADER": "heading",
    "LAYOUT_HEADER": "heading",
    "LAYOUT_TEXT": "paragraph",
    "LAYOUT_TABLE": "table",
    "LAYOUT_LIST": "list",
    "LAYOUT_FIGURE": "paragraph",
    "LAYOUT_FOOTER": "paragraph",
    "LAYOUT_PAGE_NUMBER": "paragraph",
    "LAYOUT_KEY_VALUE_SET": "paragraph",
}


def parse_pdf(file_path: str, file_size: int) -> list[DocumentBlock]:
    """
    Parse a PDF file into page-aware, structure-aware DocumentBlocks.

    Uses Textract LAYOUT analysis to identify headings, paragraphs,
    tables, and lists.  Page boundaries are preserved via page_index.

    Args:
        file_path: S3 object key.
        file_size: File size in bytes (determines sync vs async Textract).

    Returns:
        List of DocumentBlock objects with page_index and section metadata.
    """
    # PDFs must always use async Textract (sync analyze_document only supports images)
    raw_blocks = extract_structured_blocks(file_path, use_async=True)

    if not raw_blocks:
        logger.warning("No blocks returned from Textract for PDF", file_path=file_path)
        return []

    return _build_document_blocks(raw_blocks)


def _build_document_blocks(raw_blocks: list[dict]) -> list[DocumentBlock]:
    """
    Convert raw Textract blocks into DocumentBlocks.

    Strategy:
    1. First pass: Build a map of block IDs to their page numbers.
    2. Second pass: Process LAYOUT blocks for structured content.
    3. Fallback: If no LAYOUT blocks found, fall back to LINE blocks.
    """
    # Build page map: block ID → page number (0-based)
    page_map: dict[str, int] = {}
    for block in raw_blocks:
        block_id = block.get("Id", "")
        page = block.get("Page", 1)
        page_map[block_id] = page - 1  # Convert to 0-based

    # Build block content map: block ID → text
    block_text_map: dict[str, str] = {}
    for block in raw_blocks:
        if block.get("BlockType") == "LINE":
            block_text_map[block.get("Id", "")] = block.get("Text", "")

    # Attempt LAYOUT-based extraction first
    layout_blocks = [b for b in raw_blocks if b.get("BlockType", "").startswith("LAYOUT_")]

    if layout_blocks:
        return _parse_layout_blocks(layout_blocks, raw_blocks, page_map)

    # Fallback to LINE-based extraction
    return _parse_line_blocks(raw_blocks, page_map)


def _parse_layout_blocks(
    layout_blocks: list[dict],
    all_blocks: list[dict],
    page_map: dict[str, int],
) -> list[DocumentBlock]:
    """Parse Textract LAYOUT blocks into structured DocumentBlocks."""
    # Build child text resolver: layout block → child text
    child_text_map = _build_child_text_map(all_blocks)

    blocks: list[DocumentBlock] = []
    current_section: str | None = None

    for lb in layout_blocks:
        block_type_raw = lb.get("BlockType", "")
        block_type = _LAYOUT_TYPE_MAP.get(block_type_raw, "paragraph")
        block_id = lb.get("Id", "")
        page_index = page_map.get(block_id, lb.get("Page", 1) - 1)

        # Get text: either directly or from child LINE blocks
        text = child_text_map.get(block_id, "").strip()
        if not text:
            text = lb.get("Text", "").strip()
        if not text:
            continue

        # Track section from headings
        if block_type == "heading":
            current_section = text

        confidence = lb.get("Confidence", None)
        metadata = {}
        if confidence is not None:
            metadata["confidence"] = confidence
        if block_type == "heading":
            # Infer heading level from layout type
            if block_type_raw == "LAYOUT_TITLE":
                metadata["heading_level"] = 1
            elif block_type_raw == "LAYOUT_SECTION_HEADER":
                metadata["heading_level"] = 2
            else:
                metadata["heading_level"] = 3

        blocks.append(
            DocumentBlock(
                text=text,
                block_type=block_type,
                page_index=page_index,
                section=current_section,
                metadata=metadata,
            )
        )

    return blocks


def _parse_line_blocks(
    all_blocks: list[dict],
    page_map: dict[str, int],
) -> list[DocumentBlock]:
    """
    Fallback: Parse LINE blocks when LAYOUT blocks are not available.

    Groups consecutive lines on the same page into paragraph blocks.
    """
    blocks: list[DocumentBlock] = []

    for block in all_blocks:
        if block.get("BlockType") != "LINE":
            continue

        text = block.get("Text", "").strip()
        if not text:
            continue

        block_id = block.get("Id", "")
        page_index = page_map.get(block_id, block.get("Page", 1) - 1)

        confidence = block.get("Confidence", None)
        metadata = {}
        if confidence is not None:
            metadata["confidence"] = confidence

        blocks.append(
            DocumentBlock(
                text=text,
                block_type="paragraph",
                page_index=page_index,
                section=None,
                metadata=metadata,
            )
        )

    return blocks


def _build_child_text_map(all_blocks: list[dict]) -> dict[str, str]:
    """
    Build a map: parent block ID → concatenated text of child LINE blocks.

    LAYOUT blocks contain Relationships pointing to child blocks
    (usually LINE blocks) that hold the actual text.
    """
    # First, index all blocks by ID
    block_index: dict[str, dict] = {}
    for block in all_blocks:
        block_index[block.get("Id", "")] = block

    # Build parent → child text map
    result: dict[str, str] = {}
    for block in all_blocks:
        if not block.get("BlockType", "").startswith("LAYOUT_"):
            continue

        relationships = block.get("Relationships", [])
        child_texts: list[str] = []

        for rel in relationships:
            if rel.get("Type") == "CHILD":
                for child_id in rel.get("Ids", []):
                    child = block_index.get(child_id, {})
                    if child.get("BlockType") == "LINE":
                        text = child.get("Text", "").strip()
                        if text:
                            child_texts.append(text)

        result[block.get("Id", "")] = "\n".join(child_texts)

    return result

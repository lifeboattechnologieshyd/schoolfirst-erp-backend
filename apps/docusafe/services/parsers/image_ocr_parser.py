"""
Image OCR parser.

Handles: .jpg, .jpeg, .png, .tiff, .tif, .bmp
Uses AWS Textract analyze_document (sync) to OCR images.
Textract-supported formats only.
"""

from __future__ import annotations

import structlog

from apps.docusafe.services.parsers.document_block import DocumentBlock
from apps.docusafe.services.textract_service import (
    extract_structured_blocks,
)

logger = structlog.getLogger("default")


def parse_image_ocr(file_path: str) -> list[DocumentBlock]:
    """
    Parse an image file via Textract OCR into DocumentBlocks.

    Images are always single-page, so all blocks get page_index=0.
    Uses sync Textract (images are always under the 5 MB sync limit).

    Args:
        file_path: S3 object key.

    Returns:
        List of DocumentBlock objects with OCR-extracted text.
    """
    # Images always use sync Textract (single page, under 5 MB typically)
    raw_blocks = extract_structured_blocks(file_path, use_async=False)

    if not raw_blocks:
        logger.warning("No text extracted from image via OCR", file_path=file_path)
        return []

    blocks: list[DocumentBlock] = []

    # Try LAYOUT blocks first for structure
    layout_blocks = [b for b in raw_blocks if b.get("BlockType", "").startswith("LAYOUT_")]

    if layout_blocks:
        # Build block index once for efficient child text resolution
        block_index = {b.get("Id", ""): b for b in raw_blocks}

        for lb in layout_blocks:
            text = lb.get("Text", "").strip()
            if not text:
                # Try to get text from child relationships
                text = _get_child_text(lb, block_index)
            if not text:
                continue

            confidence = lb.get("Confidence", None)
            metadata = {}
            if confidence is not None:
                metadata["confidence"] = confidence

            blocks.append(
                DocumentBlock(
                    text=text,
                    block_type="paragraph",
                    page_index=0,
                    section=None,
                    metadata=metadata,
                )
            )
    else:
        # Fallback: use LINE blocks
        for block in raw_blocks:
            if block.get("BlockType") != "LINE":
                continue

            text = block.get("Text", "").strip()
            if not text:
                continue

            confidence = block.get("Confidence", None)
            metadata = {}
            if confidence is not None:
                metadata["confidence"] = confidence

            blocks.append(
                DocumentBlock(
                    text=text,
                    block_type="paragraph",
                    page_index=0,
                    section=None,
                    metadata=metadata,
                )
            )

    return blocks


def _get_child_text(layout_block: dict, block_index: dict[str, dict]) -> str:
    """Resolve text from child LINE blocks of a LAYOUT block."""
    texts: list[str] = []

    for rel in layout_block.get("Relationships", []):
        if rel.get("Type") == "CHILD":
            for child_id in rel.get("Ids", []):
                child = block_index.get(child_id, {})
                if child.get("BlockType") == "LINE":
                    text = child.get("Text", "").strip()
                    if text:
                        texts.append(text)

    return "\n".join(texts)

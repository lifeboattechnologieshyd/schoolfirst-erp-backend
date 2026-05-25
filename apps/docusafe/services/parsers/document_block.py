"""
Document block data classes for the DocuSafe parsing pipeline.

These are in-memory transfer objects — NOT Django models.
All format-specific parsers produce list[DocumentBlock].
The semantic chunker consumes DocumentBlocks and produces ChunkedDocuments.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DocumentBlock:
    """
    A single semantic block extracted from a document.

    Every parser normalises its output into a list of these blocks,
    regardless of the source format (PDF, DOCX, XLSX, images, etc.).
    """

    text: str
    block_type: str
    """
    One of:
      - "heading"    — section title / heading
      - "paragraph"  — body text
      - "table"      — tabular data (serialised as markdown pipe-table)
      - "list"       — list items
      - "raw_text"   — unstructured / fallback text
      - "sheet_row"  — single spreadsheet row
      - "slide"      — presentation slide content
    """

    page_index: int | None = None
    """0-based page / slide / sheet index.  None when not applicable."""

    section: str | None = None
    """Current heading / section name (inherited from the most recent heading)."""

    metadata: dict = field(default_factory=dict)
    """
    Extensible metadata bag.  Examples:
      - heading_level: int        (1, 2, 3 for Heading 1/2/3)
      - table_index: int          (sequential table counter)
      - sheet_name: str           (Excel sheet name)
      - slide_number: int         (1-based slide number)
      - confidence: float         (OCR confidence score)
    """


@dataclass
class ChunkedDocument:
    """
    A single chunk produced by the semantic chunker.

    Carries the text plus all provenance metadata needed to build
    enriched Qdrant point payloads.
    """

    text: str
    chunk_index: int
    page_index: int | None = None
    section: str | None = None
    block_types: list[str] = field(default_factory=list)
    """Block types that contributed to this chunk (e.g. ["heading", "paragraph"])."""

    metadata: dict = field(default_factory=dict)

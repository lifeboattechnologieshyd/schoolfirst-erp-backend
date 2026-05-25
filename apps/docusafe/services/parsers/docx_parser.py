"""
DOCX parser.

Handles: .docx
Uses python-docx to iterate the document body in order,
extracting headings, paragraphs, and tables with section tracking.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import docx
import structlog
from django.core.files.storage import default_storage
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from apps.docusafe.services.parsers.document_block import DocumentBlock

logger = structlog.getLogger("default")


def parse_docx(file_path: str) -> list[DocumentBlock]:
    """
    Parse a DOCX file into section-aware DocumentBlocks.

    Iterates the document body in order (paragraphs and tables),
    tracking the current section from heading styles.
    """
    doc = _load_docx_from_s3(file_path)
    blocks: list[DocumentBlock] = []
    current_section: str | None = None
    table_counter = 0

    for element in _iter_block_items(doc):
        if isinstance(element, Paragraph):
            text = element.text.strip()
            if not text:
                continue

            style_name = element.style.name if element.style else ""

            if style_name.startswith("Heading"):
                # Extract heading level from style name (e.g. "Heading 1" → 1)
                level = _extract_heading_level(style_name)
                current_section = text
                blocks.append(
                    DocumentBlock(
                        text=text,
                        block_type="heading",
                        page_index=0,
                        section=current_section,
                        metadata={"heading_level": level},
                    )
                )
            elif style_name.startswith("List"):
                blocks.append(
                    DocumentBlock(
                        text=text,
                        block_type="list",
                        page_index=0,
                        section=current_section,
                    )
                )
            else:
                blocks.append(
                    DocumentBlock(
                        text=text,
                        block_type="paragraph",
                        page_index=0,
                        section=current_section,
                    )
                )

        elif isinstance(element, Table):
            table_text = _table_to_markdown(element)
            if table_text.strip():
                blocks.append(
                    DocumentBlock(
                        text=table_text,
                        block_type="table",
                        page_index=0,
                        section=current_section,
                        metadata={"table_index": table_counter},
                    )
                )
                table_counter += 1

    return blocks


def _iter_block_items(doc: DocxDocument) -> Iterator[Paragraph | Table]:
    """
    Yield each paragraph and table child within the document body
    in document order.
    """
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def _table_to_markdown(table: Table) -> str:
    """
    Convert a docx Table to a pipe-delimited markdown string.

    Example output:
        | Name | Age | City |
        | --- | --- | --- |
        | Alice | 30 | NYC |
    """
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")

    if len(rows) >= 1:
        # Insert separator after header row
        col_count = len(table.rows[0].cells)
        separator = "| " + " | ".join(["---"] * col_count) + " |"
        rows.insert(1, separator)

    return "\n".join(rows)


def _extract_heading_level(style_name: str) -> int:
    """Extract numeric heading level from style name like 'Heading 2'."""
    try:
        return int(style_name.rsplit(maxsplit=1)[-1])
    except ValueError, IndexError:
        return 1


def _load_docx_from_s3(file_path: str) -> DocxDocument:
    """Download a DOCX file from S3 and return a python-docx Document."""
    try:
        with default_storage.open(file_path, "rb") as file_obj:
            content = file_obj.read()
        return docx.Document(io.BytesIO(content))
    except Exception:
        logger.exception("Failed to load DOCX from S3", file_path=file_path)
        raise

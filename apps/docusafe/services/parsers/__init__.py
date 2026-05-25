"""
Docusafe parser router.

Dispatches file parsing to the appropriate format-specific parser
based on file extension.  Every parser returns list[DocumentBlock].
"""

from __future__ import annotations

import structlog

from apps.docusafe.constants import (
    OCR_EXTENSIONS,
    PLAIN_TEXT_EXTENSIONS,
    STRUCTURED_DATA_EXTENSIONS,
    STRUCTURED_EXTENSIONS,
)
from apps.docusafe.services.parsers.document_block import DocumentBlock

logger = structlog.getLogger("default")


def parse_document(  # noqa: PLR0911
    file_path: str,
    file_extension: str,
    file_size: int,
) -> list[DocumentBlock]:
    """
    Route a file to its format-specific parser.

    Args:
        file_path: S3 object key.
        file_extension: Lowercase extension including dot (e.g. ".pdf").
        file_size: File size in bytes.

    Returns:
        List of DocumentBlock objects representing the parsed document.

    Raises:
        ValueError: If the extension has no registered parser.
    """
    ext = file_extension.lower()

    if ext in PLAIN_TEXT_EXTENSIONS:
        from apps.docusafe.services.parsers.plain_text_parser import parse_plain_text  # noqa: PLC0415

        return parse_plain_text(file_path, ext)

    if ext in STRUCTURED_DATA_EXTENSIONS:
        from apps.docusafe.services.parsers.structured_data_parser import parse_structured_data  # noqa: PLC0415

        return parse_structured_data(file_path, ext)

    if ext == ".docx":
        from apps.docusafe.services.parsers.docx_parser import parse_docx  # noqa: PLC0415

        return parse_docx(file_path)

    if ext in {".xlsx", ".xls"}:
        from apps.docusafe.services.parsers.xlsx_parser import parse_xlsx  # noqa: PLC0415

        return parse_xlsx(file_path)

    if ext in {".pptx", ".ppt"}:
        from apps.docusafe.services.parsers.pptx_parser import parse_pptx  # noqa: PLC0415

        return parse_pptx(file_path)

    if ext == ".pdf":
        from apps.docusafe.services.parsers.pdf_parser import parse_pdf  # noqa: PLC0415

        return parse_pdf(file_path, file_size)

    if ext in OCR_EXTENSIONS:
        from apps.docusafe.services.parsers.image_ocr_parser import parse_image_ocr  # noqa: PLC0415

        return parse_image_ocr(file_path)

    # Check against structured extensions that may have specific ext routing above
    if ext in STRUCTURED_EXTENSIONS:
        # Should have been caught above; defensive fallback
        logger.warning("Structured extension fell through router", ext=ext)

    raise ValueError(f"No parser registered for extension: {ext}")

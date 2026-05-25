"""
Structured data parser.

Handles: .json, .xml, .yaml, .yml
Preserves key/value structure by including key paths in block text.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import structlog
import yaml

from apps.docusafe.services.file_storage_service import DocusafeFileStorageService
from apps.docusafe.services.parsers.document_block import DocumentBlock

logger = structlog.getLogger("default")


def parse_structured_data(file_path: str, file_extension: str) -> list[DocumentBlock]:
    """
    Parse a structured data file into DocumentBlocks.

    Walks the data tree and emits one block per top-level key (dict)
    or per item (list), preserving the key path in the text.
    """
    content = DocusafeFileStorageService.read_file_text(file_path)
    if not content or not content.strip():
        return []

    ext = file_extension.lower()

    if ext == ".json":
        return _parse_json(content)
    if ext == ".xml":
        return _parse_xml(content)
    if ext in {".yaml", ".yml"}:
        return _parse_yaml(content)

    return [
        DocumentBlock(
            text=content.strip(),
            block_type="raw_text",
            page_index=0,
        )
    ]


def _parse_json(content: str) -> list[DocumentBlock]:
    """Parse JSON into blocks per top-level key or array item."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON, treating as raw text")
        return [DocumentBlock(text=content.strip(), block_type="raw_text", page_index=0)]

    return _walk_data_tree(data, prefix="")


def _parse_yaml(content: str) -> list[DocumentBlock]:
    """Parse YAML into blocks per top-level key."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        logger.warning("Invalid YAML, treating as raw text")
        return [DocumentBlock(text=content.strip(), block_type="raw_text", page_index=0)]

    if data is None:
        return []

    return _walk_data_tree(data, prefix="")


def _parse_xml(content: str) -> list[DocumentBlock]:
    """Parse XML into blocks per element."""
    try:
        root = ET.fromstring(content)  # noqa: S314
    except ET.ParseError:
        logger.warning("Invalid XML, treating as raw text")
        return [DocumentBlock(text=content.strip(), block_type="raw_text", page_index=0)]

    blocks: list[DocumentBlock] = []
    _walk_xml_element(root, blocks, prefix="")
    return blocks


def _walk_data_tree(data, prefix: str) -> list[DocumentBlock]:
    """
    Recursively walk a dict/list and emit DocumentBlocks.

    For dicts: one block per key with the full key path.
    For lists: one block per item.
    Scalar values at depth > 1 are rolled up into their parent block.
    """
    blocks: list[DocumentBlock] = []

    if isinstance(data, dict):
        for key, value in data.items():
            key_path = f"{prefix}.{key}" if prefix else str(key)

            if isinstance(value, (dict, list)):
                # Recurse into nested structures
                child_blocks = _walk_data_tree(value, prefix=key_path)
                if child_blocks:
                    blocks.extend(child_blocks)
                else:
                    # Empty nested structure
                    blocks.append(
                        DocumentBlock(
                            text=f"{key_path}: (empty)",
                            block_type="raw_text",
                            page_index=0,
                            section=key_path.split(".", maxsplit=1)[0] if "." in key_path else key_path,
                        )
                    )
            else:
                # Scalar value
                blocks.append(
                    DocumentBlock(
                        text=f"{key_path}: {value}",
                        block_type="raw_text",
                        page_index=0,
                        section=prefix.split(".", maxsplit=1)[0] if prefix else str(key),
                    )
                )

    elif isinstance(data, list):
        for idx, item in enumerate(data):
            item_path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"

            if isinstance(item, (dict, list)):
                child_blocks = _walk_data_tree(item, prefix=item_path)
                blocks.extend(child_blocks)
            else:
                blocks.append(
                    DocumentBlock(
                        text=f"{item_path}: {item}",
                        block_type="raw_text",
                        page_index=0,
                        section=prefix.split(".", maxsplit=1)[0] if prefix else None,
                    )
                )
    else:
        # Top-level scalar
        text = f"{prefix}: {data}" if prefix else str(data)
        blocks.append(
            DocumentBlock(
                text=text,
                block_type="raw_text",
                page_index=0,
            )
        )

    return blocks


def _walk_xml_element(element: ET.Element, blocks: list[DocumentBlock], prefix: str):
    """Recursively walk XML elements and emit DocumentBlocks."""
    # Strip namespace from tag for readability
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    path = f"{prefix}.{tag}" if prefix else tag

    # Element has text content directly
    text_content = (element.text or "").strip()
    children = list(element)

    if not children and text_content:
        # Leaf element with text
        blocks.append(
            DocumentBlock(
                text=f"{path}: {text_content}",
                block_type="raw_text",
                page_index=0,
                section=path.split(".", maxsplit=1)[0],
            )
        )
    elif not children and not text_content:
        # Empty leaf — include attributes if any
        if element.attrib:
            attr_text = ", ".join(f"{k}={v}" for k, v in element.attrib.items())
            blocks.append(
                DocumentBlock(
                    text=f"{path}: [{attr_text}]",
                    block_type="raw_text",
                    page_index=0,
                    section=path.split(".", maxsplit=1)[0],
                )
            )
    else:
        # Element with children — recurse
        if text_content:
            blocks.append(
                DocumentBlock(
                    text=f"{path}: {text_content}",
                    block_type="raw_text",
                    page_index=0,
                    section=path.split(".", maxsplit=1)[0],
                )
            )
        for child in children:
            _walk_xml_element(child, blocks, prefix=path)

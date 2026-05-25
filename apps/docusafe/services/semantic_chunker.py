"""
Semantic chunker — section-aware, page-aware, semantic-boundary splitting.

Three-tier strategy:

  Tier 1 — Section-aware grouping:
      Group consecutive blocks sharing the same section.
      A heading block starts a new group.

  Tier 2 — Page-aware splitting:
      Within a section group, never merge blocks from different pages.

  Tier 3 — Semantic splitting:
      If a page+section group exceeds MAX_CHUNK_SIZE:
        - Split at paragraph boundaries first
        - Then at sentence boundaries
        - Last resort: character-level split with overlap
      If a page+section group is under MIN_CHUNK_SIZE:
        - Merge with adjacent same-section, same-page blocks
"""

from __future__ import annotations

import re
from itertools import groupby

from apps.docusafe.constants import (
    SEMANTIC_CHUNK_MAX_SIZE,
    SEMANTIC_CHUNK_MIN_SIZE,
    SEMANTIC_CHUNK_OVERLAP,
)
from apps.docusafe.services.parsers.document_block import ChunkedDocument, DocumentBlock


class SemanticChunker:
    """
    Produces semantically coherent chunks from a list of DocumentBlocks.

    Three-tier strategy: section → page → semantic boundaries.
    """

    @staticmethod
    def chunk_blocks(
        blocks: list[DocumentBlock],
        max_size: int = SEMANTIC_CHUNK_MAX_SIZE,
        min_size: int = SEMANTIC_CHUNK_MIN_SIZE,
        overlap: int = SEMANTIC_CHUNK_OVERLAP,
    ) -> list[ChunkedDocument]:
        """
        Chunk a list of DocumentBlocks into semantically coherent chunks.

        Args:
            blocks: Parsed document blocks from any parser.
            max_size: Maximum characters per chunk.
            min_size: Minimum characters (merge if smaller).
            overlap: Overlap for character-level fallback splits.

        Returns:
            List of ChunkedDocument with enriched metadata.
        """
        if not blocks:
            return []

        # Tier 1: Group by section
        section_groups = SemanticChunker._group_by_section(blocks)

        # Tier 2: Split each section group by page
        page_groups: list[list[DocumentBlock]] = []
        for group in section_groups:
            page_groups.extend(SemanticChunker._split_by_page(group))

        # Tier 3: Semantic splitting within each page+section group
        raw_chunks: list[ChunkedDocument] = []
        for group in page_groups:
            group_chunks = SemanticChunker._chunk_group(group, max_size, overlap)
            raw_chunks.extend(group_chunks)

        # Merge undersized chunks with adjacent same-section, same-page chunks
        merged = SemanticChunker._merge_small_chunks(raw_chunks, min_size)

        # Assign final sequential chunk_index
        for idx, chunk in enumerate(merged):
            chunk.chunk_index = idx

        return merged

    @staticmethod
    def _group_by_section(blocks: list[DocumentBlock]) -> list[list[DocumentBlock]]:
        """
        Group consecutive blocks by section.

        A heading block always starts a new group. Blocks with the same
        section value are kept together until a new heading appears.
        """
        if not blocks:
            return []

        groups: list[list[DocumentBlock]] = []
        current_group: list[DocumentBlock] = []

        for block in blocks:
            # A heading starts a new group
            if block.block_type == "heading" and current_group:
                groups.append(current_group)
                current_group = []
            current_group.append(block)

        if current_group:
            groups.append(current_group)

        return groups

    @staticmethod
    def _split_by_page(blocks: list[DocumentBlock]) -> list[list[DocumentBlock]]:
        """Split a list of blocks into sub-lists by page_index."""
        if not blocks:
            return []

        # Use groupby on page_index — blocks are expected to be in order
        result: list[list[DocumentBlock]] = []
        for _, group in groupby(blocks, key=lambda b: b.page_index):
            result.append(list(group))

        return result

    @staticmethod
    def _chunk_group(
        blocks: list[DocumentBlock],
        max_size: int,
        overlap: int,
    ) -> list[ChunkedDocument]:
        """
        Chunk a group of blocks (same section + same page) into chunks.

        If the group fits within max_size, return as single chunk.
        Otherwise, split at block boundaries first, then sentence boundaries.
        """
        if not blocks:
            return []

        # Calculate total text
        total_text = "\n\n".join(b.text for b in blocks)

        # If whole group fits in one chunk, return it
        if len(total_text) <= max_size:
            return [
                ChunkedDocument(
                    text=total_text,
                    chunk_index=0,  # Will be reassigned later
                    page_index=blocks[0].page_index,
                    section=blocks[0].section,
                    block_types=list({b.block_type for b in blocks}),
                    metadata={},
                )
            ]

        # Try to split at block boundaries first
        chunks = SemanticChunker._split_at_block_boundaries(blocks, max_size)

        # If any chunk still exceeds max_size, split at sentence boundaries
        final_chunks: list[ChunkedDocument] = []
        for chunk in chunks:
            if len(chunk.text) <= max_size:
                final_chunks.append(chunk)
            else:
                # Split this oversized chunk at sentence boundaries
                sub_chunks = SemanticChunker._split_at_sentences(
                    chunk.text,
                    max_size,
                    overlap,
                    page_index=chunk.page_index,
                    section=chunk.section,
                    block_types=chunk.block_types,
                )
                final_chunks.extend(sub_chunks)

        return final_chunks

    @staticmethod
    def _split_at_block_boundaries(
        blocks: list[DocumentBlock],
        max_size: int,
    ) -> list[ChunkedDocument]:
        """
        Split blocks into chunks, keeping each chunk under max_size.

        Each block is kept whole unless it exceeds max_size on its own.
        """
        chunks: list[ChunkedDocument] = []
        current_texts: list[str] = []
        current_types: set[str] = set()
        current_length = 0

        page_index = blocks[0].page_index if blocks else None
        section = blocks[0].section if blocks else None

        for block in blocks:
            block_len = len(block.text) + (2 if current_texts else 0)  # Account for \n\n joiner

            if current_texts and current_length + block_len > max_size:
                # Emit current chunk
                chunks.append(
                    ChunkedDocument(
                        text="\n\n".join(current_texts),
                        chunk_index=0,
                        page_index=page_index,
                        section=section,
                        block_types=list(current_types),
                    )
                )
                current_texts = []
                current_types = set()
                current_length = 0

            current_texts.append(block.text)
            current_types.add(block.block_type)
            current_length += block_len

        # Emit remaining
        if current_texts:
            chunks.append(
                ChunkedDocument(
                    text="\n\n".join(current_texts),
                    chunk_index=0,
                    page_index=page_index,
                    section=section,
                    block_types=list(current_types),
                )
            )

        return chunks

    @staticmethod
    def _split_at_sentences(
        text: str,
        max_size: int,
        overlap: int,
        page_index: int | None,
        section: str | None,
        block_types: list[str],
    ) -> list[ChunkedDocument]:
        """
        Split text at sentence boundaries when block-level splitting
        isn't granular enough.

        Falls back to character-level splitting with overlap as last resort.
        """
        # Split text into sentences
        sentences = SemanticChunker._split_into_sentences(text)

        if not sentences:
            return []

        chunks: list[ChunkedDocument] = []
        current_sentences: list[str] = []
        current_length = 0

        for sentence in sentences:
            sent_len = len(sentence) + (1 if current_sentences else 0)

            if current_sentences and current_length + sent_len > max_size:
                # Emit current chunk
                chunks.append(
                    ChunkedDocument(
                        text=" ".join(current_sentences),
                        chunk_index=0,
                        page_index=page_index,
                        section=section,
                        block_types=block_types,
                    )
                )

                # Keep overlap: take the last few sentences
                overlap_sentences = SemanticChunker._get_overlap_sentences(current_sentences, overlap)
                current_sentences = overlap_sentences
                current_length = sum(len(s) for s in current_sentences)

            current_sentences.append(sentence)
            current_length += sent_len

        # Emit remaining
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            # Don't emit if it's identical to the last chunk (from overlap)
            if not chunks or chunk_text != chunks[-1].text:
                chunks.append(
                    ChunkedDocument(
                        text=chunk_text,
                        chunk_index=0,
                        page_index=page_index,
                        section=section,
                        block_types=block_types,
                    )
                )

        return chunks

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """
        Split text into sentences.

        Uses common sentence-ending patterns: '. ', '? ', '! ', newlines.
        """
        # Split on sentence boundaries while preserving the delimiter
        parts = re.split(r"(?<=[.!?])\s+|\n\n+", text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _get_overlap_sentences(sentences: list[str], target_overlap: int) -> list[str]:
        """Get trailing sentences that fit within the target overlap size."""
        overlap_sentences: list[str] = []
        total = 0

        for s in reversed(sentences):
            if total + len(s) > target_overlap:
                break
            overlap_sentences.insert(0, s)
            total += len(s)

        return overlap_sentences

    @staticmethod
    def _merge_small_chunks(
        chunks: list[ChunkedDocument],
        min_size: int,
    ) -> list[ChunkedDocument]:
        """
        Merge undersized chunks with their neighbors.

        Only merges if both chunks share the same section and page_index.
        """
        if len(chunks) <= 1:
            return chunks

        merged: list[ChunkedDocument] = []

        i = 0
        while i < len(chunks):
            current = chunks[i]

            # Try to merge with next chunk if current is undersized
            if (
                len(current.text) < min_size
                and i + 1 < len(chunks)
                and chunks[i + 1].section == current.section
                and chunks[i + 1].page_index == current.page_index
            ):
                next_chunk = chunks[i + 1]
                merged_chunk = ChunkedDocument(
                    text=current.text + "\n\n" + next_chunk.text,
                    chunk_index=0,
                    page_index=current.page_index,
                    section=current.section,
                    block_types=list(set(current.block_types + next_chunk.block_types)),
                    metadata={},
                )
                merged.append(merged_chunk)
                i += 2  # Skip both chunks
            else:
                merged.append(current)
                i += 1

        return merged

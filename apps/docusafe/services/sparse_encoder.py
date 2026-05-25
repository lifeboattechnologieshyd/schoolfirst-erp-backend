import re
import zlib

from qdrant_client import models


class DocusafeSparseEncoder:
    """
    Encoder for generating BM25-style sparse vectors.
    Uses a stable hash (Adler-32) for deterministic term-to-index mapping.
    """

    @staticmethod
    def encode(text: str) -> models.SparseVector:
        """
        Build a BM25-style sparse vector from text.

        Uses term-frequency tokenization with stable 31-bit hash indices.
        """
        if not text:
            return models.SparseVector(indices=[], values=[])

        # Tokenize: lowercase, alphanumeric words of 2+ chars
        tokens = re.findall(r"[a-zA-Z0-9]{2,}", text.lower())

        if not tokens:
            return models.SparseVector(indices=[], values=[])

        # Count term frequencies
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        # Convert to sparse vector using stable ADR-32 hash indices
        # Handle hash collisions by aggregating values for duplicate indices
        index_value_map: dict[int, float] = {}

        for term, count in tf.items():
            # zlib.adler32 returns a 32-bit unsigned integer
            # We use it directly or mask it to fit within 31-bit (signed positive)
            term_hash = zlib.adler32(term.encode("utf-8")) & 0x7FFFFFFF

            # BM25-style TF scoring: tf / (tf + 1.0)
            # This dampens the impact of very high frequency terms in a single block
            score = float(count / (count + 1.0))

            # Aggregate values for duplicate indices (hash collisions)
            index_value_map[term_hash] = index_value_map.get(term_hash, 0.0) + score

        # Sort by index to ensure deterministic output and meet Qdrant requirements
        sorted_items = sorted(index_value_map.items())
        sorted_indices = [idx for idx, _ in sorted_items]
        sorted_values = [val for _, val in sorted_items]

        return models.SparseVector(indices=sorted_indices, values=sorted_values)

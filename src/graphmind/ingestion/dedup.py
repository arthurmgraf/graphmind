"""Chunk-level near-duplicate detection using MinHash (Jaccard similarity)."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

_NUM_PERM = 128
_SIMILARITY_THRESHOLD = 0.85
_PRIME = (1 << 61) - 1
_MAX_HASH = (1 << 32) - 1


def _ngrams(text: str, n: int = 3) -> set[str]:
    """Extract character n-grams from text."""
    text = text.lower().strip()
    if len(text) < n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _hash_token(token: str) -> int:
    """Hash a token to a 32-bit integer."""
    return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)


class MinHashSignature:
    """MinHash signature for approximate Jaccard similarity."""

    __slots__ = ("_signature",)

    def __init__(self, text: str, num_perm: int = _NUM_PERM) -> None:
        tokens = _ngrams(text)
        self._signature = self._compute(tokens, num_perm)

    @staticmethod
    def _compute(tokens: set[str], num_perm: int) -> tuple[int, ...]:
        hashes = [_hash_token(t) for t in tokens]
        if not hashes:
            return tuple(range(num_perm))

        sig = []
        for i in range(num_perm):
            a = (i * 0x5BD1E995 + 0x1B873593) & _MAX_HASH
            b = (i * 0xCC9E2D51 + 0x1B873593) & _MAX_HASH
            min_val = _MAX_HASH
            for h in hashes:
                val = ((a * h + b) & _MAX_HASH) % _PRIME
                if val < min_val:
                    min_val = val
            sig.append(min_val)
        return tuple(sig)

    def jaccard(self, other: MinHashSignature) -> float:
        """Estimate Jaccard similarity between two signatures."""
        if len(self._signature) != len(other._signature):
            return 0.0
        matches = sum(1 for a, b in zip(self._signature, other._signature) if a == b)
        return matches / len(self._signature)


@dataclass
class DedupResult:
    total_chunks: int = 0
    unique_chunks: int = 0
    duplicate_chunks: int = 0
    duplicate_indices: list[int] | None = None


class ChunkDeduplicator:
    """Detect and remove near-duplicate chunks before embedding."""

    def __init__(
        self,
        similarity_threshold: float = _SIMILARITY_THRESHOLD,
        num_perm: int = _NUM_PERM,
    ) -> None:
        self._threshold = similarity_threshold
        self._num_perm = num_perm
        self._signatures: list[MinHashSignature] = []

    def deduplicate(self, texts: list[str]) -> DedupResult:
        """Remove near-duplicate texts, returning indices of duplicates."""
        duplicate_indices: list[int] = []
        unique_sigs: list[MinHashSignature] = []

        for i, text in enumerate(texts):
            sig = MinHashSignature(text, self._num_perm)
            is_dup = False
            for existing in unique_sigs:
                if sig.jaccard(existing) >= self._threshold:
                    is_dup = True
                    break
            if is_dup:
                duplicate_indices.append(i)
                logger.debug("chunk_duplicate_detected", index=i)
            else:
                unique_sigs.append(sig)

        result = DedupResult(
            total_chunks=len(texts),
            unique_chunks=len(texts) - len(duplicate_indices),
            duplicate_chunks=len(duplicate_indices),
            duplicate_indices=duplicate_indices,
        )

        if duplicate_indices:
            logger.info(
                "chunk_dedup_complete",
                total=result.total_chunks,
                unique=result.unique_chunks,
                duplicates=result.duplicate_chunks,
            )

        return result

    def filter_unique(self, texts: list[str]) -> list[str]:
        """Return only unique texts (removing near-duplicates)."""
        result = self.deduplicate(texts)
        dup_set = set(result.duplicate_indices or [])
        return [t for i, t in enumerate(texts) if i not in dup_set]

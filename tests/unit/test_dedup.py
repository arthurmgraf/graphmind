from __future__ import annotations

from graphmind.ingestion.dedup import (
    ChunkDeduplicator,
    DedupResult,
    MinHashSignature,
    _ngrams,
)


class TestNgrams:
    def test_extracts_trigrams(self):
        result = _ngrams("abcde", n=3)
        assert result == {"abc", "bcd", "cde"}

    def test_short_text_returns_text_itself(self):
        result = _ngrams("ab", n=3)
        assert result == {"ab"}

    def test_lowercases_input(self):
        result = _ngrams("ABC", n=3)
        assert result == {"abc"}


class TestMinHashSignature:
    def test_identical_texts_have_jaccard_one(self):
        sig1 = MinHashSignature("The quick brown fox jumps over the lazy dog")
        sig2 = MinHashSignature("The quick brown fox jumps over the lazy dog")
        assert sig1.jaccard(sig2) == 1.0

    def test_completely_different_texts_have_low_jaccard(self):
        sig1 = MinHashSignature("The quick brown fox jumps over the lazy dog")
        sig2 = MinHashSignature("A completely unrelated sentence with different words here")
        similarity = sig1.jaccard(sig2)
        assert similarity < 0.5

    def test_similar_texts_have_high_jaccard(self):
        sig1 = MinHashSignature("The quick brown fox jumps over the lazy dog")
        sig2 = MinHashSignature("The quick brown fox leaps over the lazy dog")
        similarity = sig1.jaccard(sig2)
        assert similarity > 0.5

    def test_empty_text_does_not_crash(self):
        sig = MinHashSignature("")
        assert sig.jaccard(sig) == 1.0

    def test_different_num_perm_returns_zero_jaccard(self):
        sig1 = MinHashSignature("hello", num_perm=64)
        sig2 = MinHashSignature("hello", num_perm=128)
        # Different signature lengths should return 0.0
        assert sig1.jaccard(sig2) == 0.0


class TestDedupResult:
    def test_default_fields(self):
        result = DedupResult()
        assert result.total_chunks == 0
        assert result.unique_chunks == 0
        assert result.duplicate_chunks == 0
        assert result.duplicate_indices is None

    def test_fields_set_correctly(self):
        result = DedupResult(
            total_chunks=5,
            unique_chunks=3,
            duplicate_chunks=2,
            duplicate_indices=[1, 4],
        )
        assert result.total_chunks == 5
        assert result.duplicate_indices == [1, 4]


class TestChunkDeduplicator:
    def test_identical_texts_detected_as_duplicates(self):
        dedup = ChunkDeduplicator()
        texts = [
            "LangGraph is a powerful framework for building agents",
            "LangGraph is a powerful framework for building agents",
        ]
        result = dedup.deduplicate(texts)
        assert result.total_chunks == 2
        assert result.duplicate_chunks == 1
        assert result.unique_chunks == 1
        assert result.duplicate_indices == [1]

    def test_different_texts_not_duplicates(self):
        dedup = ChunkDeduplicator()
        texts = [
            "LangGraph is a powerful framework for building agents",
            "Neo4j is a native graph database for connected data",
        ]
        result = dedup.deduplicate(texts)
        assert result.total_chunks == 2
        assert result.duplicate_chunks == 0
        assert result.unique_chunks == 2
        assert result.duplicate_indices == []

    def test_filter_unique_removes_duplicates(self):
        dedup = ChunkDeduplicator()
        texts = [
            "LangGraph is a framework for building multi-actor applications",
            "Neo4j stores data as nodes and relationships in a graph",
            "LangGraph is a framework for building multi-actor applications",
        ]
        unique = dedup.filter_unique(texts)
        assert len(unique) == 2
        assert texts[0] in unique
        assert texts[1] in unique

    def test_filter_unique_with_all_unique(self):
        dedup = ChunkDeduplicator()
        texts = [
            "First unique sentence about knowledge graphs",
            "Second unique sentence about vector databases",
            "Third unique sentence about large language models",
        ]
        unique = dedup.filter_unique(texts)
        assert len(unique) == 3

    def test_empty_input_returns_empty(self):
        dedup = ChunkDeduplicator()
        result = dedup.deduplicate([])
        assert result.total_chunks == 0
        assert result.unique_chunks == 0
        assert result.duplicate_chunks == 0
        assert result.duplicate_indices == []

    def test_filter_unique_empty_input(self):
        dedup = ChunkDeduplicator()
        unique = dedup.filter_unique([])
        assert unique == []

    def test_custom_similarity_threshold(self):
        dedup = ChunkDeduplicator(similarity_threshold=0.99)
        # With a very high threshold, nearly-identical texts might pass
        texts = [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox leaps over the lazy dog",
        ]
        result = dedup.deduplicate(texts)
        # These are similar but not identical, so with threshold=0.99 they should be unique
        assert result.unique_chunks == 2

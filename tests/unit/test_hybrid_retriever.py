from __future__ import annotations

from graphmind.retrieval.hybrid_retriever import HybridRetriever
from graphmind.schemas import RetrievalResult


class TestRRFFusion:
    def test_single_list(self):
        results = [
            RetrievalResult(id="a", text="doc a", score=1.0, source="vector"),
            RetrievalResult(id="b", text="doc b", score=0.8, source="vector"),
        ]
        fused = HybridRetriever._rrf_fusion([results], k=60)
        assert len(fused) == 2
        assert fused[0].id == "a"
        assert fused[1].id == "b"
        assert fused[0].score > fused[1].score

    def test_two_lists_with_overlap(self):
        vector = [
            RetrievalResult(id="a", text="doc a", score=1.0, source="vector"),
            RetrievalResult(id="b", text="doc b", score=0.8, source="vector"),
        ]
        graph = [
            RetrievalResult(id="b", text="doc b", score=0.9, source="graph"),
            RetrievalResult(id="c", text="doc c", score=0.7, source="graph"),
        ]
        fused = HybridRetriever._rrf_fusion([vector, graph], k=60)
        assert len(fused) == 3
        scores = {r.id: r.score for r in fused}
        assert scores["b"] > scores["a"]
        assert scores["b"] > scores["c"]

    def test_empty_lists(self):
        fused = HybridRetriever._rrf_fusion([[], []], k=60)
        assert fused == []

    def test_rrf_formula_correctness(self):
        results = [
            RetrievalResult(id="x", text="x", score=1.0, source="vector"),
        ]
        fused = HybridRetriever._rrf_fusion([results], k=60)
        expected_score = 1.0 / (60 + 1)
        assert abs(fused[0].score - expected_score) < 0.0001

    def test_deduplication_preserves_first(self):
        list1 = [RetrievalResult(id="dup", text="version1", score=1.0, source="vector")]
        list2 = [RetrievalResult(id="dup", text="version2", score=0.9, source="graph")]
        fused = HybridRetriever._rrf_fusion([list1, list2], k=60)
        assert len(fused) == 1
        assert fused[0].text == "version1"

from __future__ import annotations

from collections import defaultdict

from graphmind.config import Settings, get_settings
from graphmind.retrieval.embedder import Embedder
from graphmind.retrieval.graph_retriever import GraphRetriever
from graphmind.retrieval.vector_retriever import VectorRetriever
from graphmind.schemas import RetrievalResult


class HybridRetriever:
    def __init__(
        self,
        vector_retriever: VectorRetriever,
        graph_retriever: GraphRetriever,
        embedder: Embedder,
        settings: Settings | None = None,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._graph_retriever = graph_retriever
        self._embedder = embedder
        self._settings = settings or get_settings()

    async def retrieve(self, query: str, top_n: int = 10) -> list[RetrievalResult]:
        query_vector = await self._embedder.embed(query)

        vector_top_k = self._settings.retrieval.vector_top_k
        vector_results = await self._vector_retriever.search(
            query_vector=query_vector, limit=vector_top_k
        )

        entity_ids = [r.entity_id for r in vector_results if r.entity_id is not None]

        graph_hops = self._settings.retrieval.graph_hops
        graph_results: list[RetrievalResult] = []
        if entity_ids:
            graph_results = await self._graph_retriever.expand(
                entity_ids=entity_ids, hops=graph_hops
            )

        fused = self._rrf_fusion(
            ranked_lists=[vector_results, graph_results],
            k=self._settings.retrieval.rrf_k,
        )

        return fused[:top_n]

    @staticmethod
    def _rrf_fusion(ranked_lists: list[list[RetrievalResult]], k: int) -> list[RetrievalResult]:
        scores: defaultdict[str, float] = defaultdict(float)
        result_map: dict[str, RetrievalResult] = {}

        for ranked_list in ranked_lists:
            for rank, result in enumerate(ranked_list, start=1):
                scores[result.id] += 1.0 / (k + rank)
                if result.id not in result_map:
                    result_map[result.id] = result

        sorted_ids = sorted(scores, key=lambda rid: scores[rid], reverse=True)

        fused_results: list[RetrievalResult] = []
        for result_id in sorted_ids:
            original = result_map[result_id]
            fused_results.append(
                RetrievalResult(
                    id=original.id,
                    text=original.text,
                    score=scores[result_id],
                    source=original.source,
                    entity_id=original.entity_id,
                    metadata=original.metadata,
                )
            )

        return fused_results

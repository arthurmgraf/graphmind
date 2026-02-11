from __future__ import annotations

import structlog

from graphmind.agents.states import AgentState
from graphmind.retrieval.hybrid_retriever import HybridRetriever
from graphmind.schemas import RetrievalResult

logger = structlog.get_logger(__name__)


async def retriever_node(state: AgentState, retriever: HybridRetriever) -> dict:
    sub_questions = state.get("sub_questions") or [state["question"]]

    all_results: list[RetrievalResult] = []
    seen_ids: set[str] = set()

    for sub_q in sub_questions:
        results = await retriever.retrieve(sub_q, top_n=10)
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                all_results.append(r)

    logger.info(
        "Retrieved %d unique documents for %d sub-questions",
        len(all_results),
        len(sub_questions),
    )
    return {"documents": all_results}

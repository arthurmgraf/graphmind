from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from crewai.tools import BaseTool
from pydantic import Field

from graphmind.config import get_settings

logger = logging.getLogger(__name__)


class HybridSearchTool(BaseTool):
    name: str = "hybrid_knowledge_search"
    description: str = (
        "Searches the knowledge base using hybrid retrieval (vector similarity + "
        "knowledge graph traversal with RRF fusion). Input should be a search query string. "
        "Returns ranked documents with text, scores, and source information."
    )
    _retriever: Any = None

    def __init__(self, retriever: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._retriever = retriever

    def _run(self, query: str) -> str:
        if self._retriever is None:
            return json.dumps({"error": "Retriever not configured"})

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    results = pool.submit(
                        asyncio.run, self._retriever.retrieve(query, top_n=10)
                    ).result()
            else:
                results = asyncio.run(self._retriever.retrieve(query, top_n=10))
        except Exception as exc:
            logger.error("Hybrid search failed: %s", exc)
            return json.dumps({"error": str(exc)})

        docs = [
            {
                "id": r.id,
                "text": r.text,
                "score": round(r.score, 4),
                "source": r.source,
                "entity_id": r.entity_id,
            }
            for r in results
        ]
        return json.dumps(docs, ensure_ascii=False)


class GraphExpansionTool(BaseTool):
    name: str = "graph_expansion"
    description: str = (
        "Expands entity relationships in the knowledge graph. Input should be a "
        "comma-separated list of entity IDs. Returns connected entities and their "
        "relationships up to 2 hops away."
    )
    _graph_retriever: Any = None

    def __init__(self, graph_retriever: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._graph_retriever = graph_retriever

    def _run(self, entity_ids_str: str) -> str:
        if self._graph_retriever is None:
            return json.dumps({"error": "Graph retriever not configured"})

        entity_ids = [eid.strip() for eid in entity_ids_str.split(",") if eid.strip()]
        if not entity_ids:
            return json.dumps({"error": "No entity IDs provided"})

        try:
            settings = get_settings()
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    results = pool.submit(
                        asyncio.run,
                        self._graph_retriever.expand(entity_ids, hops=settings.retrieval.graph_hops),
                    ).result()
            else:
                results = asyncio.run(
                    self._graph_retriever.expand(entity_ids, hops=settings.retrieval.graph_hops)
                )
        except Exception as exc:
            logger.error("Graph expansion failed: %s", exc)
            return json.dumps({"error": str(exc)})

        nodes = [
            {"id": r.id, "text": r.text, "source": r.source, "entity_id": r.entity_id}
            for r in results
        ]
        return json.dumps(nodes, ensure_ascii=False)


class EvaluateAnswerTool(BaseTool):
    name: str = "evaluate_answer_quality"
    description: str = (
        "Evaluates an answer's quality against the original question and source documents. "
        "Input should be JSON with keys: question, answer, documents (list of text snippets). "
        "Returns relevancy, groundedness, completeness scores and feedback."
    )

    def _run(self, input_json: str) -> str:
        try:
            data = json.loads(input_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON input"})

        question = data.get("question", "")
        answer = data.get("answer", "")
        documents = data.get("documents", [])

        if not answer:
            return json.dumps({"score": 0.0, "feedback": "No answer provided"})

        has_citations = "[Source:" in answer or "[Document" in answer
        addresses_question = any(
            word.lower() in answer.lower()
            for word in question.split()
            if len(word) > 3
        )
        uses_context = any(
            doc_text[:50].lower() in answer.lower()
            for doc_text in documents[:5]
            if doc_text
        )

        relevancy = 0.8 if addresses_question else 0.4
        groundedness = 0.9 if has_citations else 0.5
        completeness = 0.7 if len(answer) > 100 else 0.4

        combined = (relevancy * 0.4) + (groundedness * 0.4) + (completeness * 0.2)

        return json.dumps({
            "relevancy": relevancy,
            "groundedness": groundedness,
            "completeness": completeness,
            "combined": round(combined, 3),
            "feedback": "Answer evaluated successfully",
        })

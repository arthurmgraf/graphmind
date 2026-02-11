from __future__ import annotations

import structlog

from langchain_core.messages import HumanMessage, SystemMessage

from graphmind.agents.states import AgentState
from graphmind.llm_router import LLMRouter
from graphmind.schemas import Citation

logger = structlog.get_logger(__name__)

SYNTHESIZER_SYSTEM = """You are a knowledge synthesis specialist. Given a question and
retrieved documents, produce a comprehensive, accurate answer.

Rules:
- Base your answer ONLY on the provided documents. Do not use prior knowledge.
- Cite sources using [Source: doc_id] format inline.
- If documents don't contain enough information, say so explicitly.
- Be concise but thorough. Use structured format (bullets, headers) for complex answers.
- If comparing things, use a table or side-by-side format."""


async def synthesizer_node(state: AgentState, router: LLMRouter) -> dict:
    question = state["question"]
    documents = state.get("documents", [])

    if not documents:
        return {
            "generation": "I could not find relevant information to answer this question.",
            "citations": [],
        }

    context_parts = []
    for i, doc in enumerate(documents[:10]):
        source_label = doc.source or doc.id[:8]
        context_parts.append(f"[Document {i + 1} | ID: {doc.id[:8]} | Source: {source_label}]\n{doc.text}")

    context = "\n\n---\n\n".join(context_parts)

    messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(content=f"Question: {question}\n\nDocuments:\n{context}"),
    ]

    response = await router.ainvoke(messages)
    answer = response.content.strip()

    # Extract token usage from LLM response metadata
    usage: dict = {}
    meta = getattr(response, "response_metadata", {}) or {}
    if "token_usage" in meta:
        usage = meta["token_usage"]
    elif "usage_metadata" in meta:
        usage = meta["usage_metadata"]
    elif "usage" in meta:
        usage = meta["usage"]
    provider = meta.get("provider", state.get("provider_used", ""))

    citations = [
        Citation(
            document_id=doc.metadata.get("document_id", doc.id),
            chunk_id=doc.id,
            text_snippet=doc.text[:200],
            source=doc.source,
        )
        for doc in documents[:10]
        if doc.id[:8] in answer
    ]

    logger.info("Synthesized answer with %d citations", len(citations))
    return {
        "generation": answer,
        "citations": citations,
        "usage": usage,
        "provider_used": provider,
    }

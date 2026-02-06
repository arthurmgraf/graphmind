from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from graphmind.agents.states import AgentState
from graphmind.llm_router import LLMRouter

logger = logging.getLogger(__name__)

EVALUATOR_SYSTEM = """You are an answer quality evaluator. Given a question, an answer, and
the source documents, evaluate the answer on three dimensions.

Score each dimension from 0.0 to 1.0:
1. relevancy: Does the answer address the question?
2. groundedness: Is every claim in the answer supported by the documents?
3. completeness: Does the answer cover all aspects of the question?

Return ONLY valid JSON (no markdown, no explanation):
{"relevancy": 0.0, "groundedness": 0.0, "completeness": 0.0, "feedback": "brief feedback"}"""


async def evaluator_node(state: AgentState, router: LLMRouter) -> dict:
    question = state["question"]
    generation = state.get("generation", "")
    documents = state.get("documents", [])

    if not generation:
        return {"eval_score": 0.0, "eval_feedback": "No generation to evaluate"}

    doc_snippets = "\n---\n".join(d.text[:300] for d in documents[:5])

    messages = [
        SystemMessage(content=EVALUATOR_SYSTEM),
        HumanMessage(
            content=(
                f"Question: {question}\n\n"
                f"Answer: {generation}\n\n"
                f"Source Documents:\n{doc_snippets}"
            )
        ),
    ]

    response = await router.ainvoke(messages)
    raw = response.content.strip()

    try:
        cleaned = raw.strip("`").removeprefix("json").strip()
        scores = json.loads(cleaned)
        relevancy = float(scores.get("relevancy", 0))
        groundedness = float(scores.get("groundedness", 0))
        completeness = float(scores.get("completeness", 0))
        feedback = scores.get("feedback", "")
        combined = (relevancy * 0.4) + (groundedness * 0.4) + (completeness * 0.2)
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Failed to parse evaluator response: %s", raw[:200])
        combined = 0.5
        feedback = "Evaluation parsing failed, using default score"

    logger.info("Evaluation score: %.2f", combined)
    return {"eval_score": combined, "eval_feedback": feedback}

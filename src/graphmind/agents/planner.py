from __future__ import annotations

import structlog

from langchain_core.messages import HumanMessage, SystemMessage

from graphmind.agents.states import AgentState
from graphmind.llm_router import LLMRouter

logger = structlog.get_logger(__name__)

PLANNER_SYSTEM = """You are a query planning specialist. Your job is to decompose complex
questions into simpler sub-questions that can be answered independently.

Rules:
- If the question is simple and factual, return it as-is (single sub-question).
- If the question requires comparing things, create one sub-question per thing plus a comparison.
- If the question requires multi-hop reasoning, break into sequential steps.
- Return ONLY the sub-questions, one per line. No numbering, no explanation.
- Maximum 4 sub-questions."""


async def planner_node(state: AgentState, router: LLMRouter) -> dict:
    question = state["question"]

    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=f"Decompose this question:\n{question}"),
    ]

    response = await router.ainvoke(messages)
    raw = response.content.strip()

    sub_questions = [q.strip() for q in raw.split("\n") if q.strip()]

    if not sub_questions:
        sub_questions = [question]

    if len(sub_questions) > 4:
        sub_questions = sub_questions[:4]

    logger.info("Planner decomposed into %d sub-questions", len(sub_questions))
    return {"sub_questions": sub_questions}

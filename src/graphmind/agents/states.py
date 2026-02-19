from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from graphmind.schemas import Citation, RetrievalResult


class AgentState(TypedDict):
    question: str
    sub_questions: list[str]
    documents: Annotated[list[RetrievalResult], add]
    graph_context: list[dict]
    generation: str
    citations: list[Citation]
    eval_score: float
    eval_feedback: str
    retry_count: int
    provider_used: str
    total_tokens: int
    latency_ms: float
    usage: dict  # Token usage metadata from LLM response

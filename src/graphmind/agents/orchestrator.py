"""LangGraph orchestrator for the GraphMind query pipeline.

Builds a state-machine graph: plan → retrieve → synthesize → evaluate → (retry?)
No module-level global state — the graph is built per-request or injected via DI.
"""

from __future__ import annotations

import time
from functools import partial

import structlog
from langgraph.graph import END, StateGraph

from graphmind.agents.evaluator import evaluator_node
from graphmind.agents.planner import planner_node
from graphmind.agents.retriever_agent import retriever_node
from graphmind.agents.states import AgentState
from graphmind.agents.synthesizer import synthesizer_node
from graphmind.config import get_settings
from graphmind.llm_router import LLMRouter, get_llm_router
from graphmind.retrieval.hybrid_retriever import HybridRetriever

logger = structlog.get_logger(__name__)


def _should_retry(state: AgentState) -> str:
    settings = get_settings()
    if state["eval_score"] >= settings.agents.eval_threshold:
        return "pass"
    if state["retry_count"] >= settings.agents.max_retries:
        logger.info("Max retries reached, returning best attempt")
        return "pass"
    logger.info(
        "Score %.2f below threshold %.2f, retrying (%d/%d)",
        state["eval_score"],
        settings.agents.eval_threshold,
        state["retry_count"],
        settings.agents.max_retries,
    )
    return "retry"


async def _rewrite_node(state: AgentState, router: LLMRouter) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage

    feedback = state.get("eval_feedback", "")
    question = state["question"]

    messages = [
        SystemMessage(
            content="Rewrite this question to get better search results. "
            "Consider the feedback and make the question more specific."
        ),
        HumanMessage(content=f"Original: {question}\nFeedback: {feedback}"),
    ]
    response = await router.ainvoke(messages)
    new_question = response.content.strip()  # type: ignore[union-attr]

    return {
        "question": new_question,
        "sub_questions": [],
        "documents": [],
        "retry_count": state["retry_count"] + 1,
    }


def build_graph(
    router: LLMRouter | None = None,
    retriever: HybridRetriever | None = None,
) -> StateGraph:
    if router is None:
        router = get_llm_router()

    workflow = StateGraph(AgentState)

    workflow.add_node("plan", partial(planner_node, router=router))
    if retriever is not None:
        workflow.add_node("retrieve", partial(retriever_node, retriever=retriever))
    workflow.add_node("synthesize", partial(synthesizer_node, router=router))
    workflow.add_node("evaluate", partial(evaluator_node, router=router))
    workflow.add_node("rewrite", partial(_rewrite_node, router=router))

    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "retrieve")
    workflow.add_edge("retrieve", "synthesize")
    workflow.add_edge("synthesize", "evaluate")
    workflow.add_conditional_edges(
        "evaluate",
        _should_retry,
        {"retry": "rewrite", "pass": END},
    )
    workflow.add_edge("rewrite", "plan")

    return workflow.compile()  # type: ignore[return-value]


def get_orchestrator(
    router: LLMRouter | None = None,
    retriever: HybridRetriever | None = None,
):
    """Build a new graph for the given router/retriever combination."""
    return build_graph(router=router, retriever=retriever)


async def run_query(
    question: str,
    retriever: HybridRetriever | None = None,
    engine: str = "langgraph",
    router: LLMRouter | None = None,
) -> dict:
    if engine == "crewai":
        from graphmind.crew.crew import run_crew_query

        logger.info("Running query with CrewAI engine")
        result = await run_crew_query(question=question, retriever=retriever)
        return result

    graph = get_orchestrator(router=router, retriever=retriever)

    initial_state: AgentState = {
        "question": question,
        "sub_questions": [],
        "documents": [],
        "graph_context": [],
        "generation": "",
        "citations": [],
        "eval_score": 0.0,
        "eval_feedback": "",
        "retry_count": 0,
        "provider_used": "",
        "total_tokens": 0,
        "latency_ms": 0.0,
        "usage": {},
    }

    start = time.perf_counter()
    result = await graph.ainvoke(initial_state)
    elapsed_ms = (time.perf_counter() - start) * 1000

    result["latency_ms"] = elapsed_ms
    if not result.get("provider_used"):
        result["provider_used"] = "groq"
    logger.info("Query completed in %.0fms with score %.2f", elapsed_ms, result["eval_score"])
    return result

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from graphmind.agents.states import AgentState


def _make_state(**overrides) -> AgentState:
    defaults: AgentState = {
        "question": "What is LangGraph?",
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
    }
    defaults.update(overrides)
    return defaults


class TestPlannerNode:
    @pytest.mark.asyncio
    async def test_decomposes_question(self, mock_router):
        from graphmind.agents.planner import planner_node

        mock_router.ainvoke.return_value.content = "Sub-question 1\nSub-question 2"
        state = _make_state()
        result = await planner_node(state, router=mock_router)
        assert "sub_questions" in result
        assert len(result["sub_questions"]) == 2

    @pytest.mark.asyncio
    async def test_caps_at_four_sub_questions(self, mock_router):
        from graphmind.agents.planner import planner_node

        mock_router.ainvoke.return_value.content = "Q1\nQ2\nQ3\nQ4\nQ5\nQ6"
        state = _make_state()
        result = await planner_node(state, router=mock_router)
        assert len(result["sub_questions"]) <= 4

    @pytest.mark.asyncio
    async def test_empty_response_uses_original(self, mock_router):
        from graphmind.agents.planner import planner_node

        mock_router.ainvoke.return_value.content = ""
        state = _make_state(question="Original question")
        result = await planner_node(state, router=mock_router)
        assert result["sub_questions"] == ["Original question"]


class TestSynthesizerNode:
    @pytest.mark.asyncio
    async def test_generates_answer_with_docs(self, mock_router, sample_retrieval_results):
        from graphmind.agents.synthesizer import synthesizer_node

        mock_router.ainvoke.return_value.content = "Synthesized answer."
        state = _make_state(
            documents=sample_retrieval_results,
            sub_questions=["What is LangGraph?"],
        )
        result = await synthesizer_node(state, router=mock_router)
        assert "generation" in result
        assert result["generation"] == "Synthesized answer."

    @pytest.mark.asyncio
    async def test_returns_fallback_when_no_docs(self, mock_router):
        from graphmind.agents.synthesizer import synthesizer_node

        state = _make_state(documents=[], sub_questions=["What is LangGraph?"])
        result = await synthesizer_node(state, router=mock_router)
        assert "generation" in result
        assert "could not find" in result["generation"].lower()


class TestEvaluatorNode:
    @pytest.mark.asyncio
    async def test_parses_eval_score(self, mock_router):
        from graphmind.agents.evaluator import evaluator_node

        mock_router.ainvoke.return_value.content = '{"score": 0.85, "feedback": "Good answer"}'
        state = _make_state(generation="Some answer")
        result = await evaluator_node(state, router=mock_router)
        assert "eval_score" in result


class TestShouldRetry:
    def test_passes_when_above_threshold(self):
        from graphmind.agents.orchestrator import _should_retry

        state = _make_state(eval_score=0.8, retry_count=0)
        assert _should_retry(state) == "pass"

    def test_retries_when_below_threshold(self):
        from graphmind.agents.orchestrator import _should_retry

        state = _make_state(eval_score=0.3, retry_count=0)
        assert _should_retry(state) == "retry"

    def test_passes_when_max_retries_reached(self):
        from graphmind.agents.orchestrator import _should_retry

        state = _make_state(eval_score=0.3, retry_count=2)
        assert _should_retry(state) == "pass"

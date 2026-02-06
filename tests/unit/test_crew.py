from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from graphmind.crew.tools import EvaluateAnswerTool, HybridSearchTool


class TestHybridSearchTool:
    def test_returns_error_when_no_retriever(self):
        tool = HybridSearchTool(retriever=None)
        result = json.loads(tool._run("test query"))
        assert "error" in result
        assert result["error"] == "Retriever not configured"

    def test_metadata(self):
        tool = HybridSearchTool()
        assert tool.name == "hybrid_knowledge_search"
        assert "hybrid" in tool.description.lower()


class TestEvaluateAnswerTool:
    def test_evaluates_good_answer(self):
        tool = EvaluateAnswerTool()
        input_data = json.dumps({
            "question": "What is LangGraph?",
            "answer": "LangGraph is a framework for building stateful applications. [Source: doc1] It supports cyclic graphs.",
            "documents": ["LangGraph is a framework for building stateful applications."],
        })
        result = json.loads(tool._run(input_data))
        assert "relevancy" in result
        assert "groundedness" in result
        assert "completeness" in result
        assert "combined" in result
        assert result["groundedness"] == 0.9

    def test_evaluates_poor_answer(self):
        tool = EvaluateAnswerTool()
        input_data = json.dumps({
            "question": "What is LangGraph?",
            "answer": "Short",
            "documents": ["LangGraph is a framework."],
        })
        result = json.loads(tool._run(input_data))
        assert result["completeness"] == 0.4

    def test_handles_empty_answer(self):
        tool = EvaluateAnswerTool()
        input_data = json.dumps({
            "question": "What is LangGraph?",
            "answer": "",
            "documents": [],
        })
        result = json.loads(tool._run(input_data))
        assert result["score"] == 0.0

    def test_handles_invalid_json(self):
        tool = EvaluateAnswerTool()
        result = json.loads(tool._run("not json"))
        assert "error" in result


class TestCrewAgents:
    def test_create_research_planner(self):
        from graphmind.crew.agents import create_research_planner

        agent = create_research_planner(llm=MagicMock())
        assert agent.role == "Research Planner"
        assert agent.allow_delegation is False

    def test_create_knowledge_retriever(self):
        from graphmind.crew.agents import create_knowledge_retriever

        agent = create_knowledge_retriever(llm=MagicMock())
        assert agent.role == "Knowledge Retriever"

    def test_create_answer_synthesizer(self):
        from graphmind.crew.agents import create_answer_synthesizer

        agent = create_answer_synthesizer(llm=MagicMock())
        assert agent.role == "Answer Synthesizer"

    def test_create_quality_evaluator(self):
        from graphmind.crew.agents import create_quality_evaluator

        agent = create_quality_evaluator(llm=MagicMock())
        assert agent.role == "Quality Evaluator"
        assert len(agent.tools) == 1


class TestCrewTasks:
    def test_create_planning_task(self):
        from graphmind.crew.tasks import create_planning_task

        agent = MagicMock()
        task = create_planning_task(agent, "What is LangGraph?")
        assert "LangGraph" in task.description
        assert task.agent is agent

    def test_create_retrieval_task_has_context(self):
        from graphmind.crew.tasks import create_planning_task, create_retrieval_task

        agent = MagicMock()
        planning = create_planning_task(agent, "test")
        retrieval = create_retrieval_task(agent, "test", planning)
        assert planning in retrieval.context

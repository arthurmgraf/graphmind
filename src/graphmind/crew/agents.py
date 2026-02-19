from __future__ import annotations

from typing import Any

import structlog
from crewai import Agent

from graphmind.crew.tools import EvaluateAnswerTool, GraphExpansionTool, HybridSearchTool

logger = structlog.get_logger(__name__)


def create_research_planner(llm: Any = None) -> Agent:
    return Agent(
        role="Research Planner",
        goal=(
            "Analyze complex questions and decompose them into focused sub-questions "
            "that can be independently researched to build a comprehensive answer."
        ),
        backstory=(
            "You are an expert research strategist with deep experience in knowledge "
            "management and information retrieval. You excel at breaking down complex "
            "queries into atomic, searchable sub-questions. You understand that multi-hop "
            "reasoning requires sequential decomposition, while comparisons need parallel "
            "investigation of each subject."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )


def create_knowledge_retriever(
    llm: Any = None,
    retriever: Any = None,
    graph_retriever: Any = None,
) -> Agent:
    tools = []
    if retriever is not None:
        tools.append(HybridSearchTool(retriever=retriever))
    if graph_retriever is not None:
        tools.append(GraphExpansionTool(graph_retriever=graph_retriever))  # type: ignore[arg-type]

    return Agent(
        role="Knowledge Retriever",
        goal=(
            "Find the most relevant information from the knowledge base by combining "
            "vector similarity search with knowledge graph traversal. Retrieve "
            "comprehensive context that covers all aspects of the sub-questions."
        ),
        backstory=(
            "You are a specialist in hybrid information retrieval, combining semantic "
            "vector search with structured knowledge graph traversal. You understand "
            "that the best results come from fusing multiple retrieval strategies. "
            "You always search for each sub-question independently and deduplicate results."
        ),
        tools=tools,
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )


def create_answer_synthesizer(llm: Any = None) -> Agent:
    return Agent(
        role="Answer Synthesizer",
        goal=(
            "Produce comprehensive, accurate, well-cited answers based exclusively "
            "on retrieved documents. Never use prior knowledge outside the provided context."
        ),
        backstory=(
            "You are a knowledge synthesis expert who excels at combining information "
            "from multiple sources into coherent, well-structured answers. You always "
            "cite your sources using [Source: doc_id] format. You use structured formats "
            "(bullets, tables) for complex or comparative answers. When documents lack "
            "sufficient information, you explicitly state what is missing."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )


def create_quality_evaluator(llm: Any = None) -> Agent:
    tools = [EvaluateAnswerTool()]

    return Agent(
        role="Quality Evaluator",
        goal=(
            "Rigorously evaluate answer quality on relevancy, groundedness, and "
            "completeness. Provide actionable feedback when quality is below threshold."
        ),
        backstory=(
            "You are a quality assurance specialist for AI-generated answers. You score "
            "answers on three dimensions: relevancy (does it address the question), "
            "groundedness (is every claim supported by source documents), and completeness "
            "(does it cover all aspects). You provide specific, actionable feedback for "
            "improvement when scores are below 0.7."
        ),
        tools=tools,
        verbose=False,
        allow_delegation=False,
        llm=llm,
    )

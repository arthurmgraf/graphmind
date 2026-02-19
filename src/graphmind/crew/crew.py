from __future__ import annotations

import json
import time
from typing import Any

import structlog
from crewai import Crew, Process

from graphmind.config import get_settings
from graphmind.crew.agents import (
    create_answer_synthesizer,
    create_knowledge_retriever,
    create_quality_evaluator,
    create_research_planner,
)
from graphmind.crew.tasks import (
    create_evaluation_task,
    create_planning_task,
    create_retrieval_task,
    create_synthesis_task,
)
from graphmind.retrieval.hybrid_retriever import HybridRetriever

logger = structlog.get_logger(__name__)


class GraphMindCrew:
    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        graph_retriever: Any = None,
        llm: Any = None,
    ) -> None:
        self._retriever = retriever
        self._graph_retriever = graph_retriever
        self._llm = llm
        self._settings = get_settings()

    def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        try:
            from langchain_groq import ChatGroq

            settings = self._settings
            return ChatGroq(
                model=settings.llm_primary.model,
                api_key=settings.groq_api_key,  # type: ignore[arg-type]
                temperature=settings.llm_primary.temperature,
                max_tokens=settings.llm_primary.max_tokens,
            )
        except Exception:
            logger.warning("Failed to create Groq LLM for CrewAI, using default")
            return None

    def run(self, question: str) -> dict:
        settings = self._settings
        max_retries = settings.agents.max_retries
        threshold = settings.agents.eval_threshold

        best_result: dict = {}
        best_score = 0.0

        for attempt in range(max_retries + 1):
            current_question = (
                question
                if attempt == 0
                else self._rewrite_question(question, best_result.get("eval_feedback", ""))
            )

            result = self._execute_crew(current_question, question)

            eval_score = result.get("eval_score", 0.0)
            if eval_score > best_score:
                best_score = eval_score
                best_result = result

            if eval_score >= threshold:
                logger.info(
                    "CrewAI query passed on attempt %d with score %.2f",
                    attempt + 1,
                    eval_score,
                )
                break

            if attempt < max_retries:
                logger.info(
                    "CrewAI score %.2f below threshold %.2f, retrying (%d/%d)",
                    eval_score,
                    threshold,
                    attempt + 1,
                    max_retries,
                )

        best_result["retry_count"] = min(attempt, max_retries)
        return best_result

    def _execute_crew(self, question: str, original_question: str) -> dict:
        start = time.perf_counter()
        llm = self._get_llm()

        planner = create_research_planner(llm=llm)
        retriever = create_knowledge_retriever(
            llm=llm,
            retriever=self._retriever,
            graph_retriever=self._graph_retriever,
        )
        synthesizer = create_answer_synthesizer(llm=llm)
        evaluator = create_quality_evaluator(llm=llm)

        planning_task = create_planning_task(planner, question)
        retrieval_task = create_retrieval_task(retriever, question, planning_task)
        synthesis_task = create_synthesis_task(synthesizer, question, retrieval_task)
        evaluation_task = create_evaluation_task(
            evaluator,
            original_question,
            synthesis_task,
            retrieval_task,
        )

        crew = Crew(
            agents=[planner, retriever, synthesizer, evaluator],
            tasks=[planning_task, retrieval_task, synthesis_task, evaluation_task],
            process=Process.sequential,
            verbose=False,
        )

        try:
            crew_output = crew.kickoff()
            raw_output = str(crew_output)
        except Exception as exc:
            logger.error("CrewAI execution failed: %s", exc)
            return {
                "generation": f"CrewAI pipeline failed: {exc}",
                "citations": [],
                "eval_score": 0.0,
                "eval_feedback": str(exc),
                "latency_ms": (time.perf_counter() - start) * 1000,
            }

        elapsed_ms = (time.perf_counter() - start) * 1000

        eval_score = 0.5
        eval_feedback = ""
        try:
            eval_data = json.loads(raw_output)
            eval_score = float(eval_data.get("combined", eval_data.get("eval_score", 0.5)))
            eval_feedback = eval_data.get("feedback", "")
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        generation = str(synthesis_task.output) if synthesis_task.output else raw_output

        return {
            "question": question,
            "generation": generation,
            "citations": [],
            "eval_score": eval_score,
            "eval_feedback": eval_feedback,
            "provider_used": "crewai",
            "latency_ms": elapsed_ms,
        }

    def _rewrite_question(self, original: str, feedback: str) -> str:
        llm = self._get_llm()
        if llm is None:
            return original

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(
                    content="Rewrite this question to get better search results. "
                    "Consider the feedback and make the question more specific."
                ),
                HumanMessage(content=f"Original: {original}\nFeedback: {feedback}"),
            ]
            response = llm.invoke(messages)
            return response.content.strip()
        except Exception as exc:
            logger.warning("Question rewrite failed: %s", exc)
            return original


async def run_crew_query(
    question: str,
    retriever: HybridRetriever | None = None,
) -> dict:
    crew = GraphMindCrew(retriever=retriever)
    return crew.run(question)

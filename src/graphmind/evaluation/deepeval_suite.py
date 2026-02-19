from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import structlog

from graphmind.evaluation.eval_models import GroqEvalModel

logger = structlog.get_logger(__name__)


@dataclass
class EvalResult:
    question: str
    relevancy: float
    groundedness: float
    completeness: float
    combined: float
    passed: bool


def evaluate_single(
    question: str,
    answer: str,
    context: list[str],
    eval_model: GroqEvalModel | None = None,
    threshold: float = 0.7,
) -> EvalResult:
    if eval_model is None:
        eval_model = GroqEvalModel()

    context_text = "\n---\n".join(context[:5])

    prompt = f"""Evaluate this answer on three dimensions. Score each 0.0 to 1.0.

Question: {question}
Answer: {answer}
Context Documents:
{context_text}

Return ONLY valid JSON:
{{"relevancy": 0.0, "groundedness": 0.0, "completeness": 0.0}}"""

    try:
        raw = eval_model.generate(prompt)
        cleaned = raw.strip("`").removeprefix("json").strip()
        scores = json.loads(cleaned)
        relevancy = float(scores.get("relevancy", 0))
        groundedness = float(scores.get("groundedness", 0))
        completeness = float(scores.get("completeness", 0))
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Failed to parse eval response, using defaults")
        relevancy = groundedness = completeness = 0.5

    combined = (relevancy * 0.4) + (groundedness * 0.4) + (completeness * 0.2)

    return EvalResult(
        question=question,
        relevancy=relevancy,
        groundedness=groundedness,
        completeness=completeness,
        combined=combined,
        passed=combined >= threshold,
    )


def evaluate_benchmark(
    dataset_path: str | Path,
    eval_model: GroqEvalModel | None = None,
    threshold: float = 0.7,
) -> list[EvalResult]:
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark dataset not found: {path}")

    results: list[EvalResult] = []

    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            result = evaluate_single(
                question=entry["question"],
                answer=entry.get("answer", ""),
                context=entry.get("context", []),
                eval_model=eval_model,
                threshold=threshold,
            )
            results.append(result)
            logger.info(
                "Eval: %s | score=%.2f | %s",
                entry["question"][:50],
                result.combined,
                "PASS" if result.passed else "FAIL",
            )

    return results


def generate_report(results: list[EvalResult]) -> dict:
    if not results:
        return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}

    passed = sum(1 for r in results if r.passed)
    avg_relevancy = sum(r.relevancy for r in results) / len(results)
    avg_groundedness = sum(r.groundedness for r in results) / len(results)
    avg_completeness = sum(r.completeness for r in results) / len(results)
    avg_combined = sum(r.combined for r in results) / len(results)

    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3),
        "avg_relevancy": round(avg_relevancy, 3),
        "avg_groundedness": round(avg_groundedness, 3),
        "avg_completeness": round(avg_completeness, 3),
        "avg_combined": round(avg_combined, 3),
    }

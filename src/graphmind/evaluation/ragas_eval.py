from __future__ import annotations

import json
import structlog
from pathlib import Path

logger = structlog.get_logger(__name__)


def run_ragas_evaluation(
    dataset_path: str | Path,
    llm_model: str = "groq/llama-3.3-70b-versatile",
) -> dict:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.llms import llm_factory
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except ImportError:
        logger.error("RAGAS not installed. Run: pip install 'graphmind[eval]'")
        return {"error": "ragas not installed"}

    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    questions, answers, contexts, ground_truths = [], [], [], []

    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            questions.append(entry["question"])
            answers.append(entry.get("answer", ""))
            contexts.append(entry.get("context", []))
            ground_truths.append(entry.get("ground_truth", ""))

    eval_dataset = Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
    )

    llm = llm_factory(model=llm_model)

    result = evaluate(
        dataset=eval_dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=llm,
    )

    scores = {k: round(float(v), 4) for k, v in result.items() if isinstance(v, (int, float))}
    logger.info("RAGAS evaluation complete: %s", scores)
    return scores

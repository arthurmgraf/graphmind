from __future__ import annotations

import json
import logging
from pathlib import Path

from graphmind.evaluation.deepeval_suite import evaluate_benchmark, generate_report
from graphmind.evaluation.eval_models import GroqEvalModel

logger = logging.getLogger(__name__)

_BENCHMARK_PATH = Path(__file__).resolve().parent.parent.parent.parent / "eval" / "benchmark_dataset.jsonl"
_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "eval" / "reports"


def run_full_benchmark(
    dataset_path: str | Path | None = None,
    threshold: float = 0.7,
) -> dict:
    path = Path(dataset_path) if dataset_path else _BENCHMARK_PATH

    logger.info("Running benchmark from %s", path)
    eval_model = GroqEvalModel()

    results = evaluate_benchmark(path, eval_model=eval_model, threshold=threshold)
    report = generate_report(results)

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _REPORTS_DIR / "latest_benchmark.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Benchmark report saved to %s", report_path)
    logger.info(
        "Results: %d/%d passed (%.1f%%) | avg_score=%.3f",
        report["passed"],
        report["total"],
        report["pass_rate"] * 100,
        report["avg_combined"],
    )
    return report


def cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run GraphMind evaluation benchmark")
    parser.add_argument("--dataset", type=str, default=None, help="Path to benchmark JSONL")
    parser.add_argument("--threshold", type=float, default=0.7, help="Pass/fail threshold")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    run_full_benchmark(dataset_path=args.dataset, threshold=args.threshold)


if __name__ == "__main__":
    cli()

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from graphmind.evaluation.deepeval_suite import evaluate_benchmark, generate_report


@pytest.mark.integration
class TestEvalBenchmarkIntegration:
    def test_evaluate_benchmark_from_file(self, tmp_path):
        dataset = tmp_path / "test_dataset.jsonl"
        entries = [
            {
                "question": "What is Python?",
                "answer": "Python is a programming language.",
                "context": ["Python is a high-level programming language."],
                "ground_truth": "Python is a programming language.",
            },
            {
                "question": "What is JavaScript?",
                "answer": "JavaScript is a web scripting language.",
                "context": ["JavaScript runs in browsers."],
                "ground_truth": "JavaScript is a scripting language for the web.",
            },
        ]
        with open(dataset, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        eval_model = MagicMock()
        eval_model.generate.return_value = '{"relevancy": 0.85, "groundedness": 0.9, "completeness": 0.8}'

        results = evaluate_benchmark(dataset, eval_model=eval_model, threshold=0.7)
        assert len(results) == 2
        assert all(r.passed for r in results)

        report = generate_report(results)
        assert report["total"] == 2
        assert report["passed"] == 2
        assert report["pass_rate"] == 1.0
        assert report["avg_combined"] > 0

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            evaluate_benchmark("/nonexistent/file.jsonl")

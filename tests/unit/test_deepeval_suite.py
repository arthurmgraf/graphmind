from __future__ import annotations

from unittest.mock import MagicMock

from graphmind.evaluation.deepeval_suite import EvalResult, evaluate_single, generate_report


class TestEvaluateSingle:
    def test_parses_valid_json_response(self):
        eval_model = MagicMock()
        eval_model.generate.return_value = '{"relevancy": 0.9, "groundedness": 0.85, "completeness": 0.8}'

        result = evaluate_single(
            question="What is LangGraph?",
            answer="LangGraph is a framework.",
            context=["LangGraph is a library for building apps."],
            eval_model=eval_model,
        )
        assert isinstance(result, EvalResult)
        assert result.relevancy == 0.9
        assert result.groundedness == 0.85
        assert result.completeness == 0.8
        expected_combined = (0.9 * 0.4) + (0.85 * 0.4) + (0.8 * 0.2)
        assert abs(result.combined - expected_combined) < 0.001
        assert result.passed is True

    def test_handles_json_with_markdown_fences(self):
        eval_model = MagicMock()
        eval_model.generate.return_value = '```json\n{"relevancy": 0.7, "groundedness": 0.7, "completeness": 0.7}\n```'

        result = evaluate_single(
            question="test", answer="test", context=["ctx"],
            eval_model=eval_model,
        )
        assert result.relevancy == 0.7

    def test_falls_back_on_parse_error(self):
        eval_model = MagicMock()
        eval_model.generate.return_value = "not valid json"

        result = evaluate_single(
            question="test", answer="test", context=["ctx"],
            eval_model=eval_model,
        )
        assert result.relevancy == 0.5
        assert result.groundedness == 0.5
        assert result.completeness == 0.5

    def test_below_threshold_fails(self):
        eval_model = MagicMock()
        eval_model.generate.return_value = '{"relevancy": 0.3, "groundedness": 0.3, "completeness": 0.3}'

        result = evaluate_single(
            question="test", answer="test", context=["ctx"],
            eval_model=eval_model, threshold=0.7,
        )
        assert result.passed is False


class TestGenerateReport:
    def test_empty_results(self):
        report = generate_report([])
        assert report["total"] == 0
        assert report["passed"] == 0
        assert report["pass_rate"] == 0.0

    def test_all_passing(self):
        results = [
            EvalResult("q1", 0.9, 0.9, 0.9, 0.9, True),
            EvalResult("q2", 0.8, 0.8, 0.8, 0.8, True),
        ]
        report = generate_report(results)
        assert report["total"] == 2
        assert report["passed"] == 2
        assert report["pass_rate"] == 1.0

    def test_mixed_results(self):
        results = [
            EvalResult("q1", 0.9, 0.9, 0.9, 0.9, True),
            EvalResult("q2", 0.3, 0.3, 0.3, 0.3, False),
        ]
        report = generate_report(results)
        assert report["total"] == 2
        assert report["passed"] == 1
        assert report["failed"] == 1
        assert report["pass_rate"] == 0.5

    def test_report_has_all_averages(self):
        results = [EvalResult("q1", 0.8, 0.7, 0.6, 0.72, True)]
        report = generate_report(results)
        assert "avg_relevancy" in report
        assert "avg_groundedness" in report
        assert "avg_completeness" in report
        assert "avg_combined" in report

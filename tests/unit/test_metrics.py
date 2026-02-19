from __future__ import annotations

import pytest

from graphmind.observability.metrics import MetricsCollector, QueryMetric


class TestMetricsCollector:
    def test_initial_state(self):
        mc = MetricsCollector()
        assert mc.total_queries == 0
        assert mc.avg_latency_ms == 0.0
        assert mc.avg_eval_score == 0.0
        assert mc.retry_rate == 0.0

    def test_record_metric(self):
        mc = MetricsCollector()
        mc.record(
            QueryMetric(
                question="What is LangGraph?",
                latency_ms=150.0,
                eval_score=0.85,
                retry_count=0,
                sources_used=5,
                provider="groq",
            )
        )
        assert mc.total_queries == 1
        assert mc.avg_latency_ms == 150.0
        assert mc.avg_eval_score == 0.85
        assert mc.retry_rate == 0.0

    def test_avg_across_multiple(self):
        mc = MetricsCollector()
        mc.record(QueryMetric("q1", 100.0, 0.8, 0, 3, "groq"))
        mc.record(QueryMetric("q2", 200.0, 0.9, 1, 5, "groq"))
        assert mc.avg_latency_ms == pytest.approx(150.0)
        assert mc.avg_eval_score == pytest.approx(0.85)
        assert mc.retry_rate == pytest.approx(0.5)

    def test_p95_latency(self):
        mc = MetricsCollector()
        for i in range(100):
            mc.record(QueryMetric(f"q{i}", float(i), 0.8, 0, 3, "groq"))
        p95 = mc.p95_latency_ms()
        assert p95 >= 90.0

    def test_summary_structure(self):
        mc = MetricsCollector()
        mc.record(QueryMetric("q1", 100.0, 0.8, 0, 3, "groq"))
        summary = mc.summary()
        assert "total_queries" in summary
        assert "avg_latency_ms" in summary
        assert "p95_latency_ms" in summary
        assert "avg_eval_score" in summary
        assert "retry_rate" in summary

    def test_recent(self):
        mc = MetricsCollector()
        for i in range(20):
            mc.record(QueryMetric(f"question-{i}", float(i), 0.8, 0, 3, "groq"))
        recent = mc.recent(5)
        assert len(recent) == 5
        assert recent[0]["question"].startswith("question-19")

    def test_max_history(self):
        mc = MetricsCollector(max_history=5)
        for i in range(10):
            mc.record(QueryMetric(f"q{i}", float(i), 0.8, 0, 3, "groq"))
        assert mc.total_queries == 5

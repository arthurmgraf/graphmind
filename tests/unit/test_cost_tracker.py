from __future__ import annotations

from graphmind.observability.cost_tracker import CostTracker, QueryCost


class TestCostTracker:
    def test_initial_state(self):
        tracker = CostTracker()
        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0
        assert tracker.total_calls == 0

    def test_record_adds_entry(self):
        tracker = CostTracker()
        entry = tracker.record(
            provider="groq",
            model="llama-3.3-70b-versatile",
            input_tokens=100,
            output_tokens=50,
        )
        assert isinstance(entry, QueryCost)
        assert entry.total_tokens == 150
        assert tracker.total_calls == 1

    def test_multiple_records(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100, 50)
        tracker.record("gemini", "gemini-pro", 200, 100)
        assert tracker.total_calls == 2
        assert tracker.total_tokens == 450

    def test_summary_structure(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100, 50)
        summary = tracker.summary()
        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert "total_calls" in summary
        assert "by_provider" in summary
        assert "groq" in summary["by_provider"]

    def test_by_provider_aggregation(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100, 50)
        tracker.record("groq", "llama", 200, 100)
        tracker.record("gemini", "gemini-pro", 300, 150)
        summary = tracker.summary()
        assert summary["by_provider"]["groq"]["calls"] == 2
        assert summary["by_provider"]["gemini"]["calls"] == 1
        assert summary["by_provider"]["groq"]["tokens"] == 450


class TestQueryCost:
    def test_default_values(self):
        qc = QueryCost()
        assert qc.provider == ""
        assert qc.cost_usd == 0.0

from __future__ import annotations

from graphmind.observability.cost_tracker import BudgetAlert, CostTracker


class TestBudgetAlertDataclass:
    def test_default_fields(self):
        alert = BudgetAlert(threshold_usd=80.0, current_usd=82.0)
        assert alert.threshold_usd == 80.0
        assert alert.current_usd == 82.0
        assert alert.tenant_id == ""
        assert alert.message == ""

    def test_fields_set_correctly(self):
        alert = BudgetAlert(
            threshold_usd=10.0,
            current_usd=12.0,
            tenant_id="acme",
            message="Budget exceeded",
        )
        assert alert.tenant_id == "acme"
        assert alert.message == "Budget exceeded"


class TestBudgetAlertAt80Percent:
    def test_alert_fires_at_80_percent(self):
        tracker = CostTracker(budget_limit_usd=1.0)
        # Groq pricing: input=$0.59/M, output=$0.79/M
        # To reach $0.80 (80% of $1.00) with groq:
        # cost = (input * 0.59 + output * 0.79) / 1_000_000
        # Using 1_000_000 input tokens: cost = 0.59 + 0 = $0.59
        # Using 1_000_000 input + 300_000 output: cost = 0.59 + 0.237 = $0.827
        tracker.record("groq", "llama", 1_000_000, 300_000)
        alerts = tracker.alerts
        assert len(alerts) >= 1
        # Should have the 80% alert
        threshold_values = [a.threshold_usd for a in alerts]
        assert 0.8 in threshold_values


class TestBudgetAlertAt100Percent:
    def test_alert_fires_at_100_percent(self):
        tracker = CostTracker(budget_limit_usd=0.50)
        # Groq: 1M input tokens = $0.59 which exceeds $0.50
        tracker.record("groq", "llama", 1_000_000, 0)
        alerts = tracker.alerts
        threshold_values = [a.threshold_usd for a in alerts]
        # Both 80% ($0.40) and 100% ($0.50) should fire
        assert 0.40 in threshold_values
        assert 0.50 in threshold_values

    def test_both_80_and_100_fire_together(self):
        tracker = CostTracker(budget_limit_usd=0.10)
        # Groq: 1M input = $0.59 which far exceeds $0.10
        tracker.record("groq", "llama", 1_000_000, 0)
        alerts = tracker.alerts
        # Both thresholds (80% = $0.08, 100% = $0.10) should have fired
        assert len(alerts) >= 2
        global_alerts = [a for a in alerts if a.tenant_id == ""]
        assert len(global_alerts) == 2


class TestNoDuplicateAlerts:
    def test_no_duplicate_alerts_for_same_threshold(self):
        tracker = CostTracker(budget_limit_usd=0.50)
        # First call exceeds 80%
        tracker.record("groq", "llama", 1_000_000, 0)
        count_after_first = len(tracker.alerts)

        # Second call adds more cost but should not re-fire same alerts
        tracker.record("groq", "llama", 1_000_000, 0)
        len(tracker.alerts)

        # Global alerts should not duplicate (80% and 100% fired once each)
        global_alerts = [a for a in tracker.alerts if a.tenant_id == ""]
        assert len(global_alerts) == count_after_first  # no new global alerts


class TestPerTenantCostIsolation:
    def test_tenant_cost_returns_tenant_spend(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100_000, 50_000, tenant_id="acme")
        tracker.record("groq", "llama", 200_000, 100_000, tenant_id="beta")

        acme_cost = tracker.tenant_cost("acme")
        beta_cost = tracker.tenant_cost("beta")

        assert acme_cost > 0
        assert beta_cost > 0
        assert beta_cost > acme_cost  # beta used more tokens

    def test_tenant_cost_returns_zero_for_unknown(self):
        tracker = CostTracker()
        assert tracker.tenant_cost("unknown") == 0.0

    def test_tenant_costs_are_isolated(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 500_000, 0, tenant_id="acme")
        tracker.record("gemini", "flash", 500_000, 0, tenant_id="beta")

        # Groq input: 500k * 0.59 / 1M = $0.295
        # Gemini input: 500k * 0.075 / 1M = $0.0375
        acme_cost = tracker.tenant_cost("acme")
        beta_cost = tracker.tenant_cost("beta")
        assert abs(acme_cost - 0.295) < 0.001
        assert abs(beta_cost - 0.0375) < 0.001

    def test_no_tenant_tracking_without_tenant_id(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100_000, 50_000)  # no tenant
        assert tracker.tenant_summary() == {}


class TestTenantSummary:
    def test_tenant_summary_returns_correct_totals(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100_000, 50_000, tenant_id="acme")
        tracker.record("groq", "llama", 200_000, 100_000, tenant_id="acme")
        tracker.record("gemini", "flash", 100_000, 50_000, tenant_id="beta")

        summary = tracker.tenant_summary()
        assert "acme" in summary
        assert "beta" in summary
        assert summary["acme"]["cost_usd"] > 0
        assert summary["beta"]["cost_usd"] > 0

    def test_tenant_summary_matches_tenant_cost(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100_000, 50_000, tenant_id="acme")
        summary = tracker.tenant_summary()
        assert abs(summary["acme"]["cost_usd"] - tracker.tenant_cost("acme")) < 1e-9


class TestSummaryBudgetUsedPct:
    def test_summary_includes_budget_used_pct(self):
        tracker = CostTracker(budget_limit_usd=100.0)
        tracker.record("groq", "llama", 1_000_000, 0)
        summary = tracker.summary()
        assert "budget_used_pct" in summary
        # Groq 1M input = $0.59, budget = $100 -> 0.59%
        expected_pct = round(0.59 / 100.0 * 100, 1)
        assert summary["budget_used_pct"] == expected_pct

    def test_summary_budget_pct_at_zero(self):
        tracker = CostTracker(budget_limit_usd=100.0)
        summary = tracker.summary()
        assert summary["budget_used_pct"] == 0.0

    def test_summary_includes_alerts_fired(self):
        tracker = CostTracker(budget_limit_usd=0.10)
        tracker.record("groq", "llama", 1_000_000, 0)
        summary = tracker.summary()
        assert summary["alerts_fired"] >= 2  # 80% + 100%

    def test_summary_includes_by_tenant(self):
        tracker = CostTracker()
        tracker.record("groq", "llama", 100_000, 0, tenant_id="acme")
        summary = tracker.summary()
        assert "by_tenant" in summary
        assert "acme" in summary["by_tenant"]

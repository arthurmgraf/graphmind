from __future__ import annotations

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

# Pricing per 1 M tokens (USD) — updated 2025-01
PRICING_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "groq": {"input": 0.59, "output": 0.79},  # Llama 3.3 70B
    "gemini": {"input": 0.075, "output": 0.30},  # Gemini 2.0 Flash
    "ollama": {"input": 0.0, "output": 0.0},  # local — zero cost
}


@dataclass
class QueryCost:
    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0


@dataclass
class BudgetAlert:
    """Fired when cost exceeds a threshold."""

    threshold_usd: float
    current_usd: float
    tenant_id: str = ""
    message: str = ""


@dataclass
class CostTracker:
    queries: list[QueryCost] = field(default_factory=list)
    budget_limit_usd: float = 100.0  # monthly budget
    _by_tenant: dict[str, float] = field(default_factory=dict)
    _alerts: list[BudgetAlert] = field(default_factory=list)

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        tenant_id: str = "",
    ) -> QueryCost:
        total = input_tokens + output_tokens
        pricing = PRICING_PER_1M_TOKENS.get(provider, {"input": 0.0, "output": 0.0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        entry = QueryCost(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cost_usd=cost,
            calls=1,
        )
        self.queries.append(entry)

        # Per-tenant cost isolation
        if tenant_id:
            self._by_tenant[tenant_id] = self._by_tenant.get(tenant_id, 0.0) + cost

        # Budget alert check
        self._check_budget_alerts(tenant_id)

        return entry

    def _check_budget_alerts(self, tenant_id: str = "") -> None:
        # Global budget alert at 80% and 100%
        total = self.total_cost
        for threshold_pct in (0.8, 1.0):
            threshold = self.budget_limit_usd * threshold_pct
            if total >= threshold:
                already_alerted = any(
                    a.threshold_usd == threshold and a.tenant_id == "" for a in self._alerts
                )
                if not already_alerted:
                    alert = BudgetAlert(
                        threshold_usd=threshold,
                        current_usd=total,
                        message=(
                            f"Global budget {threshold_pct:.0%} reached:"
                            f" ${total:.4f} / ${self.budget_limit_usd:.2f}"
                        ),
                    )
                    self._alerts.append(alert)
                    logger.warning(
                        "budget_alert",
                        threshold_pct=f"{threshold_pct:.0%}",
                        current_usd=round(total, 6),
                        limit_usd=self.budget_limit_usd,
                    )

        # Per-tenant budget alert
        if tenant_id and tenant_id in self._by_tenant:
            tenant_cost = self._by_tenant[tenant_id]
            tenant_limit = self.budget_limit_usd / 10  # each tenant gets 10% of budget
            if tenant_cost >= tenant_limit:
                already_alerted = any(a.tenant_id == tenant_id for a in self._alerts)
                if not already_alerted:
                    alert = BudgetAlert(
                        threshold_usd=tenant_limit,
                        current_usd=tenant_cost,
                        tenant_id=tenant_id,
                        message=f"Tenant {tenant_id} budget exceeded: ${tenant_cost:.4f}",
                    )
                    self._alerts.append(alert)
                    logger.warning(
                        "tenant_budget_alert",
                        tenant_id=tenant_id,
                        current_usd=round(tenant_cost, 6),
                        limit_usd=tenant_limit,
                    )

    @property
    def total_cost(self) -> float:
        return sum(q.cost_usd for q in self.queries)

    @property
    def total_tokens(self) -> int:
        return sum(q.total_tokens for q in self.queries)

    @property
    def total_calls(self) -> int:
        return len(self.queries)

    @property
    def alerts(self) -> list[BudgetAlert]:
        return list(self._alerts)

    def tenant_cost(self, tenant_id: str) -> float:
        return self._by_tenant.get(tenant_id, 0.0)

    def tenant_summary(self) -> dict[str, dict]:
        return {tid: {"cost_usd": round(cost, 6)} for tid, cost in self._by_tenant.items()}

    def summary(self) -> dict:
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "budget_limit_usd": self.budget_limit_usd,
            "budget_used_pct": round(
                (self.total_cost / self.budget_limit_usd * 100)
                if self.budget_limit_usd > 0
                else 0.0,
                1,
            ),
            "alerts_fired": len(self._alerts),
            "by_provider": self._by_provider(),
            "by_tenant": self.tenant_summary(),
        }

    def _by_provider(self) -> dict[str, dict]:
        providers: dict[str, dict] = {}
        for q in self.queries:
            if q.provider not in providers:
                providers[q.provider] = {"tokens": 0, "cost_usd": 0.0, "calls": 0}
            providers[q.provider]["tokens"] += q.total_tokens
            providers[q.provider]["cost_usd"] += q.cost_usd
            providers[q.provider]["calls"] += 1
        return providers


_tracker = CostTracker()


def get_cost_tracker() -> CostTracker:
    return _tracker

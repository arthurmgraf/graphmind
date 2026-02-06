from __future__ import annotations

from dataclasses import dataclass, field

PRICING_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "groq": {"input": 0.0, "output": 0.0},
    "gemini": {"input": 0.0, "output": 0.0},
    "ollama": {"input": 0.0, "output": 0.0},
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
class CostTracker:
    queries: list[QueryCost] = field(default_factory=list)

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
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
        return entry

    @property
    def total_cost(self) -> float:
        return sum(q.cost_usd for q in self.queries)

    @property
    def total_tokens(self) -> int:
        return sum(q.total_tokens for q in self.queries)

    @property
    def total_calls(self) -> int:
        return len(self.queries)

    def summary(self) -> dict:
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "by_provider": self._by_provider(),
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

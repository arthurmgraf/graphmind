from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class QueryMetric:
    question: str
    latency_ms: float
    eval_score: float
    retry_count: int
    sources_used: int
    provider: str
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    def __init__(self, max_history: int = 1000):
        self._history: deque[QueryMetric] = deque(maxlen=max_history)

    def record(self, metric: QueryMetric) -> None:
        self._history.append(metric)

    @property
    def total_queries(self) -> int:
        return len(self._history)

    @property
    def avg_latency_ms(self) -> float:
        if not self._history:
            return 0.0
        return sum(m.latency_ms for m in self._history) / len(self._history)

    @property
    def avg_eval_score(self) -> float:
        if not self._history:
            return 0.0
        return sum(m.eval_score for m in self._history) / len(self._history)

    @property
    def retry_rate(self) -> float:
        if not self._history:
            return 0.0
        retried = sum(1 for m in self._history if m.retry_count > 0)
        return retried / len(self._history)

    def p95_latency_ms(self) -> float:
        if not self._history:
            return 0.0
        latencies = sorted(m.latency_ms for m in self._history)
        idx = int(len(latencies) * 0.95)
        return latencies[min(idx, len(latencies) - 1)]

    def summary(self) -> dict:
        return {
            "total_queries": self.total_queries,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms(), 1),
            "avg_eval_score": round(self.avg_eval_score, 3),
            "retry_rate": round(self.retry_rate, 3),
        }

    def recent(self, n: int = 10) -> list[dict]:
        items = list(self._history)[-n:]
        return [
            {
                "question": m.question[:80],
                "latency_ms": round(m.latency_ms, 1),
                "eval_score": round(m.eval_score, 3),
                "retry_count": m.retry_count,
                "provider": m.provider,
            }
            for m in reversed(items)
        ]


_collector = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _collector

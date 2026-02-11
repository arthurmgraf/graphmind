"""A/B testing experiment registry for prompt and model variants."""
from __future__ import annotations
import structlog
import random
import time
from dataclasses import dataclass, field
from typing import Any

logger = structlog.get_logger(__name__)

@dataclass
class ExperimentVariant:
    name: str
    traffic_percentage: float
    config: dict[str, Any] = field(default_factory=dict)

@dataclass
class ExperimentResult:
    variant: str
    eval_score: float = 0.0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class Experiment:
    id: str
    name: str
    description: str = ""
    active: bool = True
    variants: list[ExperimentVariant] = field(default_factory=list)
    results: list[ExperimentResult] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def assign_variant(self, tenant_id: str | None = None) -> ExperimentVariant | None:
        if not self.active or not self.variants:
            return None
        if tenant_id:
            seed = hash(f"{self.id}:{tenant_id}") % 100
        else:
            seed = random.randint(0, 99)
        cumulative = 0.0
        for variant in self.variants:
            cumulative += variant.traffic_percentage
            if seed < cumulative:
                return variant
        return self.variants[-1]

    def record_result(self, result: ExperimentResult) -> None:
        self.results.append(result)

    def summary(self) -> dict[str, Any]:
        variant_stats: dict[str, dict] = {}
        for variant in self.variants:
            vr = [r for r in self.results if r.variant == variant.name]
            if vr:
                variant_stats[variant.name] = {
                    "count": len(vr),
                    "avg_eval_score": sum(r.eval_score for r in vr) / len(vr),
                    "avg_latency_ms": sum(r.latency_ms for r in vr) / len(vr),
                    "avg_cost_usd": sum(r.cost_usd for r in vr) / len(vr),
                }
            else:
                variant_stats[variant.name] = {"count": 0}
        return {"id": self.id, "name": self.name, "active": self.active, "variants": variant_stats}

class ExperimentRegistry:
    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}

    def create(self, experiment: Experiment) -> None:
        self._experiments[experiment.id] = experiment

    def get(self, experiment_id: str) -> Experiment | None:
        return self._experiments.get(experiment_id)

    def list_active(self) -> list[Experiment]:
        return [e for e in self._experiments.values() if e.active]

    def deactivate(self, experiment_id: str) -> bool:
        exp = self._experiments.get(experiment_id)
        if exp:
            exp.active = False
            return True
        return False

_registry: ExperimentRegistry | None = None

def get_experiment_registry() -> ExperimentRegistry:
    global _registry
    if _registry is None:
        _registry = ExperimentRegistry()
    return _registry

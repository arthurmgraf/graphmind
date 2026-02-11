"""Feature flag system for gradual rollouts and feature gating."""
from __future__ import annotations
import structlog
import random
from dataclasses import dataclass, field
from graphmind.config import get_settings

logger = structlog.get_logger(__name__)

@dataclass
class FeatureFlag:
    name: str
    enabled: bool = False
    rollout_percentage: float = 100.0
    description: str = ""

    def is_active(self, tenant_id: str | None = None) -> bool:
        if not self.enabled:
            return False
        if self.rollout_percentage >= 100.0:
            return True
        if tenant_id:
            seed = hash(f"{self.name}:{tenant_id}") % 100
            return seed < self.rollout_percentage
        return random.random() * 100 < self.rollout_percentage

class FeatureFlagRegistry:
    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            FeatureFlag("streaming_enabled", True, 100.0, "Enable SSE streaming responses"),
            FeatureFlag("crewai_enabled", True, 100.0, "Enable CrewAI engine option"),
            FeatureFlag("dedup_enabled", True, 100.0, "Enable content-hash deduplication"),
            FeatureFlag("webhooks_enabled", False, 0.0, "Enable webhook notifications"),
            FeatureFlag("multi_tenancy_enabled", False, 0.0, "Enable multi-tenant isolation"),
            FeatureFlag("conversation_memory_enabled", False, 0.0, "Enable session-based conversation memory"),
            FeatureFlag("injection_detection_enabled", True, 100.0, "Enable prompt injection detection"),
            FeatureFlag("chaos_enabled", False, 0.0, "Enable chaos engineering fault injection"),
        ]
        for flag in defaults:
            self._flags[flag.name] = flag

    def is_active(self, name: str, tenant_id: str | None = None) -> bool:
        flag = self._flags.get(name)
        if flag is None:
            logger.warning("Unknown feature flag: %s", name)
            return False
        return flag.is_active(tenant_id)

    def register(self, flag: FeatureFlag) -> None:
        self._flags[flag.name] = flag

    def set_enabled(self, name: str, enabled: bool) -> None:
        if name in self._flags:
            self._flags[name].enabled = enabled

    def list_flags(self) -> list[dict]:
        return [
            {"name": f.name, "enabled": f.enabled, "rollout_percentage": f.rollout_percentage, "description": f.description}
            for f in self._flags.values()
        ]

_registry: FeatureFlagRegistry | None = None

def get_feature_flags() -> FeatureFlagRegistry:
    global _registry
    if _registry is None:
        _registry = FeatureFlagRegistry()
    return _registry

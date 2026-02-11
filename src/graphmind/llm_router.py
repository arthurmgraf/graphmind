"""Multi-provider LLM router with circuit breaker and cascading fallback.

Supports three providers: Groq → Gemini → Ollama.  Each provider has an
independent circuit breaker with CLOSED → OPEN → HALF_OPEN state machine.
"""

from __future__ import annotations

import enum
import structlog
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, AsyncIterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from graphmind.config import Settings, get_settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker with half-open state
# ---------------------------------------------------------------------------

class CircuitPhase(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitState:
    failures: int = 0
    last_failure: float = 0.0
    open_until: float = 0.0
    max_failures: int = 5
    _phase: CircuitPhase = CircuitPhase.CLOSED

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        if self.failures >= self.max_failures:
            backoff = min(2 ** (self.failures - self.max_failures + 1), 60)
            self.open_until = self.last_failure + backoff
            self._phase = CircuitPhase.OPEN

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0
        self._phase = CircuitPhase.CLOSED

    @property
    def phase(self) -> CircuitPhase:
        if self._phase == CircuitPhase.OPEN:
            if time.monotonic() >= self.open_until:
                self._phase = CircuitPhase.HALF_OPEN
        return self._phase

    @property
    def is_available(self) -> bool:
        p = self.phase
        return p in (CircuitPhase.CLOSED, CircuitPhase.HALF_OPEN)


# ---------------------------------------------------------------------------
# Provider metrics
# ---------------------------------------------------------------------------

@dataclass
class ProviderMetrics:
    calls: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    last_used: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        successful = self.calls - self.failures
        return self.total_latency_ms / successful if successful > 0 else 0.0

    @property
    def failure_rate(self) -> float:
        return self.failures / self.calls if self.calls > 0 else 0.0


@dataclass
class RouterMetrics:
    by_provider: dict[str, ProviderMetrics] = field(default_factory=dict)

    def record(self, provider: str, latency_ms: float, success: bool) -> None:
        if provider not in self.by_provider:
            self.by_provider[provider] = ProviderMetrics()
        m = self.by_provider[provider]
        m.calls += 1
        m.last_used = time.time()
        if success:
            m.total_latency_ms += latency_ms
        else:
            m.failures += 1

    def summary(self) -> dict[str, Any]:
        return {
            name: {
                "calls": m.calls,
                "failures": m.failures,
                "failure_rate": round(m.failure_rate, 3),
                "avg_latency_ms": round(m.avg_latency_ms, 1),
            }
            for name, m in self.by_provider.items()
        }


# ---------------------------------------------------------------------------
# Provider builders
# ---------------------------------------------------------------------------

def _build_groq(settings: Settings) -> BaseChatModel:
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.llm_primary.model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_primary.temperature,
        max_tokens=settings.llm_primary.max_tokens,
    )


def _build_gemini(settings: Settings) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.llm_secondary.model,
        google_api_key=settings.gemini_api_key,
        temperature=settings.llm_secondary.temperature,
        max_output_tokens=settings.llm_secondary.max_tokens,
    )


def _build_ollama(settings: Settings) -> BaseChatModel:
    from langchain_community.chat_models import ChatOllama

    return ChatOllama(
        base_url=settings.llm_fallback.base_url or settings.ollama_base_url,
        model=settings.llm_fallback.model,
        temperature=settings.llm_fallback.temperature,
    )


_PROVIDERS: list[tuple[str, Any]] = [
    ("groq", _build_groq),
    ("gemini", _build_gemini),
    ("ollama", _build_ollama),
]


class LLMRouter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache: dict[str, BaseChatModel] = {}
        self._circuits: dict[str, CircuitState] = {
            name: CircuitState() for name, _ in _PROVIDERS
        }
        self.metrics = RouterMetrics()

    def _get_llm(self, name: str, builder: Any) -> BaseChatModel:
        if name not in self._cache:
            self._cache[name] = builder(self._settings)
        return self._cache[name]

    @property
    def circuit_states(self) -> dict[str, str]:
        return {name: cs.phase.value for name, cs in self._circuits.items()}

    async def ainvoke(
        self, messages: list[BaseMessage], **kwargs: Any
    ) -> BaseMessage:
        last_error: Exception | None = None
        provider_used: str = ""

        for name, builder in _PROVIDERS:
            circuit = self._circuits[name]
            if not circuit.is_available:
                logger.debug("Circuit %s for %s, skipping", circuit.phase.value, name)
                continue

            is_probe = circuit.phase == CircuitPhase.HALF_OPEN

            t0 = time.perf_counter()
            try:
                llm = self._get_llm(name, builder)
                response = await llm.ainvoke(messages, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_success()
                self.metrics.record(name, elapsed, success=True)
                provider_used = name
                if is_probe:
                    logger.info("Half-open probe succeeded for %s, circuit closed", name)
                logger.info("LLM response via %s (%.0f ms)", name, elapsed)
                if not hasattr(response, "response_metadata"):
                    response.response_metadata = {}
                response.response_metadata["provider"] = provider_used
                return response
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_failure()
                self.metrics.record(name, elapsed, success=False)
                if is_probe:
                    logger.warning("Half-open probe failed for %s, circuit re-opened", name)
                logger.warning(
                    "Provider %s failed after %.0f ms: %s", name, elapsed, exc,
                )
                last_error = exc
                continue

        raise RuntimeError(
            f"All LLM providers exhausted. Last error: {last_error}"
        )

    async def astream(
        self, messages: list[BaseMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream tokens from the first available provider."""
        last_error: Exception | None = None

        for name, builder in _PROVIDERS:
            circuit = self._circuits[name]
            if not circuit.is_available:
                continue

            t0 = time.perf_counter()
            try:
                llm = self._get_llm(name, builder)
                async for chunk in llm.astream(messages, **kwargs):
                    if hasattr(chunk, "content"):
                        yield chunk.content
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_success()
                self.metrics.record(name, elapsed, success=True)
                return
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_failure()
                self.metrics.record(name, elapsed, success=False)
                last_error = exc
                continue

        raise RuntimeError(
            f"All LLM providers exhausted (streaming). Last error: {last_error}"
        )

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> BaseMessage:
        last_error: Exception | None = None

        for name, builder in _PROVIDERS:
            circuit = self._circuits[name]
            if not circuit.is_available:
                continue

            t0 = time.perf_counter()
            try:
                llm = self._get_llm(name, builder)
                response = llm.invoke(messages, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_success()
                self.metrics.record(name, elapsed, success=True)
                logger.info("LLM response via %s (%.0f ms)", name, elapsed)
                if not hasattr(response, "response_metadata"):
                    response.response_metadata = {}
                response.response_metadata["provider"] = name
                return response
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_failure()
                self.metrics.record(name, elapsed, success=False)
                logger.warning(
                    "Provider %s failed after %.0f ms: %s", name, elapsed, exc,
                )
                last_error = exc
                continue

        raise RuntimeError(
            f"All LLM providers exhausted. Last error: {last_error}"
        )

    def get_primary(self) -> BaseChatModel:
        return self._get_llm("groq", _build_groq)

    def get_secondary(self) -> BaseChatModel:
        return self._get_llm("gemini", _build_gemini)

    def get_fallback(self) -> BaseChatModel:
        return self._get_llm("ollama", _build_ollama)


@lru_cache
def get_llm_router() -> LLMRouter:
    """Singleton LLM router (thread-safe via lru_cache)."""
    return LLMRouter()

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from graphmind.config import Settings, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit breaker: prevents hammering a provider that is consistently failing
# ---------------------------------------------------------------------------

@dataclass
class _CircuitState:
    failures: int = 0
    last_failure: float = 0.0
    open_until: float = 0.0

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure = time.monotonic()
        backoff = min(2 ** self.failures, 60)  # cap at 60 s
        self.open_until = self.last_failure + backoff

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    @property
    def is_open(self) -> bool:
        if self.open_until == 0.0:
            return False
        return time.monotonic() < self.open_until


# ---------------------------------------------------------------------------
# Provider metrics: tracks success / failure / latency per provider
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
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._cache: dict[str, BaseChatModel] = {}
        self._circuits: dict[str, _CircuitState] = {
            name: _CircuitState() for name, _ in _PROVIDERS
        }
        self.metrics = RouterMetrics()

    def _get_llm(self, name: str, builder: Any) -> BaseChatModel:
        if name not in self._cache:
            self._cache[name] = builder(self._settings)
        return self._cache[name]

    async def ainvoke(
        self, messages: list[BaseMessage], **kwargs: Any
    ) -> BaseMessage:
        last_error: Exception | None = None
        provider_used: str = ""

        for name, builder in _PROVIDERS:
            circuit = self._circuits[name]
            if circuit.is_open:
                logger.debug("Circuit open for %s, skipping", name)
                continue

            t0 = time.perf_counter()
            try:
                llm = self._get_llm(name, builder)
                response = await llm.ainvoke(messages, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_success()
                self.metrics.record(name, elapsed, success=True)
                provider_used = name
                logger.info(
                    "LLM response via %s (%.0f ms)", name, elapsed
                )
                # Attach provider metadata for downstream cost tracking
                if not hasattr(response, "response_metadata"):
                    response.response_metadata = {}
                response.response_metadata["provider"] = provider_used
                return response
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                circuit.record_failure()
                self.metrics.record(name, elapsed, success=False)
                logger.warning(
                    "Provider %s failed after %.0f ms: %s", name, elapsed, exc
                )
                last_error = exc
                continue

        raise RuntimeError(
            f"All LLM providers exhausted. Last error: {last_error}"
        )

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> BaseMessage:
        last_error: Exception | None = None

        for name, builder in _PROVIDERS:
            circuit = self._circuits[name]
            if circuit.is_open:
                logger.debug("Circuit open for %s, skipping", name)
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
                    "Provider %s failed after %.0f ms: %s", name, elapsed, exc
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


_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router

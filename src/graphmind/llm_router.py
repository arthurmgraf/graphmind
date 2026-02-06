from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from graphmind.config import Settings, get_settings

logger = logging.getLogger(__name__)


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

    def _get_llm(self, name: str, builder: Any) -> BaseChatModel:
        if name not in self._cache:
            self._cache[name] = builder(self._settings)
        return self._cache[name]

    async def ainvoke(self, messages: list[BaseMessage], **kwargs: Any) -> BaseMessage:
        last_error: Exception | None = None
        for name, builder in _PROVIDERS:
            try:
                llm = self._get_llm(name, builder)
                response = await llm.ainvoke(messages, **kwargs)
                logger.info("LLM response via %s", name)
                return response
            except Exception as exc:
                logger.warning("Provider %s failed: %s", name, exc)
                last_error = exc
                continue
        raise RuntimeError(f"All LLM providers exhausted. Last error: {last_error}")

    def invoke(self, messages: list[BaseMessage], **kwargs: Any) -> BaseMessage:
        last_error: Exception | None = None
        for name, builder in _PROVIDERS:
            try:
                llm = self._get_llm(name, builder)
                response = llm.invoke(messages, **kwargs)
                logger.info("LLM response via %s", name)
                return response
            except Exception as exc:
                logger.warning("Provider %s failed: %s", name, exc)
                last_error = exc
                continue
        raise RuntimeError(f"All LLM providers exhausted. Last error: {last_error}")

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

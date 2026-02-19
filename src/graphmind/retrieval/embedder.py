"""Ollama embedding client with retry, caching, and batch backpressure."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import OrderedDict

import httpx

from graphmind.config import Settings, get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_CACHE_MAX_SIZE = 2048
_BATCH_SIZE = 32


class Embedder:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._model = self._settings.embeddings.model
        self._dimensions = self._settings.embeddings.dimensions
        self._base_url = self._settings.embeddings.base_url.rstrip("/")
        self._external_client = http_client
        self._own_client: httpx.AsyncClient | None = None
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None and not self._external_client.is_closed:
            return self._external_client
        if self._own_client is None or self._own_client.is_closed:
            self._own_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._own_client

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    async def _post_with_retry(self, payload: dict) -> dict:
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_error = exc
                wait = _BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "Embedding request failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(f"Embedding request failed after {_MAX_RETRIES} attempts: {last_error}")

    async def embed(self, text: str) -> list[float]:
        key = self._cache_key(text)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        data = await self._post_with_retry({"model": self._model, "input": text})
        vector = data["embeddings"][0]

        if len(vector) != self._dimensions:
            raise ValueError(f"Dimension mismatch: expected {self._dimensions}, got {len(vector)}")

        self._cache[key] = vector
        if len(self._cache) > _CACHE_MAX_SIZE:
            self._cache.popitem(last=False)

        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts with backpressure (sub-batches of _BATCH_SIZE)."""
        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                self._cache.move_to_end(key)
                results[i] = self._cache[key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            total_batches = (len(uncached_texts) + _BATCH_SIZE - 1) // _BATCH_SIZE

            for batch_num in range(total_batches):
                start = batch_num * _BATCH_SIZE
                end = min(start + _BATCH_SIZE, len(uncached_texts))
                batch_texts = uncached_texts[start:end]
                batch_indices = uncached_indices[start:end]

                logger.info(
                    "Embedding batch %d/%d (%d/%d chunks)",
                    batch_num + 1,
                    total_batches,
                    end,
                    len(uncached_texts),
                )

                data = await self._post_with_retry({"model": self._model, "input": batch_texts})
                embeddings = data["embeddings"]

                for j, idx in enumerate(batch_indices):
                    vector = embeddings[j]
                    results[idx] = vector
                    key = self._cache_key(batch_texts[j])
                    self._cache[key] = vector
                    if len(self._cache) > _CACHE_MAX_SIZE:
                        self._cache.popitem(last=False)

                # Yield control between batches
                if batch_num < total_batches - 1:
                    await asyncio.sleep(0)

        return results  # type: ignore[return-value]

    async def close(self) -> None:
        if self._own_client is not None and not self._own_client.is_closed:
            await self._own_client.aclose()
            self._own_client = None

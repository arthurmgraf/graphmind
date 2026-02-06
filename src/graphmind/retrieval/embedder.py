from __future__ import annotations

import httpx

from graphmind.config import Settings, get_settings


class Embedder:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = self._settings.embeddings.model
        self._base_url = self._settings.embeddings.base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def embed(self, text: str) -> list[float]:
        client = await self._get_client()
        response = await client.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = await self._get_client()
        response = await client.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

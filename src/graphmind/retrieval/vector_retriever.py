from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from graphmind.config import Settings, get_settings
from graphmind.schemas import RetrievalResult


class VectorRetriever:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._collection = self._settings.vector_store.collection
        self._dimensions = self._settings.embeddings.dimensions
        self._client = AsyncQdrantClient(
            host=self._settings.vector_store.host,
            port=self._settings.vector_store.port,
        )

    async def ensure_collection(self) -> None:
        collections = await self._client.get_collections()
        existing_names = [c.name for c in collections.collections]
        if self._collection not in existing_names:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._dimensions,
                    distance=Distance.COSINE,
                ),
            )

    async def index(self, chunk_id: str, vector: list[float], payload: dict) -> None:
        if len(vector) != self._dimensions:
            raise ValueError(
                f"Vector dimension {len(vector)} != expected {self._dimensions}"
            )
        point = PointStruct(
            id=chunk_id,
            vector=vector,
            payload=payload,
        )
        await self._client.upsert(
            collection_name=self._collection,
            points=[point],
        )

    async def search(
        self, query_vector: list[float], limit: int = 20
    ) -> list[RetrievalResult]:
        hits = await self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=limit,
        )
        results: list[RetrievalResult] = []
        for hit in hits:
            results.append(
                RetrievalResult(
                    id=str(hit.id),
                    text=hit.payload.get("text", ""),
                    score=hit.score,
                    source="vector",
                    entity_id=hit.payload.get("entity_id"),
                    metadata=hit.payload,
                )
            )
        return results

    async def close(self) -> None:
        await self._client.close()

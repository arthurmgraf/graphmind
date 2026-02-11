"""Qdrant vector retriever with DI support for shared client."""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from graphmind.config import Settings, get_settings
from graphmind.schemas import RetrievalResult


class VectorRetriever:
    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._collection = self._settings.vector_store.collection
        self._dimensions = self._settings.embeddings.dimensions
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = AsyncQdrantClient(
                host=self._settings.vector_store.host,
                port=self._settings.vector_store.port,
            )
            self._owns_client = True

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
        self,
        query_vector: list[float],
        limit: int = 20,
        tenant_id: str | None = None,
    ) -> list[RetrievalResult]:
        query_filter = None
        if tenant_id:
            query_filter = Filter(
                must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
            )

        hits = await self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=limit,
            query_filter=query_filter,
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

    async def find_by_content_hash(self, content_hash: str) -> str | None:
        """Check if a document with the given content hash already exists."""
        results = await self._client.scroll(
            collection_name=self._collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="content_hash", match=MatchValue(value=content_hash))]
            ),
            limit=1,
        )
        points = results[0]
        if points:
            return points[0].payload.get("document_id", str(points[0].id))
        return None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

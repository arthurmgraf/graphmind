"""FastAPI dependency injection for GraphMind.

All shared resources (DB drivers, clients, routers) are created once in the
application lifespan and injected via ``Depends()`` into route handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

from graphmind.config import Settings, get_settings
from graphmind.llm_router import LLMRouter
from graphmind.observability.cost_tracker import CostTracker
from graphmind.observability.metrics import MetricsCollector
from graphmind.retrieval.embedder import Embedder
from graphmind.retrieval.graph_retriever import GraphRetriever
from graphmind.retrieval.hybrid_retriever import HybridRetriever
from graphmind.retrieval.vector_retriever import VectorRetriever

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Resource container — holds all shared, long-lived resources
# ---------------------------------------------------------------------------


@dataclass
class Resources:
    """Container for application-level shared resources."""

    settings: Settings = field(default_factory=get_settings)
    neo4j_driver: AsyncDriver | None = None
    qdrant_client: AsyncQdrantClient | None = None
    http_client: httpx.AsyncClient | None = None
    llm_router: LLMRouter | None = None
    embedder: Embedder | None = None
    vector_retriever: VectorRetriever | None = None
    graph_retriever: GraphRetriever | None = None
    hybrid_retriever: HybridRetriever | None = None
    cost_tracker: CostTracker = field(default_factory=CostTracker)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)

    async def startup(self) -> None:
        """Create and warm up all shared connections."""
        s = self.settings
        logger.info("Initialising shared resources")

        # Neo4j connection pool
        self.neo4j_driver = AsyncGraphDatabase.driver(
            s.neo4j_uri,
            auth=(s.neo4j_username, s.neo4j_password),
            max_connection_pool_size=50,
        )

        # Qdrant client
        self.qdrant_client = AsyncQdrantClient(
            host=s.qdrant_host,
            port=s.qdrant_port,
        )

        # Shared HTTP client for Ollama embeddings
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

        # LLM router
        self.llm_router = LLMRouter(settings=s)

        # Embedder (reuses shared http_client)
        self.embedder = Embedder(settings=s, http_client=self.http_client)

        # Retrievers
        self.vector_retriever = VectorRetriever(
            settings=s,
            client=self.qdrant_client,
        )
        self.graph_retriever = GraphRetriever(
            settings=s,
            driver=self.neo4j_driver,
        )
        self.hybrid_retriever = HybridRetriever(
            vector_retriever=self.vector_retriever,
            graph_retriever=self.graph_retriever,
            embedder=self.embedder,
            settings=s,
        )

        logger.info("All shared resources initialised")

    async def shutdown(self) -> None:
        """Close all connections and flush pending data."""
        logger.info("Shutting down shared resources")

        from graphmind.observability.langfuse_client import flush as langfuse_flush

        langfuse_flush()

        if self.embedder is not None:
            await self.embedder.close()
        if self.http_client is not None and not self.http_client.is_closed:
            await self.http_client.aclose()
        if self.qdrant_client is not None:
            await self.qdrant_client.close()
        if self.neo4j_driver is not None:
            await self.neo4j_driver.close()

        logger.info("All shared resources released")


# ---------------------------------------------------------------------------
# Module-level holder — set by the app lifespan
# ---------------------------------------------------------------------------

_resources: Resources | None = None


def set_resources(r: Resources) -> None:
    global _resources
    _resources = r


def get_resources() -> Resources:
    if _resources is None:
        raise RuntimeError(
            "Resources not initialised. Call set_resources() during application startup."
        )
    return _resources


# ---------------------------------------------------------------------------
# FastAPI Depends() helpers
# ---------------------------------------------------------------------------


def get_llm_router_dep() -> LLMRouter:
    return get_resources().llm_router  # type: ignore[return-value]


def get_hybrid_retriever_dep() -> HybridRetriever:
    return get_resources().hybrid_retriever  # type: ignore[return-value]


def get_cost_tracker_dep() -> CostTracker:
    return get_resources().cost_tracker


def get_metrics_dep() -> MetricsCollector:
    return get_resources().metrics


def get_neo4j_driver_dep() -> AsyncDriver:
    return get_resources().neo4j_driver  # type: ignore[return-value]


def get_qdrant_client_dep() -> AsyncQdrantClient:
    return get_resources().qdrant_client  # type: ignore[return-value]


def get_settings_dep() -> Settings:
    return get_resources().settings

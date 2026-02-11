"""Health check and graph stats endpoints with DI and circuit state reporting."""

from __future__ import annotations

import structlog
import time

import httpx
from fastapi import APIRouter, Request

from graphmind.config import get_settings
from graphmind.knowledge.graph_builder import GraphBuilder
from graphmind.schemas import GraphStats, HealthResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_CACHE_TTL = 15.0
_cached_result: HealthResponse | None = None
_cached_at: float = 0.0


async def _check_neo4j(request: Request) -> str:
    resources = request.app.state.resources
    driver = resources.neo4j_driver
    if driver is None:
        return "not configured"
    try:
        async with driver.session() as session:
            await session.run("RETURN 1")
        return "healthy"
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return f"unhealthy: {exc}"


async def _check_qdrant(request: Request) -> str:
    resources = request.app.state.resources
    client = resources.qdrant_client
    if client is None:
        return "not configured"
    try:
        await client.get_collections()
        return "healthy"
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)
        return f"unhealthy: {exc}"


async def _check_ollama() -> str:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            response.raise_for_status()
        return "healthy"
    except Exception as exc:
        logger.warning("Ollama health check failed: %s", exc)
        return f"unhealthy: {exc}"


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    global _cached_result, _cached_at

    now = time.monotonic()
    if _cached_result is not None and (now - _cached_at) < _CACHE_TTL:
        return _cached_result

    logger.info("Running health checks")

    services: dict[str, str] = {}
    services["neo4j"] = await _check_neo4j(request)
    services["qdrant"] = await _check_qdrant(request)
    services["ollama"] = await _check_ollama()

    all_healthy = all(v == "healthy" for v in services.values())
    status = "ok" if all_healthy else "degraded"

    # Get circuit breaker states from the LLM router
    circuits: dict[str, str] = {}
    resources = request.app.state.resources
    if resources.llm_router is not None:
        circuits = resources.llm_router.circuit_states

    result = HealthResponse(
        status=status,
        version="0.2.0",
        services=services,
        circuits=circuits,
    )

    _cached_result = result
    _cached_at = now

    logger.info("Health check completed: %s", status)
    return result


@router.get("/stats", response_model=GraphStats)
async def graph_stats(request: Request) -> GraphStats:
    logger.info("Fetching graph statistics")

    try:
        resources = request.app.state.resources
        driver = resources.neo4j_driver
        async with GraphBuilder(driver=driver) as builder:
            stats = await builder.get_stats()
    except Exception:
        logger.exception("Failed to retrieve graph statistics")
        return GraphStats()

    logger.info(
        "Graph stats: %d entities, %d relations",
        stats.total_entities,
        stats.total_relations,
    )
    return stats

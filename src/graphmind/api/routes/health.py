from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

from graphmind.config import get_settings
from graphmind.knowledge.graph_builder import GraphBuilder
from graphmind.schemas import GraphStats, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


async def _check_neo4j() -> str:
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        async with driver.session() as session:
            await session.run("RETURN 1")
        return "healthy"
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return f"unhealthy: {exc}"
    finally:
        await driver.close()


async def _check_qdrant() -> str:
    settings = get_settings()
    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    try:
        await client.get_collections()
        return "healthy"
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)
        return f"unhealthy: {exc}"
    finally:
        await client.close()


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
async def health_check() -> HealthResponse:
    logger.info("Running health checks")

    services: dict[str, str] = {}

    services["neo4j"] = await _check_neo4j()
    services["qdrant"] = await _check_qdrant()
    services["ollama"] = await _check_ollama()

    all_healthy = all(v == "healthy" for v in services.values())
    status = "ok" if all_healthy else "degraded"

    logger.info("Health check completed: %s", status)
    return HealthResponse(
        status=status,
        version="0.1.0",
        services=services,
    )


@router.get("/stats", response_model=GraphStats)
async def graph_stats() -> GraphStats:
    logger.info("Fetching graph statistics")

    try:
        async with GraphBuilder() as builder:
            stats = await builder.get_stats()
    except Exception as exc:
        logger.exception("Failed to retrieve graph statistics")
        return GraphStats()

    logger.info(
        "Graph stats: %d entities, %d relations",
        stats.total_entities,
        stats.total_relations,
    )
    return stats

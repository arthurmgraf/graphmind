from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from typing import Any

import httpx
import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)
from neo4j import AsyncGraphDatabase
from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient

from graphmind.agents.orchestrator import run_query
from graphmind.config import Settings, get_settings
from graphmind.ingestion.pipeline import IngestionPipeline
from graphmind.knowledge.graph_builder import GraphBuilder
from graphmind.safety.injection_detector import InjectionDetector
from graphmind.schemas import (
    Citation,
    GraphStats,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)

logger = structlog.get_logger(__name__)

server = Server("graphmind")
_injection_detector = InjectionDetector()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query",
            description=(
                "Ask a question to GraphMind's agentic RAG pipeline. "
                "Performs hybrid vector + graph retrieval with self-evaluation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": (
                            "Natural language question that may require multi-hop reasoning"
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of retrieval results to consider",
                        "default": 10,
                    },
                    "engine": {
                        "type": "string",
                        "description": "Orchestration engine: 'langgraph' or 'crewai'",
                        "default": "langgraph",
                        "enum": ["langgraph", "crewai"],
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="ingest",
            description=(
                "Ingest a document into the knowledge base. "
                "Chunks the content, generates embeddings, and extracts entities and relations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Full text content of the document to ingest",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Original filename of the document",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "Document format",
                        "default": "md",
                    },
                },
                "required": ["content", "filename"],
            },
        ),
        Tool(
            name="graph_stats",
            description=(
                "Return statistics about the knowledge graph including "
                "entity counts, relation counts, and type distributions."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="health",
            description=(
                "Check the health of all GraphMind backend services "
                "(Neo4j, Qdrant, Ollama) and report their status."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> Sequence[TextContent]:
    arguments = arguments or {}

    try:
        if name == "query":
            return await _handle_query(arguments)
        if name == "ingest":
            return await _handle_ingest(arguments)
        if name == "graph_stats":
            return await _handle_graph_stats()
        if name == "health":
            return await _handle_health()
    except Exception:
        logger.exception("Tool '%s' failed", name)
        return [TextContent(type="text", text=json.dumps({"error": "Tool execution failed"}))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def _handle_query(arguments: dict[str, Any]) -> list[TextContent]:
    # Validate input via Pydantic (reuse REST schema)
    try:
        validated = QueryRequest(
            question=arguments.get("question", ""),
            top_k=arguments.get("top_k", 10),
            engine=arguments.get("engine", "langgraph"),
        )
    except ValidationError as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    # Injection detection (same safety layer as REST API)
    check_result = _injection_detector.detect(validated.question)
    if check_result.is_suspicious:
        logger.warning("MCP injection detected: patterns=%s", check_result.matched_patterns)
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "Potential prompt injection detected",
                        "patterns": check_result.matched_patterns,
                    }
                ),
            )
        ]

    logger.info(
        "MCP query tool invoked with question: %s (top_k=%d, engine=%s)",
        validated.question,
        validated.top_k,
        validated.engine,
    )

    result = await run_query(question=validated.question, engine=validated.engine)

    citations = [Citation(**c) if isinstance(c, dict) else c for c in result.get("citations", [])]

    response = QueryResponse(
        answer=result.get("generation", ""),
        citations=citations,
        eval_score=result.get("eval_score", 0.0),
        sources_used=len(citations),
        latency_ms=result.get("latency_ms", 0.0),
        cost_usd=0.0,
    )

    logger.info(
        "MCP query completed with score %.2f (%d sources)",
        response.eval_score,
        response.sources_used,
    )

    payload = {
        "answer": response.answer,
        "citations": [c.model_dump() for c in response.citations],
        "eval_score": response.eval_score,
    }
    return [TextContent(type="text", text=json.dumps(payload))]


async def _handle_ingest(arguments: dict[str, Any]) -> list[TextContent]:
    # Validate input via Pydantic (reuse REST schema)
    try:
        validated = IngestRequest(
            content=arguments.get("content", ""),
            filename=arguments.get("filename", ""),
            doc_type=arguments.get("doc_type", "md"),
        )
    except ValidationError as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    content = validated.content
    filename = validated.filename
    doc_type = validated.doc_type

    logger.info("MCP ingest tool invoked for file: %s (type=%s)", filename, doc_type)

    pipeline = IngestionPipeline()
    response: IngestResponse = await pipeline.process(
        content=content,
        filename=filename,
        doc_type=doc_type,
    )

    logger.info(
        "MCP ingest completed: %d chunks, %d entities, %d relations",
        response.chunks_created,
        response.entities_extracted,
        response.relations_extracted,
    )

    payload = {
        "document_id": response.document_id,
        "chunks_created": response.chunks_created,
        "entities_extracted": response.entities_extracted,
        "relations_extracted": response.relations_extracted,
    }
    return [TextContent(type="text", text=json.dumps(payload))]


async def _handle_graph_stats() -> list[TextContent]:
    logger.info("MCP graph_stats tool invoked")

    async with GraphBuilder() as builder:
        stats: GraphStats = await builder.get_stats()

    payload = stats.model_dump()

    logger.info(
        "MCP graph_stats: %d entities, %d relations",
        stats.total_entities,
        stats.total_relations,
    )

    return [TextContent(type="text", text=json.dumps(payload))]


async def _handle_health() -> list[TextContent]:
    logger.info("MCP health tool invoked")

    settings: Settings = get_settings()
    services: dict[str, str] = {}

    try:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        await driver.verify_connectivity()
        await driver.close()
        services["neo4j"] = "ok"
    except Exception as exc:
        logger.error("Neo4j health check failed: %s", exc)
        services["neo4j"] = "unhealthy"

    try:
        client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        await client.get_collections()
        await client.close()
        services["qdrant"] = "ok"
    except Exception as exc:
        logger.error("Qdrant health check failed: %s", exc)
        services["qdrant"] = "unhealthy"

    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            resp = await http_client.get(settings.ollama_base_url)
            resp.raise_for_status()
        services["ollama"] = "ok"
    except Exception as exc:
        logger.error("Ollama health check failed: %s", exc)
        services["ollama"] = "unhealthy"

    all_ok = all(v == "ok" for v in services.values())
    response = HealthResponse(
        status="ok" if all_ok else "degraded",
        version="0.1.0",
        services=services,
    )

    logger.info("MCP health: %s", response.status)

    return [TextContent(type="text", text=json.dumps(response.model_dump()))]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting GraphMind MCP server")

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())

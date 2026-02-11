"""Async ingestion worker powered by arq (Redis-based task queue)."""

from __future__ import annotations

import logging

from arq.connections import RedisSettings

from graphmind.config import get_settings
from graphmind.ingestion.pipeline import IngestionPipeline
from graphmind.retrieval.embedder import Embedder
from graphmind.retrieval.vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


async def ingest_document(
    ctx: dict,
    content: str,
    filename: str,
    doc_type: str = "markdown",
) -> dict:
    """Process a document through the ingestion pipeline.

    Args:
        ctx: arq worker context containing shared settings.
        content: Raw document content to ingest.
        filename: Original filename of the document.
        doc_type: Document type (default ``"markdown"``).

    Returns:
        Dictionary with ingestion results including document_id,
        chunks_created, entities_extracted, and relations_extracted.
    """
    settings = ctx["settings"]
    embedder = Embedder(settings=settings)
    try:
        vector_retriever = VectorRetriever(settings=settings)
        pipeline = IngestionPipeline(
            embedder=embedder,
            vector_retriever=vector_retriever,
        )
        response = await pipeline.process(
            content=content,
            filename=filename,
            doc_type=doc_type,
        )
        return {
            "document_id": response.document_id,
            "chunks_created": response.chunks_created,
            "entities_extracted": response.entities_extracted,
            "relations_extracted": response.relations_extracted,
        }
    finally:
        await embedder.close()


async def startup(ctx: dict) -> None:
    """Store application settings in the worker context on startup."""
    ctx["settings"] = get_settings()
    logger.info("Ingest worker started")


async def shutdown(ctx: dict) -> None:
    """Graceful shutdown hook (no-op for now)."""
    pass


class WorkerSettings:
    """arq worker configuration."""

    functions = [ingest_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="localhost", port=6379)


def cli() -> None:
    """Console-script entry point to launch the arq worker."""
    import arq

    arq.run_worker(WorkerSettings)

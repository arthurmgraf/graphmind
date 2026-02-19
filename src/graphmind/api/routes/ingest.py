"""Ingest endpoint with content-hash deduplication."""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Request

from graphmind.errors import PipelineError, ValidationError
from graphmind.ingestion.pipeline import IngestionPipeline
from graphmind.observability.audit import AuditLogger
from graphmind.schemas import IngestRequest, IngestResponse

_audit = AuditLogger()

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/ingest", response_model=IngestResponse)
async def handle_ingest(request: IngestRequest, req: Request) -> IngestResponse:
    start = time.perf_counter()
    logger.info(
        "Received ingest request for file: %s (%d bytes)",
        request.filename,
        len(request.content),
    )

    if not request.content.strip():
        raise ValidationError("Content cannot be empty or whitespace-only")

    resources = req.app.state.resources

    # Content-hash deduplication check
    if resources.vector_retriever is not None:
        import hashlib

        content_hash = hashlib.sha256(request.content.encode("utf-8")).hexdigest()
        existing_id = await resources.vector_retriever.find_by_content_hash(content_hash)
        if existing_id:
            logger.info(
                "Duplicate document detected (hash=%s), returning existing ID",
                content_hash[:12],
            )
            return IngestResponse(
                document_id=existing_id,
                duplicate=True,
            )

    try:
        pipeline = IngestionPipeline(
            embedder=resources.embedder,
            vector_retriever=resources.vector_retriever,
        )
        response = await pipeline.process(
            content=request.content,
            filename=request.filename,
            doc_type=request.doc_type,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Ingestion failed for file: %s", request.filename)
        raise PipelineError(
            message=f"Ingestion pipeline failed: {exc}",
            details={"filename": request.filename},
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    client_ip = req.client.host if req.client else ""
    _audit.log_ingest(
        request_id=getattr(req.state, "request_id", ""),
        client_ip=client_ip,
        filename=request.filename,
        status=200,
        elapsed_ms=elapsed_ms,
    )

    logger.info(
        "Ingestion completed for %s: %d chunks, %d entities, %d relations",
        request.filename,
        response.chunks_created,
        response.entities_extracted,
        response.relations_extracted,
    )
    return response

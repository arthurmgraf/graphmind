from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from graphmind.ingestion.pipeline import IngestionPipeline
from graphmind.schemas import IngestRequest, IngestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/ingest", response_model=IngestResponse)
async def handle_ingest(request: IngestRequest) -> IngestResponse:
    logger.info("Received ingest request for file: %s (%d bytes)", request.filename, len(request.content))

    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty or whitespace-only")

    try:
        pipeline = IngestionPipeline()
        response = await pipeline.process(
            content=request.content,
            filename=request.filename,
            doc_type=request.doc_type,
        )
    except Exception as exc:
        logger.exception("Ingestion failed for file: %s", request.filename)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion pipeline failed: {exc}",
        ) from exc

    logger.info(
        "Ingestion completed for %s: %d chunks, %d entities, %d relations",
        request.filename,
        response.chunks_created,
        response.entities_extracted,
        response.relations_extracted,
    )
    return response

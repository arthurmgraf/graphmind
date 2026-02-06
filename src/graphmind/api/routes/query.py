from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from graphmind.agents.orchestrator import run_query
from graphmind.schemas import Citation, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest) -> QueryResponse:
    logger.info("Received query: %s", request.question)
    start = time.perf_counter()

    try:
        result = await run_query(question=request.question, engine=request.engine)
    except Exception as exc:
        logger.exception("Query pipeline failed for question: %s", request.question)
        raise HTTPException(
            status_code=500,
            detail=f"Query pipeline failed: {exc}",
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000

    citations = [
        Citation(**c) if isinstance(c, dict) else c
        for c in result.get("citations", [])
    ]

    response = QueryResponse(
        answer=result.get("generation", ""),
        citations=citations,
        eval_score=result.get("eval_score", 0.0),
        sources_used=len(citations),
        latency_ms=elapsed_ms,
        cost_usd=0.0,
    )

    logger.info(
        "Query completed in %.0fms with score %.2f",
        response.latency_ms,
        response.eval_score,
    )
    return response

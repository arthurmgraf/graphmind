from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

from graphmind.agents.orchestrator import run_query
from graphmind.observability.cost_tracker import get_cost_tracker
from graphmind.observability.langfuse_client import log_span, trace_query
from graphmind.observability.metrics import QueryMetric, get_metrics
from graphmind.schemas import Citation, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest) -> QueryResponse:
    logger.info("Received query: %s (engine=%s)", request.question, request.engine)
    start = time.perf_counter()

    with trace_query(request.question, metadata={"engine": request.engine}) as trace_data:
        try:
            log_span(trace_data, "orchestrator_start", input_data={"question": request.question})
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

        # --- cost tracking ---
        provider_used = result.get("provider_used", "groq")
        total_tokens = result.get("total_tokens", 0)
        cost_entry = get_cost_tracker().record(
            provider=provider_used,
            model=result.get("model", ""),
            input_tokens=int(total_tokens * 0.7),  # estimate split
            output_tokens=int(total_tokens * 0.3),
        )

        response = QueryResponse(
            answer=result.get("generation", ""),
            citations=citations,
            eval_score=result.get("eval_score", 0.0),
            sources_used=len(citations),
            latency_ms=elapsed_ms,
            cost_usd=cost_entry.cost_usd,
        )

        # --- metrics ---
        get_metrics().record(
            QueryMetric(
                question=request.question,
                latency_ms=elapsed_ms,
                eval_score=response.eval_score,
                retry_count=result.get("retry_count", 0),
                sources_used=response.sources_used,
                provider=provider_used,
            )
        )

        log_span(
            trace_data,
            "orchestrator_end",
            output_data={
                "eval_score": response.eval_score,
                "latency_ms": round(elapsed_ms, 1),
                "cost_usd": round(response.cost_usd, 6),
            },
        )
        trace_data["output"] = {
            "answer": response.answer[:200],
            "eval_score": response.eval_score,
        }

    logger.info(
        "Query completed in %.0fms with score %.2f (cost=$%.6f)",
        response.latency_ms,
        response.eval_score,
        response.cost_usd,
    )
    return response

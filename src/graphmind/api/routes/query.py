"""Query endpoint with SSE streaming, cost tracking, and experiment support."""

from __future__ import annotations

import json
import time

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from graphmind.agents.orchestrator import run_query
from graphmind.errors import InjectionDetectedError, PipelineError
from graphmind.features import FeatureFlagRegistry
from graphmind.retrieval.response_cache import ResponseCache
from graphmind.safety.injection_detector import InjectionDetector
from graphmind.schemas import Citation, QueryRequest, QueryResponse

_injection_detector = InjectionDetector()
_feature_flags = FeatureFlagRegistry()
_response_cache = ResponseCache()

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


@router.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest, req: Request) -> QueryResponse:
    logger.info("Received query: %s (engine=%s)", request.question, request.engine)
    start = time.perf_counter()

    # --- injection detection (pre-LLM guard) ---
    if _feature_flags.is_active("injection_detection_enabled"):
        result_check = _injection_detector.detect(request.question)
        if result_check.is_suspicious:
            logger.warning(
                "Injection detected in query: patterns=%s",
                result_check.matched_patterns,
            )
            raise InjectionDetectedError(
                message="Potential prompt injection detected",
                details={"matched_patterns": result_check.matched_patterns},
            )

    # --- response cache check ---
    cached = _response_cache.get(request.question, request.engine, request.top_k)
    if cached is not None:
        logger.info("cache_hit", question=request.question[:80])
        return QueryResponse(**cached)

    resources = req.app.state.resources
    cost_tracker = resources.cost_tracker
    metrics_collector = resources.metrics

    from graphmind.observability.langfuse_client import log_span, trace_query
    from graphmind.observability.metrics import QueryMetric

    with trace_query(request.question, metadata={"engine": request.engine}) as trace_data:
        try:
            log_span(trace_data, "orchestrator_start", input_data={"question": request.question})
            result = await run_query(
                question=request.question,
                engine=request.engine,
                retriever=resources.hybrid_retriever,
                router=resources.llm_router,
            )
        except Exception as exc:
            logger.exception("Query pipeline failed for question: %s", request.question)
            raise PipelineError(
                message=f"Query pipeline failed: {exc}",
                details={"question": request.question[:200]},
            ) from exc

        elapsed_ms = (time.perf_counter() - start) * 1000

        citations = [
            Citation(**c) if isinstance(c, dict) else c for c in result.get("citations", [])
        ]

        # --- cost tracking (extract actual tokens from LLM response metadata) ---
        provider_used = result.get("provider_used", "groq")
        usage = result.get("usage", {})
        input_tokens = (
            usage.get("prompt_tokens")
            or usage.get("prompt_eval_count")  # Ollama
            or usage.get("input_tokens")  # Gemini
            or result.get("input_tokens", 0)
        )
        output_tokens = (
            usage.get("completion_tokens")
            or usage.get("eval_count")  # Ollama
            or usage.get("output_tokens")  # Gemini
            or result.get("output_tokens", 0)
        )
        # Fallback: if metadata unavailable, estimate from total
        if not input_tokens and not output_tokens:
            total_tokens = result.get("total_tokens", 0)
            input_tokens = int(total_tokens * 0.7)
            output_tokens = int(total_tokens * 0.3)

        cost_entry = cost_tracker.record(
            provider=provider_used,
            model=result.get("model", ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        response = QueryResponse(
            answer=result.get("generation", ""),
            citations=citations,
            eval_score=result.get("eval_score", 0.0),
            sources_used=len(citations),
            latency_ms=elapsed_ms,
            cost_usd=cost_entry.cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            session_id=request.session_id,
        )

        # --- metrics ---
        metrics_collector.record(
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

    # --- cache the response ---
    _response_cache.put(
        request.question,
        response.model_dump(),
        request.engine,
        request.top_k,
    )

    logger.info(
        "Query completed in %.0fms with score %.2f (cost=$%.6f)",
        response.latency_ms,
        response.eval_score,
        response.cost_usd,
    )
    return response


@router.post("/query/stream")
async def handle_query_stream(request: QueryRequest, req: Request) -> StreamingResponse:
    """SSE streaming endpoint for real-time query responses."""
    resources = req.app.state.resources

    async def event_generator():
        try:
            yield _sse_event("planning", {"question": request.question})

            result = await run_query(
                question=request.question,
                engine=request.engine,
                retriever=resources.hybrid_retriever,
                router=resources.llm_router,
            )

            yield _sse_event(
                "retrieving",
                {
                    "sources_found": len(result.get("documents", [])),
                },
            )

            yield _sse_event(
                "generating",
                {
                    "answer": result.get("generation", ""),
                },
            )

            yield _sse_event(
                "evaluating",
                {
                    "eval_score": result.get("eval_score", 0.0),
                },
            )

            citations = [
                c if isinstance(c, dict) else c.model_dump() for c in result.get("citations", [])
            ]

            yield _sse_event(
                "done",
                {
                    "answer": result.get("generation", ""),
                    "citations": citations,
                    "eval_score": result.get("eval_score", 0.0),
                    "provider": result.get("provider_used", ""),
                },
            )

        except Exception as exc:
            logger.exception("Streaming query failed")
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

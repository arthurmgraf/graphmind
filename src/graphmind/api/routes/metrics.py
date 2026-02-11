"""Prometheus metrics endpoint for GraphMind API."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ---------------------------------------------------------------------------
# Prometheus metric definitions
# ---------------------------------------------------------------------------

REQUESTS_TOTAL = Counter(
    "graphmind_requests_total",
    "Total API requests",
    ["method", "path", "status"],
)

REQUEST_DURATION = Histogram(
    "graphmind_request_duration_seconds",
    "Request duration",
    ["method", "path"],
)

ACTIVE_REQUESTS = Gauge(
    "graphmind_active_requests",
    "Currently active requests",
)

QUERY_LATENCY = Histogram(
    "graphmind_query_latency_ms",
    "Query pipeline latency in ms",
    buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000],
)

CIRCUIT_STATE = Gauge(
    "graphmind_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["provider"],
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Expose all registered Prometheus metrics in the standard exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

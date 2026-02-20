"""GraphMind API application factory.

Creates a fully configured FastAPI application with:
- Proper lifespan management (startup/shutdown with resource cleanup)
- Request logging middleware with request_id propagation
- API key authentication middleware (optional)
- Sliding-window rate limiter with bounded memory
- Structured error handling
- CORS configuration
- Prometheus-compatible /metrics endpoint
"""

from __future__ import annotations

import time
import uuid as uuid_mod
from collections import OrderedDict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from graphmind.config import Settings, get_settings
from graphmind.dependencies import Resources, set_resources
from graphmind.errors import register_exception_handlers
from graphmind.observability.logging_config import configure_logging
from graphmind.security.auth import AuthMiddleware
from graphmind.security.rbac import RBACRegistry

logger = structlog.get_logger(__name__)

# Maximum number of unique client IPs tracked by the rate limiter
_RATE_LIMIT_MAX_CLIENTS = 10_000


# ---------------------------------------------------------------------------
# Lifespan — initialise shared resources on startup, release on shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    resources: Resources = app.state.resources
    settings = resources.settings

    json_logs = settings.is_production
    configure_logging(json_output=json_logs)

    logger.info(
        "GraphMind API starting (rate_limit=%d rpm, auth=%s)",
        settings.rate_limit_rpm,
        "enabled" if settings.api_key else "disabled",
    )

    await resources.startup()
    set_resources(resources)

    yield  # ---- application is running ----

    logger.info("GraphMind API shutting down — draining resources")
    await resources.shutdown()
    logger.info("GraphMind API shut down")


# ---------------------------------------------------------------------------
# Middleware — request logging
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get(
            "X-Request-ID",
            str(uuid_mod.uuid4())[:8],
        )
        # Store on request.state for downstream use (error handler, audit)
        request.state.request_id = request_id

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            "%s %s %d %.0fms request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Middleware — sliding-window rate limiter with bounded memory
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client-IP sliding-window rate limiter.

    Uses an ``OrderedDict`` bounded to ``max_clients`` entries so that memory
    usage stays predictable even under traffic from many unique IPs.
    """

    def __init__(self, app, rpm: int = 60, max_clients: int = _RATE_LIMIT_MAX_CLIENTS):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._rpm = rpm
        self._max_clients = max_clients
        self._window: OrderedDict[str, list[float]] = OrderedDict()

    def _evict_stale(self) -> None:
        """Remove oldest clients when we exceed max_clients."""
        while len(self._window) > self._max_clients:
            self._window.popitem(last=False)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if self._rpm <= 0:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        if client_ip in self._window:
            self._window.move_to_end(client_ip)
        else:
            self._window[client_ip] = []
            self._evict_stale()

        window = self._window[client_ip]

        # Purge timestamps older than 60 s
        window[:] = [t for t in window if now - t < 60]

        if len(window) >= self._rpm:
            return Response(
                content='{"error":{"code":"RATE_LIMIT_EXCEEDED","message":"Rate limit exceeded"}}',
                status_code=429,
                media_type="application/json",
            )

        window.append(now)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Middleware — request body size limit
# ---------------------------------------------------------------------------


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds a configurable limit."""

    def __init__(self, app, max_bytes: int = 15 * 1024 * 1024):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return Response(
                content=(
                    '{"error":{"code":"PAYLOAD_TOO_LARGE",'
                    '"message":"Request body exceeds size limit"}}'
                ),
                status_code=413,
                media_type="application/json",
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a fully configured FastAPI application.

    Parameters
    ----------
    settings:
        Optional settings override. If *None*, ``get_settings()`` is used.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="GraphMind API",
        description="Autonomous Knowledge Agent Platform",
        version="0.2.0",
        lifespan=_lifespan,
    )

    # Attach resources container to app.state (used by lifespan)
    app.state.resources = Resources(settings=settings)

    # --- Exception handlers (structured error responses) ---
    register_exception_handlers(app, debug=settings.debug)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # --- Middleware stack (order: outermost first) ---
    rbac_registry = RBACRegistry()
    app.state.rbac_registry = rbac_registry

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware, registry=rbac_registry)
    app.add_middleware(RateLimitMiddleware, rpm=settings.rate_limit_rpm)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=15 * 1024 * 1024)

    # --- OpenTelemetry (optional) ---
    otel_endpoint = getattr(settings, "otel_endpoint", None) or None
    try:
        from graphmind.observability.otel import setup_otel

        setup_otel(app, endpoint=otel_endpoint)
    except Exception:
        logger.debug("OpenTelemetry not configured or unavailable")

    # --- Routes ---
    from graphmind.api.routes.documents import router as documents_router
    from graphmind.api.routes.graph import router as graph_router
    from graphmind.api.routes.health import router as health_router
    from graphmind.api.routes.ingest import router as ingest_router
    from graphmind.api.routes.metrics import router as metrics_router
    from graphmind.api.routes.query import router as query_router

    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    app.include_router(metrics_router)
    app.include_router(graph_router)
    app.include_router(documents_router)

    return app


# ---------------------------------------------------------------------------
# Default application instance (used by uvicorn/gunicorn)
# ---------------------------------------------------------------------------

app = create_app()


def run() -> None:
    uvicorn.run("graphmind.api.main:app", host="0.0.0.0", port=8000, reload=True)

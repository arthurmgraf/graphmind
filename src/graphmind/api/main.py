from __future__ import annotations

import logging
import time
import uuid as uuid_mod
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from graphmind.api.routes.health import router as health_router
from graphmind.api.routes.ingest import router as ingest_router
from graphmind.api.routes.query import router as query_router
from graphmind.config import get_settings
from graphmind.observability.langfuse_client import flush as langfuse_flush

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: initialise shared resources on startup, release on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger.info(
        "GraphMind API starting up (rate_limit=%d rpm, auth=%s)",
        settings.rate_limit_rpm,
        "enabled" if settings.api_key else "disabled",
    )
    yield
    langfuse_flush()
    logger.info("GraphMind API shut down")


app = FastAPI(
    title="GraphMind API",
    description="Autonomous Knowledge Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS — configurable via settings
# ---------------------------------------------------------------------------

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid_mod.uuid4())[:8])
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


app.add_middleware(RequestLoggingMiddleware)


# ---------------------------------------------------------------------------
# API key authentication middleware (optional — enable by setting API_KEY)
# ---------------------------------------------------------------------------

class APIKeyMiddleware(BaseHTTPMiddleware):
    _PUBLIC_PATHS = {"/api/v1/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.api_key:
            return await call_next(request)

        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)

        provided = (
            request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        )
        if provided != settings.api_key:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)


# ---------------------------------------------------------------------------
# Sliding-window rate limiter (per-client IP, configurable RPM)
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rpm: int = 60):
        super().__init__(app)
        self._rpm = rpm
        self._window: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if self._rpm <= 0:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._window[client_ip]

        # Purge entries older than 60 s
        window[:] = [t for t in window if now - t < 60]

        if len(window) >= self._rpm:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        window.append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware, rpm=_settings.rate_limit_rpm)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)


def run() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)

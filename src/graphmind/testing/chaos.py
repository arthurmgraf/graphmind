"""Chaos engineering fault injection for staging environments."""

from __future__ import annotations

import asyncio
import logging
import random

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ChaosMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, error_rate: float = 0.0, latency_ms: int = 0, enabled: bool = False):
        super().__init__(app)
        self._error_rate = error_rate
        self._latency_ms = latency_ms
        self._enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)
        if self._latency_ms > 0:
            delay = random.uniform(0, self._latency_ms) / 1000
            logger.debug("Chaos: injecting %.0fms latency", delay * 1000)
            await asyncio.sleep(delay)
        if self._error_rate > 0 and random.random() < self._error_rate:
            logger.warning("Chaos: injecting 500 error")
            return Response(
                content=(
                    '{"error":{"code":"CHAOS_FAULT",'
                    '"message":"Injected failure for chaos testing"}}'
                ),
                status_code=500,
                media_type="application/json",
            )
        return await call_next(request)

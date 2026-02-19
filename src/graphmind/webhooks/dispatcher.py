"""Async webhook dispatcher with retry and HMAC verification."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class WebhookRegistration:
    id: str
    url: str
    events: list[str]
    secret: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class WebhookDelivery:
    webhook_id: str
    event: str
    status_code: int = 0
    success: bool = False
    attempts: int = 0
    error: str = ""
    delivered_at: float = field(default_factory=time.time)


class WebhookDispatcher:
    def __init__(self) -> None:
        self._registrations: dict[str, WebhookRegistration] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._max_retries = 3
        self._backoff_base = 1.0

    def register(self, registration: WebhookRegistration) -> None:
        self._registrations[registration.id] = registration
        logger.info("Webhook registered: %s -> %s", registration.id, registration.url)

    def unregister(self, webhook_id: str) -> bool:
        if webhook_id in self._registrations:
            del self._registrations[webhook_id]
            return True
        return False

    def _sign_payload(self, payload: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    async def dispatch(self, event: str, data: dict[str, Any]) -> list[WebhookDelivery]:
        matching = [r for r in self._registrations.values() if event in r.events]
        deliveries: list[WebhookDelivery] = []
        for reg in matching:
            delivery = await self._deliver(reg, event, data)
            deliveries.append(delivery)
            self._deliveries.append(delivery)
        return deliveries

    async def _deliver(
        self,
        reg: WebhookRegistration,
        event: str,
        data: dict[str, Any],
    ) -> WebhookDelivery:
        payload = json.dumps({"event": event, "data": data, "timestamp": time.time()}).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if reg.secret:
            headers["X-Webhook-Signature"] = self._sign_payload(payload, reg.secret)

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(reg.url, content=payload, headers=headers)
                if resp.status_code < 400:
                    return WebhookDelivery(
                        webhook_id=reg.id,
                        event=event,
                        status_code=resp.status_code,
                        success=True,
                        attempts=attempt + 1,
                    )
                if resp.status_code >= 500:
                    await asyncio.sleep(self._backoff_base * (2**attempt))
                    continue
                return WebhookDelivery(
                    webhook_id=reg.id,
                    event=event,
                    status_code=resp.status_code,
                    success=False,
                    attempts=attempt + 1,
                    error=f"HTTP {resp.status_code}",
                )
            except Exception as exc:
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._backoff_base * (2**attempt))
                    continue
                return WebhookDelivery(
                    webhook_id=reg.id,
                    event=event,
                    success=False,
                    attempts=attempt + 1,
                    error=str(exc),
                )
        return WebhookDelivery(
            webhook_id=reg.id,
            event=event,
            success=False,
            attempts=self._max_retries,
            error="max retries exceeded",
        )

    def get_deliveries(
        self,
        webhook_id: str | None = None,
        limit: int = 50,
    ) -> list[WebhookDelivery]:
        deliveries = self._deliveries
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        return deliveries[-limit:]


_dispatcher: WebhookDispatcher | None = None


def get_webhook_dispatcher() -> WebhookDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = WebhookDispatcher()
    return _dispatcher

"""RBAC-aware authentication middleware with timing-safe comparison."""

from __future__ import annotations

import hashlib
import hmac

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from graphmind.observability.audit import get_audit_logger
from graphmind.security.rbac import RBACRegistry, Role

logger = structlog.get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate requests via API key -> RBAC resolution.

    Supports two modes:
    1. RBAC mode: key hash looked up in RBACRegistry for role/tenant
    2. Legacy mode: key compared against settings.api_key (auto-registered as admin)

    Public paths bypass authentication entirely.
    """

    _PUBLIC_PATHS = {"/api/v1/health", "/openapi.json"}

    def __init__(self, app, registry: RBACRegistry):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._registry = registry

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        settings = request.app.state.resources.settings

        # No auth configured -> allow in dev/test, reject in production
        if not settings.api_key:
            if settings.is_production:
                logger.error("API_KEY not set in production — rejecting request")
                return self._unauthorized_response()
            request.state.role = Role.ADMIN
            request.state.tenant_id = "default"
            return await call_next(request)

        # Public paths skip auth
        if request.url.path in self._PUBLIC_PATHS:
            return await call_next(request)

        # Allow docs only in non-production
        if request.url.path in {"/docs", "/redoc"} and not settings.is_production:
            return await call_next(request)

        # Extract Bearer token
        provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not provided:
            self._log_auth_failure(request, "missing_key")
            return self._unauthorized_response()

        # Try RBAC registry first (hashed key lookup)
        key_hash = hashlib.sha256(provided.encode()).hexdigest()
        record = self._registry.resolve(key_hash)

        if record is not None:
            request.state.role = record.role
            request.state.tenant_id = record.tenant_id
            request.state.key_record = record
            return await call_next(request)

        # Legacy fallback: compare against settings.api_key (timing-safe)
        if hmac.compare_digest(provided.encode(), settings.api_key.encode()):
            request.state.role = Role.ADMIN
            request.state.tenant_id = "default"
            return await call_next(request)

        self._log_auth_failure(request, "invalid_key")
        return self._unauthorized_response()

    def _log_auth_failure(self, request: Request, reason: str) -> None:
        client_ip = request.client.host if request.client else "unknown"
        request_id = getattr(request.state, "request_id", "")
        audit = get_audit_logger()
        audit.log_auth_failure(client_ip=client_ip, request_id=request_id)
        logger.warning("auth_failed", reason=reason, client_ip=client_ip, path=request.url.path)

    @staticmethod
    def _unauthorized_response() -> Response:
        return Response(
            content=(
                '{"error":{"code":"AUTHENTICATION_ERROR","message":"Invalid or missing API key"}}'
            ),
            status_code=401,
            media_type="application/json",
        )

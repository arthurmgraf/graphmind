"""Structured error handling for GraphMind API.

Provides a standard error envelope, custom exceptions, and a FastAPI
exception handler that maps exceptions to HTTP status codes.
"""

from __future__ import annotations

import structlog
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Error envelope schema
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str = ""
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class GraphMindError(Exception):
    """Base exception for all GraphMind errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationError(GraphMindError):
    status_code = 400
    error_code = "VALIDATION_ERROR"


class AuthenticationError(GraphMindError):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"


class ForbiddenError(GraphMindError):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(GraphMindError):
    status_code = 404
    error_code = "NOT_FOUND"


class RateLimitError(GraphMindError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"


class PayloadTooLargeError(GraphMindError):
    status_code = 413
    error_code = "PAYLOAD_TOO_LARGE"


class PipelineError(GraphMindError):
    status_code = 500
    error_code = "PIPELINE_ERROR"


class ProviderExhaustedError(GraphMindError):
    status_code = 502
    error_code = "ALL_PROVIDERS_EXHAUSTED"


class InjectionDetectedError(GraphMindError):
    status_code = 400
    error_code = "INJECTION_DETECTED"


# ---------------------------------------------------------------------------
# Exception handler registration
# ---------------------------------------------------------------------------

def _build_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    include_trace: bool = False,
    exc: Exception | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    error_details = details
    if include_trace and exc is not None:
        error_details = error_details or {}
        error_details["traceback"] = traceback.format_exception(exc)

    body = ErrorResponse(
        error=ErrorDetail(
            code=error_code,
            message=message,
            request_id=request_id,
            details=error_details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(app: FastAPI, *, debug: bool = False) -> None:
    """Register structured exception handlers on a FastAPI app."""

    @app.exception_handler(GraphMindError)
    async def _graphmind_error(request: Request, exc: GraphMindError) -> JSONResponse:
        logger.warning(
            "GraphMindError %s: %s", exc.error_code, exc.message,
        )
        return _build_error_response(
            request,
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            include_trace=debug,
            exc=exc,
        )

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        return _build_error_response(
            request,
            status_code=400,
            error_code="VALIDATION_ERROR",
            message=str(exc),
            include_trace=debug,
            exc=exc,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        message = str(exc) if debug else "An internal error occurred"
        return _build_error_response(
            request,
            status_code=500,
            error_code="INTERNAL_ERROR",
            message=message,
            include_trace=debug,
            exc=exc,
        )

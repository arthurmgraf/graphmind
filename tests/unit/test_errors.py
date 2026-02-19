from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# errors.py imports fastapi and pydantic at the module level.
# If fastapi is not installed in the test environment, we need to provide
# lightweight stubs so the module can be imported without error.
_need_fastapi_stub = "fastapi" not in sys.modules
if _need_fastapi_stub:
    _fastapi_mod = ModuleType("fastapi")
    _fastapi_mod.FastAPI = MagicMock()  # type: ignore[attr-defined]
    _fastapi_mod.Request = MagicMock()  # type: ignore[attr-defined]
    _fastapi_responses = ModuleType("fastapi.responses")
    _fastapi_responses.JSONResponse = MagicMock()  # type: ignore[attr-defined]
    sys.modules["fastapi"] = _fastapi_mod
    sys.modules["fastapi.responses"] = _fastapi_responses

from graphmind.errors import (  # noqa: E402
    AuthenticationError,
    ForbiddenError,
    GraphMindError,
    InjectionDetectedError,
    NotFoundError,
    PayloadTooLargeError,
    PipelineError,
    ProviderExhaustedError,
    RateLimitError,
    ValidationError,
)


class TestGraphMindError:
    def test_stores_message(self):
        err = GraphMindError("something broke")
        assert err.message == "something broke"
        assert str(err) == "something broke"

    def test_stores_details(self):
        details = {"field": "name", "reason": "required"}
        err = GraphMindError("bad input", details=details)
        assert err.details == details

    def test_details_default_to_none(self):
        err = GraphMindError("oops")
        assert err.details is None

    def test_default_status_code(self):
        assert GraphMindError.status_code == 500

    def test_default_error_code(self):
        assert GraphMindError.error_code == "INTERNAL_ERROR"

    def test_is_exception(self):
        err = GraphMindError("boom")
        assert isinstance(err, Exception)


class TestValidationError:
    def test_status_code(self):
        assert ValidationError.status_code == 400

    def test_error_code(self):
        assert ValidationError.error_code == "VALIDATION_ERROR"

    def test_inherits_graphmind_error(self):
        err = ValidationError("bad field")
        assert isinstance(err, GraphMindError)
        assert err.message == "bad field"


class TestAuthenticationError:
    def test_status_code(self):
        assert AuthenticationError.status_code == 401

    def test_error_code(self):
        assert AuthenticationError.error_code == "AUTHENTICATION_ERROR"

    def test_inherits_graphmind_error(self):
        assert issubclass(AuthenticationError, GraphMindError)


class TestForbiddenError:
    def test_status_code(self):
        assert ForbiddenError.status_code == 403

    def test_error_code(self):
        assert ForbiddenError.error_code == "FORBIDDEN"

    def test_inherits_graphmind_error(self):
        assert issubclass(ForbiddenError, GraphMindError)


class TestNotFoundError:
    def test_status_code(self):
        assert NotFoundError.status_code == 404

    def test_error_code(self):
        assert NotFoundError.error_code == "NOT_FOUND"

    def test_inherits_graphmind_error(self):
        assert issubclass(NotFoundError, GraphMindError)


class TestRateLimitError:
    def test_status_code(self):
        assert RateLimitError.status_code == 429

    def test_error_code(self):
        assert RateLimitError.error_code == "RATE_LIMIT_EXCEEDED"

    def test_inherits_graphmind_error(self):
        assert issubclass(RateLimitError, GraphMindError)


class TestPayloadTooLargeError:
    def test_status_code(self):
        assert PayloadTooLargeError.status_code == 413

    def test_error_code(self):
        assert PayloadTooLargeError.error_code == "PAYLOAD_TOO_LARGE"

    def test_inherits_graphmind_error(self):
        assert issubclass(PayloadTooLargeError, GraphMindError)


class TestPipelineError:
    def test_status_code(self):
        assert PipelineError.status_code == 500

    def test_error_code(self):
        assert PipelineError.error_code == "PIPELINE_ERROR"

    def test_inherits_graphmind_error(self):
        assert issubclass(PipelineError, GraphMindError)


class TestProviderExhaustedError:
    def test_status_code(self):
        assert ProviderExhaustedError.status_code == 502

    def test_error_code(self):
        assert ProviderExhaustedError.error_code == "ALL_PROVIDERS_EXHAUSTED"

    def test_inherits_graphmind_error(self):
        assert issubclass(ProviderExhaustedError, GraphMindError)


class TestInjectionDetectedError:
    def test_status_code(self):
        assert InjectionDetectedError.status_code == 400

    def test_error_code(self):
        assert InjectionDetectedError.error_code == "INJECTION_DETECTED"

    def test_inherits_graphmind_error(self):
        assert issubclass(InjectionDetectedError, GraphMindError)

    def test_stores_details(self):
        details = {"pattern": "ignore previous instructions"}
        err = InjectionDetectedError("injection detected", details=details)
        assert err.details == details
        assert err.message == "injection detected"


class TestAllSubclassesAreGraphMindErrors:
    """Verify every custom exception is part of the GraphMindError hierarchy."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            ValidationError,
            AuthenticationError,
            ForbiddenError,
            NotFoundError,
            RateLimitError,
            PayloadTooLargeError,
            PipelineError,
            ProviderExhaustedError,
            InjectionDetectedError,
        ],
    )
    def test_is_subclass(self, exc_class):
        assert issubclass(exc_class, GraphMindError)

    @pytest.mark.parametrize(
        "exc_class",
        [
            ValidationError,
            AuthenticationError,
            ForbiddenError,
            NotFoundError,
            RateLimitError,
            PayloadTooLargeError,
            PipelineError,
            ProviderExhaustedError,
            InjectionDetectedError,
        ],
    )
    def test_can_be_caught_as_graphmind_error(self, exc_class):
        with pytest.raises(GraphMindError):
            raise exc_class("test")

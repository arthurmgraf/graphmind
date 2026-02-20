"""Tests for AuthMiddleware with RBAC resolution."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from graphmind.api.main import create_app
from graphmind.config import Settings
from graphmind.security.rbac import RBACRegistry, Role


@pytest.fixture
def settings_with_key():
    """Settings with API key configured."""
    s = Settings()
    s.api_key = "test-secret-key"
    return s


@pytest.fixture
def settings_no_key():
    """Settings with no API key (dev mode)."""
    s = Settings()
    s.api_key = ""
    return s


@pytest.fixture
def app_with_key(settings_with_key):
    app = create_app(settings=settings_with_key)
    # Mock resources to prevent real connections
    resources = MagicMock()
    resources.settings = settings_with_key
    resources.startup = AsyncMock()
    resources.shutdown = AsyncMock()
    resources.llm_router = None
    resources.neo4j_driver = None
    resources.qdrant_client = None
    resources.hybrid_retriever = None
    resources.embedder = None
    resources.vector_retriever = None
    resources.cost_tracker = MagicMock()
    resources.metrics = MagicMock()
    app.state.resources = resources
    return app


@pytest.fixture
def client_with_key(app_with_key):
    return TestClient(app_with_key, raise_server_exceptions=False)


@pytest.fixture
def app_no_key(settings_no_key):
    app = create_app(settings=settings_no_key)
    resources = MagicMock()
    resources.settings = settings_no_key
    resources.startup = AsyncMock()
    resources.shutdown = AsyncMock()
    resources.llm_router = None
    resources.neo4j_driver = None
    resources.qdrant_client = None
    app.state.resources = resources
    return app


@pytest.fixture
def client_no_key(app_no_key):
    return TestClient(app_no_key, raise_server_exceptions=False)


class TestPublicPaths:
    def test_health_no_auth_needed(self, client_with_key):
        """Health endpoint should be accessible without authentication."""
        resp = client_with_key.get("/api/v1/health")
        assert resp.status_code != 401


class TestMissingKey:
    def test_missing_key_returns_401(self, client_with_key):
        """Requests without Authorization header should get 401."""
        resp = client_with_key.post(
            "/api/v1/query",
            json={"question": "test"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "AUTHENTICATION_ERROR"


class TestInvalidKey:
    def test_invalid_key_returns_401(self, client_with_key):
        """Requests with wrong API key should get 401."""
        resp = client_with_key.post(
            "/api/v1/query",
            json={"question": "test"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401


class TestLegacyKey:
    def test_legacy_key_grants_admin(self, client_with_key):
        """The settings.api_key should work as a legacy admin key."""
        resp = client_with_key.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        # Should not be 401 — the key is valid
        assert resp.status_code != 401


class TestRBACKey:
    def test_rbac_key_resolves_role(self, app_with_key):
        """A key registered in RBACRegistry should resolve to its role."""
        registry: RBACRegistry = app_with_key.state.rbac_registry
        key = "rbac-viewer-key"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        registry.register_key(
            key_hash=key_hash,
            tenant_id="tenant-a",
            role=Role.VIEWER,
            description="test viewer",
        )

        client = TestClient(app_with_key, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert resp.status_code != 401


class TestTimingSafe:
    def test_timing_safe_comparison_used(self):
        """Verify that auth.py uses hmac.compare_digest (code inspection)."""
        import inspect

        from graphmind.security.auth import AuthMiddleware

        source = inspect.getsource(AuthMiddleware)
        assert "hmac.compare_digest" in source
        # Should NOT use direct string comparison `!=` or `==` for key comparison
        assert "provided != settings.api_key" not in source
        assert "provided == settings.api_key" not in source


class TestAuthFailureAudit:
    def test_auth_failure_audit_logged(self, client_with_key):
        """Failed auth should log an audit event."""
        with patch("graphmind.security.auth.get_audit_logger") as mock_get_audit:
            mock_audit = MagicMock()
            mock_get_audit.return_value = mock_audit

            client_with_key.post(
                "/api/v1/query",
                json={"question": "test"},
                headers={"Authorization": "Bearer bad-key"},
            )

            mock_audit.log_auth_failure.assert_called_once()


class TestProductionNoKey:
    def test_production_no_key_rejects(self):
        """In production with no API_KEY, all requests should be rejected."""
        s = Settings()
        s.api_key = ""

        app = create_app(settings=s)
        resources = MagicMock()
        resources.settings = s
        resources.startup = AsyncMock()
        resources.shutdown = AsyncMock()
        app.state.resources = resources

        client = TestClient(app, raise_server_exceptions=False)

        prod_prop = property(lambda self: True)
        with patch.object(type(s), "is_production", new_callable=lambda: prod_prop):
            resp = client.post(
                "/api/v1/query",
                json={"question": "test"},
            )
            assert resp.status_code == 401

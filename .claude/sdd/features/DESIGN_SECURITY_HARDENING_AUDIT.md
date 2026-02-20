# DESIGN: Security Hardening Audit

> Technical design for fixing 7 CRITICAL/HIGH vulnerabilities and 7 MEDIUM improvements identified in the security audit.

## Metadata

| Attribute   | Value                                                                              |
| ----------- | ---------------------------------------------------------------------------------- |
| **Feature** | SECURITY_HARDENING_AUDIT                                                           |
| **Date**    | 2026-02-20                                                                         |
| **Author**  | design-agent                                                                       |
| **DEFINE**  | [DEFINE_SECURITY_HARDENING_AUDIT.md](./DEFINE_SECURITY_HARDENING_AUDIT.md)         |
| **Status**  | Ready for Build                                                                    |

---

## Architecture Overview

```text
BEFORE (current — broken auth):
┌──────────┐   ┌───────────────────────────────────────────────────┐
│  Client   │──▶│ RequestLogging → APIKey(single key) → RateLimit  │
│           │   │          ↓                                        │
│           │   │   All routes open (no role check)                │
│           │   │   /query  /ingest  /docs  /metrics  /health      │
└──────────┘   └───────────────────────────────────────────────────┘
                RBACRegistry exists but is DEAD CODE

AFTER (fixed — enforced RBAC):
┌──────────┐   ┌───────────────────────────────────────────────────┐
│  Client   │──▶│ RequestLogging → AuthMiddleware → RateLimit      │
│ Bearer key│   │       │                                          │
│           │   │       ├─ hash(key) → RBACRegistry.resolve()      │
│           │   │       ├─ request.state.role = record.role         │
│           │   │       ├─ request.state.tenant_id = record.tenant  │
│           │   │       └─ hmac.compare_digest() for timing safety  │
│           │   │                      ↓                            │
│           │   │   require_permission(P) dependency per route     │
│           │   │   /query[QUERY] /ingest[INGEST] /metrics[ADMIN]  │
└──────────┘   └───────────────────────────────────────────────────┘
                Public: /health(sanitized), /docs(dev only)

MCP Server (fixed):
┌──────────────┐   ┌───────────────────────────────────────┐
│ MCP stdio    │──▶│ Pydantic validation → InjectionDetector│
│ (local only) │   │         ↓                              │
│              │   │   run_query() / IngestionPipeline       │
└──────────────┘   └───────────────────────────────────────┘

Webhook Dispatcher (fixed):
┌──────────┐   ┌───────────────────────────────────────────┐
│ Register │──▶│ validate_url() → block private IPs/schemes│
│ webhook  │   │         ↓                                  │
│          │   │   SSRF-safe httpx.post() to allowed URLs   │
└──────────┘   └───────────────────────────────────────────┘
```

---

## Components

| Component | Purpose | Technology |
| --- | --- | --- |
| **AuthMiddleware** | Replace `APIKeyMiddleware` with RBAC-aware auth | Python/FastAPI middleware |
| **require_permission** | Per-route permission check dependency | FastAPI `Depends()` |
| **url_validator** | SSRF protection for webhooks | `ipaddress` stdlib |
| **MCP input validation** | Pydantic schemas + injection detection for MCP | Pydantic v2 |
| **Error sanitizer** | Remove internal details from error responses | Custom exception handler |
| **Security headers** | Add missing HTTP security headers | FastAPI middleware |

---

## Key Decisions

### Decision 1: Upgrade APIKeyMiddleware to RBAC-Aware AuthMiddleware

| Attribute  | Value      |
| ---------- | ---------- |
| **Status** | Accepted   |
| **Date**   | 2026-02-20 |

**Context:** The existing `APIKeyMiddleware` compares against a single global API key (`settings.api_key`). The existing `RBACRegistry` with roles/permissions is complete but unused. We need to connect them.

**Choice:** Replace `APIKeyMiddleware` with `AuthMiddleware` that:
1. Extracts Bearer token from `Authorization` header
2. Hashes it with SHA-256
3. Looks up the hash in `RBACRegistry`
4. Falls back to single-key mode (compares against `settings.api_key` as legacy support)
5. Attaches `role`, `tenant_id`, `key_record` to `request.state`
6. Uses `hmac.compare_digest()` for constant-time comparison

**Rationale:** This approach preserves backward compatibility (single API_KEY still works), activates the existing RBAC system, and adds timing-safe comparison in one change.

**Alternatives Rejected:**
1. JWT-based auth — Over-engineered for current scale, adds dependency (PyJWT), requires token issuance flow
2. API Gateway auth — Moves auth outside application, loses RBAC granularity per route
3. Database-backed key store — Adds DB dependency for auth, in-memory is sufficient at current scale

**Consequences:**
- Migration path: existing `API_KEY` env var becomes a "legacy admin key" that auto-registers with admin role
- New keys can be registered programmatically with specific roles/tenants
- Tests need updated fixtures for the new auth model

---

### Decision 2: Per-Route Permission Checks via FastAPI Dependencies

| Attribute  | Value      |
| ---------- | ---------- |
| **Status** | Accepted   |
| **Date**   | 2026-02-20 |

**Context:** Routes need to enforce specific permissions based on the authenticated user's role.

**Choice:** Create a `require_permission(permission: Permission)` factory that returns a FastAPI `Depends()` callable. Each route declares its required permission:

```python
@router.post("/query", dependencies=[Depends(require_permission(Permission.QUERY))])
```

**Rationale:** FastAPI's dependency injection is the idiomatic pattern. Each route is self-documenting about its permission requirement. The dependency reads `request.state.role` (set by middleware) and raises `ForbiddenError` if the role lacks the permission.

**Alternatives Rejected:**
1. Permission check in middleware (path→permission mapping) — Fragile, breaks when routes change. Not self-documenting.
2. Decorator pattern — Doesn't integrate with FastAPI's DI system.

**Consequences:**
- Every route must explicitly declare its permission (no implicit allow)
- Public routes remain in the middleware's `_PUBLIC_PATHS` set

---

### Decision 3: Decouple Debug Mode from API Key Presence

| Attribute  | Value      |
| ---------- | ---------- |
| **Status** | Accepted   |
| **Date**   | 2026-02-20 |

**Context:** Currently `debug = settings.api_key == ""` means any deployment without API_KEY gets stack traces in errors. This conflates "development convenience" with "security posture".

**Choice:** Base debug mode on `GRAPHMIND_ENV`:
- `GRAPHMIND_ENV=dev` or `GRAPHMIND_ENV=test` → debug=True
- `GRAPHMIND_ENV=staging` or `GRAPHMIND_ENV=production` → debug=False
- Also log a WARNING on startup when no API_KEY is set and env is not dev/test

**Rationale:** Environment is the correct signal for debug mode, not auth configuration. A staging deployment might have an API key but still want debug off.

**Alternatives Rejected:**
1. Refuse to start without API_KEY — Breaks development workflow, too disruptive
2. Explicit `DEBUG` env var — Another config to manage, env-based inference is simpler

**Consequences:**
- Development still works with no API_KEY (auth bypassed, debug enabled)
- Production/staging never leaks tracebacks regardless of API_KEY state

---

### Decision 4: SSRF Protection via Private IP Validation

| Attribute  | Value      |
| ---------- | ---------- |
| **Status** | Accepted   |
| **Date**   | 2026-02-20 |

**Context:** `WebhookDispatcher` makes HTTP requests to user-registered URLs with no validation.

**Choice:** Add `validate_webhook_url()` that:
1. Parses the URL (reject malformed)
2. Only allows `http` and `https` schemes
3. Resolves hostname to IP via `socket.getaddrinfo()`
4. Blocks private/reserved IP ranges via `ipaddress.ip_address().is_private`
5. Blocks `localhost`, `0.0.0.0`, `[::1]`, `169.254.x.x` (link-local)
6. Validates at registration time AND at dispatch time (DNS rebinding defense)

**Rationale:** Using stdlib `ipaddress` is zero-dependency and covers all RFC 1918/5737/6598 ranges. Checking at both registration and dispatch time prevents DNS rebinding attacks.

**Alternatives Rejected:**
1. URL allowlist only — Too restrictive, doesn't scale with legitimate webhook targets
2. Check at registration only — Vulnerable to DNS rebinding (domain resolves to public IP at register, private IP at dispatch)

**Consequences:**
- Webhooks to internal services (localhost:7687 etc.) will be blocked
- Time-of-check-to-time-of-use (TOCTOU) gap minimized by dual validation

---

### Decision 5: MCP Server Input Validation (Not Full Auth)

| Attribute  | Value      |
| ---------- | ---------- |
| **Status** | Accepted   |
| **Date**   | 2026-02-20 |

**Context:** MCP server runs via stdio (local process), not over network. But it lacks input validation and injection detection.

**Choice:** Add:
1. Pydantic schema validation for all tool inputs (reuse existing `QueryRequest`, `IngestRequest`)
2. Injection detection via `InjectionDetector` before query execution
3. Length limits matching REST API constraints
4. Clear documentation that MCP is local-only

**Rationale:** MCP stdio is inherently local (requires process access), so full authentication is unnecessary. But input validation and injection detection are defense-in-depth against compromised MCP clients.

**Alternatives Rejected:**
1. Full API key auth for MCP — stdio doesn't have headers, would require custom auth protocol
2. Ignore MCP security — Leaves a gap where a compromised MCP client bypasses all safety

**Consequences:**
- MCP and REST API share the same safety layer (injection detection)
- MCP input validation reuses existing Pydantic schemas

---

## File Manifest

| # | File | Action | Purpose | Dependencies |
| --- | --- | --- | --- | --- |
| 1 | `src/graphmind/api/main.py` | **Modify** | Replace `APIKeyMiddleware` with `AuthMiddleware`, decouple debug mode from API_KEY, add security headers, move `/metrics` to authenticated paths, disable `/docs`+`/redoc` in production | None |
| 2 | `src/graphmind/security/rbac.py` | **Modify** | Add `require_permission()` dependency factory, add legacy key auto-registration | None |
| 3 | `src/graphmind/security/auth.py` | **Create** | `AuthMiddleware` class with RBAC resolution, timing-safe comparison, audit logging | 2 |
| 4 | `src/graphmind/security/ssrf.py` | **Create** | `validate_webhook_url()` with private IP blocking, DNS rebinding defense | None |
| 5 | `src/graphmind/webhooks/dispatcher.py` | **Modify** | Integrate SSRF validation on `register()` and `_deliver()` | 4 |
| 6 | `src/graphmind/mcp/server.py` | **Modify** | Add Pydantic validation for tool inputs, add injection detection for queries | None |
| 7 | `src/graphmind/errors.py` | **Modify** | Sanitize error messages: never include exception text in non-debug mode | None |
| 8 | `src/graphmind/api/routes/health.py` | **Modify** | Sanitize health check error messages (no exception details in response) | None |
| 9 | `src/graphmind/api/routes/graph.py` | **Modify** | Remove `str(exc)` from error responses | None |
| 10 | `src/graphmind/api/routes/query.py` | **Modify** | Add `Depends(require_permission(Permission.QUERY))` | 2 |
| 11 | `src/graphmind/api/routes/ingest.py` | **Modify** | Add `Depends(require_permission(Permission.INGEST))` | 2 |
| 12 | `src/graphmind/api/routes/documents.py` | **Modify** | Add `Depends(require_permission(Permission.VIEW_STATS))`, enforce tenant_id from `request.state` | 2 |
| 13 | `src/graphmind/api/routes/metrics.py` | **Modify** | Add `Depends(require_permission(Permission.VIEW_METRICS))` | 2 |
| 14 | `src/graphmind/schemas.py` | **Modify** | Add `doc_type` field_validator against supported_formats | None |
| 15 | `src/graphmind/config.py` | **Modify** | Add `debug` property based on GRAPHMIND_ENV, add `auth_required` warning | None |
| 16 | `docker-compose.yml` | **Modify** | Bind all ports to `127.0.0.1` | None |
| 17 | `k8s/networkpolicy.yaml` | **Create** | Pod-to-pod isolation for GraphMind namespace | None |
| 18 | `k8s/kustomization.yaml` | **Modify** | Add `networkpolicy.yaml` to resources list | 17 |
| 19 | `tests/unit/test_auth_middleware.py` | **Create** | Tests for AuthMiddleware with RBAC | 3 |
| 20 | `tests/unit/test_ssrf.py` | **Create** | Tests for SSRF URL validation | 4 |
| 21 | `tests/unit/test_security_routes.py` | **Create** | Tests for permission enforcement on routes | 2, 3 |
| 22 | `tests/unit/test_mcp_security.py` | **Create** | Tests for MCP input validation and injection detection | 6 |

**Total Files:** 22 (5 Create, 15 Modify, 2 Modify-infra)

---

## Agent Assignment Rationale

| Agent | Files Assigned | Why This Agent |
| --- | --- | --- |
| @python-developer | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | All Python source changes require clean patterns, type hints, dataclasses |
| @test-generator | 19, 20, 21, 22 | Pytest test generation with fixtures and edge cases |
| (general) | 16, 17, 18 | YAML infrastructure changes, no specialist needed |

---

## Code Patterns

### Pattern 1: AuthMiddleware (replaces APIKeyMiddleware)

```python
# src/graphmind/security/auth.py
"""RBAC-aware authentication middleware with timing-safe comparison."""
from __future__ import annotations

import hashlib
import hmac

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from graphmind.observability.audit import AuditLogger
from graphmind.security.rbac import RBACRegistry, Role

logger = structlog.get_logger(__name__)
_audit = AuditLogger()


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate requests via API key → RBAC resolution.

    Supports two modes:
    1. RBAC mode: key hash looked up in RBACRegistry for role/tenant
    2. Legacy mode: key compared against settings.api_key (auto-registered as admin)

    Public paths bypass authentication entirely.
    """

    _PUBLIC_PATHS = {"/api/v1/health", "/openapi.json"}

    def __init__(self, app, registry: RBACRegistry):
        super().__init__(app)
        self._registry = registry

    async def dispatch(self, request: Request, call_next):
        settings = request.app.state.resources.settings

        # No auth configured → allow in dev/test, warn in production
        if not settings.api_key:
            if settings.is_production:
                logger.error("API_KEY not set in production — rejecting all requests")
                return self._unauthorized_response(request)
            # Dev/test: allow without auth
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
        provided = (
            request.headers.get("Authorization", "")
            .removeprefix("Bearer ")
            .strip()
        )
        if not provided:
            self._log_auth_failure(request, "missing_key")
            return self._unauthorized_response(request)

        # Try RBAC registry first (hashed key lookup)
        key_hash = hashlib.sha256(provided.encode()).hexdigest()
        record = self._registry.resolve(key_hash)

        if record is not None:
            request.state.role = record.role
            request.state.tenant_id = record.tenant_id
            request.state.key_record = record
            return await call_next(request)

        # Legacy fallback: compare against settings.api_key
        if hmac.compare_digest(provided.encode(), settings.api_key.encode()):
            request.state.role = Role.ADMIN
            request.state.tenant_id = "default"
            return await call_next(request)

        self._log_auth_failure(request, "invalid_key")
        return self._unauthorized_response(request)

    def _log_auth_failure(self, request: Request, reason: str) -> None:
        client_ip = request.client.host if request.client else "unknown"
        request_id = getattr(request.state, "request_id", "")
        _audit.log_auth_failure(client_ip=client_ip, request_id=request_id)
        logger.warning(
            "auth_failed", reason=reason, client_ip=client_ip, path=request.url.path
        )

    @staticmethod
    def _unauthorized_response(request: Request) -> Response:
        return Response(
            content=(
                '{"error":{"code":"AUTHENTICATION_ERROR",'
                '"message":"Invalid or missing API key"}}'
            ),
            status_code=401,
            media_type="application/json",
        )
```

### Pattern 2: require_permission Dependency

```python
# Addition to src/graphmind/security/rbac.py

from fastapi import Request
from graphmind.errors import ForbiddenError

_ROLE_PERMISSIONS: dict[Role, set[Permission]] = { ... }  # existing


def require_permission(permission: Permission):
    """FastAPI dependency factory for route-level permission checks.

    Usage:
        @router.post("/ingest", dependencies=[Depends(require_permission(Permission.INGEST))])
    """
    async def _check(request: Request) -> None:
        role: Role | None = getattr(request.state, "role", None)
        if role is None:
            raise ForbiddenError("No role assigned — authentication may have failed")
        allowed = _ROLE_PERMISSIONS.get(role, set())
        if permission not in allowed:
            raise ForbiddenError(
                f"Role '{role.value}' lacks permission '{permission.value}'",
                details={"required": permission.value, "role": role.value},
            )
    return _check
```

### Pattern 3: SSRF URL Validator

```python
# src/graphmind/security/ssrf.py
"""SSRF protection: validate webhook URLs against private IP ranges."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)

_BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}


class SSRFError(Exception):
    """Raised when a URL targets a private/internal resource."""


def validate_webhook_url(url: str) -> None:
    """Validate that a webhook URL does not target private/internal resources.

    Raises SSRFError if the URL is unsafe. Call at BOTH registration and dispatch
    time to defend against DNS rebinding.
    """
    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"Unsupported scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("Missing hostname in URL")

    # Known blocked hostnames
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"Blocked hostname: {hostname}")

    # Resolve hostname to IP(s) and check each
    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFError(f"DNS resolution failed for {hostname}: {exc}") from exc

    for family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            raise SSRFError(f"URL resolves to private/reserved IP: {ip}")

    logger.debug("webhook_url_validated", url=url)
```

### Pattern 4: Sanitized Health Check Errors

```python
# Pattern for health.py error sanitization
async def _check_neo4j(request: Request) -> str:
    ...
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return "unhealthy"  # NOT f"unhealthy: {exc}"
```

### Pattern 5: MCP Input Validation

```python
# Pattern for mcp/server.py query handler
async def _handle_query(arguments: dict[str, Any]) -> list[TextContent]:
    # Validate via Pydantic (reuse REST schema)
    from graphmind.schemas import QueryRequest
    try:
        validated = QueryRequest(
            question=arguments.get("question", ""),
            top_k=arguments.get("top_k", 10),
            engine=arguments.get("engine", "langgraph"),
        )
    except ValidationError as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    # Injection detection (same as REST API)
    from graphmind.safety.injection_detector import InjectionDetector
    detector = InjectionDetector()
    result_check = detector.detect(validated.question)
    if result_check.is_suspicious:
        return [TextContent(type="text", text=json.dumps({
            "error": "Potential prompt injection detected",
            "patterns": result_check.matched_patterns,
        }))]

    result = await run_query(question=validated.question, engine=validated.engine)
    ...
```

### Pattern 6: doc_type Validation

```python
# Addition to src/graphmind/schemas.py IngestRequest
class IngestRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10 * 1024 * 1024)
    filename: str = Field(..., min_length=1, max_length=512)
    doc_type: str = "markdown"
    tenant_id: str | None = Field(default=None)

    @field_validator("doc_type")
    @classmethod
    def _validate_doc_type(cls, v: str) -> str:
        allowed = {"pdf", "md", "markdown", "html", "txt", "py", "ts", "js"}
        if v not in allowed:
            raise ValueError(f"doc_type must be one of {sorted(allowed)}")
        return v
```

### Pattern 7: Docker Compose Port Binding

```yaml
# docker-compose.yml — bind to localhost only
services:
  qdrant:
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"
  neo4j:
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
  postgres:
    ports:
      - "127.0.0.1:5432:5432"
  langfuse:
    ports:
      - "127.0.0.1:3000:3000"
  ollama:
    ports:
      - "127.0.0.1:11434:11434"
```

### Pattern 8: K8s NetworkPolicy

```yaml
# k8s/networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: graphmind-api-policy
  namespace: graphmind
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: graphmind
      app.kubernetes.io/component: api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 8000
          protocol: TCP
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/part-of: graphmind
      ports:
        - port: 7687   # Neo4j
        - port: 6333   # Qdrant
        - port: 11434  # Ollama
        - port: 3000   # Langfuse
    - to:                # Allow external HTTPS (LLM APIs, webhooks)
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - port: 443
          protocol: TCP
```

### Pattern 9: Config.is_production Property

```python
# Addition to src/graphmind/config.py Settings
import os

class Settings(BaseSettings):
    ...  # existing fields

    @property
    def is_production(self) -> bool:
        env = os.getenv("GRAPHMIND_ENV", "dev").lower()
        return env in ("production", "staging")

    @property
    def debug(self) -> bool:
        env = os.getenv("GRAPHMIND_ENV", "dev").lower()
        return env in ("dev", "test")
```

---

## Data Flow

```text
1. Client sends request with `Authorization: Bearer <api_key>`
   │
   ▼
2. RequestLoggingMiddleware assigns request_id
   │
   ▼
3. AuthMiddleware:
   ├─ Public path? → skip auth, continue
   ├─ No API_KEY configured?
   │   ├─ Production? → 401 reject
   │   └─ Dev/test? → assign admin role, continue
   ├─ Hash provided key → look up in RBACRegistry
   │   ├─ Found? → assign role + tenant_id from record
   │   └─ Not found? → hmac.compare_digest vs settings.api_key
   │       ├─ Match? → assign admin role (legacy mode)
   │       └─ No match? → 401 + audit log
   │
   ▼
4. RateLimitMiddleware → BodySizeLimitMiddleware
   │
   ▼
5. Route handler:
   ├─ require_permission(Permission.X) dependency
   │   ├─ Role has permission? → continue
   │   └─ Role lacks permission? → 403 Forbidden
   ├─ Route logic executes
   └─ Error handler:
       ├─ Debug mode? → include traceback
       └─ Production? → generic message + request_id only
```

---

## Integration Points

| External System | Integration Type | Authentication | Security Change |
| --- | --- | --- | --- |
| Neo4j | Bolt driver | Username/password env var | No change |
| Qdrant | REST SDK | None (internal network) | K8s NetworkPolicy restricts access |
| Ollama | HTTP REST | None (internal network) | K8s NetworkPolicy restricts access |
| Langfuse | HTTP REST | Public/Secret key env vars | No change |
| Groq/Gemini APIs | HTTP REST | API keys env vars | No change |
| Webhook targets | HTTP POST | HMAC signature | SSRF validation added |

---

## Testing Strategy

| Test Type | Scope | Files | Tools | Coverage Goal |
| --- | --- | --- | --- | --- |
| Unit | AuthMiddleware | `test_auth_middleware.py` | pytest + httpx | All auth paths (6 scenarios) |
| Unit | SSRF validator | `test_ssrf.py` | pytest | All IP ranges + DNS mock |
| Unit | Route permissions | `test_security_routes.py` | pytest + FastAPI TestClient | All routes × all roles |
| Unit | MCP validation | `test_mcp_security.py` | pytest | Input validation + injection |
| Integration | Full auth flow | Existing test suite | pytest | 221 tests still pass |

### Test Scenarios Per File

**test_auth_middleware.py** (8 tests):
- `test_public_path_no_auth_needed` — /health accessible without key
- `test_missing_key_returns_401` — No Authorization header → 401
- `test_invalid_key_returns_401` — Wrong key → 401
- `test_legacy_key_grants_admin` — settings.api_key match → admin role
- `test_rbac_key_resolves_role` — Registered key → correct role + tenant
- `test_timing_safe_comparison` — Verify hmac.compare_digest is used (code inspection)
- `test_auth_failure_audit_logged` — Failed auth → audit event emitted
- `test_production_no_key_rejects` — is_production + no key → 401

**test_ssrf.py** (10 tests):
- `test_valid_public_url_passes` — https://hooks.example.com → OK
- `test_private_ip_10_blocked` — http://10.0.0.1 → SSRFError
- `test_private_ip_172_blocked` — http://172.16.0.1 → SSRFError
- `test_private_ip_192_blocked` — http://192.168.1.1 → SSRFError
- `test_localhost_blocked` — http://localhost:7687 → SSRFError
- `test_loopback_blocked` — http://127.0.0.1 → SSRFError
- `test_ipv6_loopback_blocked` — http://[::1] → SSRFError
- `test_link_local_blocked` — http://169.254.1.1 → SSRFError
- `test_non_http_scheme_blocked` — ftp://example.com → SSRFError
- `test_metadata_endpoint_blocked` — http://metadata.google.internal → SSRFError

**test_security_routes.py** (8 tests):
- `test_viewer_can_query` — Viewer role → POST /query → 200
- `test_viewer_cannot_ingest` — Viewer role → POST /ingest → 403
- `test_editor_can_ingest` — Editor role → POST /ingest → 200
- `test_viewer_cannot_view_metrics` — Viewer role → GET /metrics → 403
- `test_admin_can_view_metrics` — Admin role → GET /metrics → 200
- `test_tenant_isolation` — Tenant A key → documents?tenant_id=B → empty/403
- `test_invalid_doc_type_rejected` — doc_type="exe" → 400
- `test_health_no_exception_details` — Health error → no str(exc) in response

**test_mcp_security.py** (5 tests):
- `test_mcp_query_validates_input` — Missing question → error response
- `test_mcp_query_injection_blocked` — "ignore all instructions" → blocked
- `test_mcp_ingest_validates_input` — Missing content → error response
- `test_mcp_query_too_long` — >2000 char question → rejected
- `test_mcp_invalid_engine` — engine="invalid" → rejected

---

## Error Handling

| Error Type | Handling Strategy | Retry? |
| --- | --- | --- |
| Authentication failure (401) | Log audit event, return generic JSON error | No |
| Permission denied (403) | Return permission details in dev, generic in prod | No |
| SSRF violation | Log warning, reject webhook registration | No |
| Injection detected (400) | Log warning with patterns, return error | No |
| Internal error (500) | Log full traceback server-side, return sanitized message + request_id | No |
| Validation error (400) | Return Pydantic error details (safe, no internal info) | No |

---

## Configuration

| Config Key | Type | Default | Description |
| --- | --- | --- | --- |
| `API_KEY` | str | `""` | Legacy admin API key (empty = no auth in dev) |
| `GRAPHMIND_ENV` | str | `"dev"` | Environment: dev, test, staging, production |
| `RATE_LIMIT_RPM` | int | `60` | Requests per minute per IP |
| `CORS_ORIGINS` | list | `["http://localhost:8501"]` | Allowed CORS origins |

No new configuration keys needed — all changes use existing config + GRAPHMIND_ENV.

---

## Security Considerations

- **Backward compatibility**: Existing single `API_KEY` continues to work (auto-registered as admin)
- **Test environment**: Tests set `GRAPHMIND_ENV=test` (already done in conftest.py), which means auth is bypassed in tests unless explicitly testing auth
- **SSRF dual check**: Validating URLs at both registration and dispatch time mitigates DNS rebinding
- **Constant-time comparison**: `hmac.compare_digest()` prevents timing-based key extraction
- **No secrets in logs**: Auth failures log client IP and path but never the provided key
- **Audit trail**: All auth failures are logged with structured audit events

---

## Observability

| Aspect | Implementation |
| --- | --- |
| Logging | Auth failures logged via `AuditLogger.log_auth_failure()` with client_ip, request_id |
| Metrics | Existing Prometheus counters will capture 401/403 responses automatically |
| Tracing | Existing OpenTelemetry spans capture request lifecycle (no changes needed) |

---

## Implementation Order

Build should proceed in this order to maintain a working system at each step:

```text
Phase A: Foundation (no breaking changes)
  1. config.py — Add is_production, debug properties
  2. security/ssrf.py — Create SSRF validator (standalone)
  3. schemas.py — Add doc_type validator
  4. errors.py — Sanitize error responses

Phase B: Auth overhaul
  5. security/rbac.py — Add require_permission factory
  6. security/auth.py — Create AuthMiddleware
  7. api/main.py — Swap middleware, decouple debug, protect /docs+/metrics

Phase C: Route protection
  8. api/routes/query.py — Add permission dependency
  9. api/routes/ingest.py — Add permission dependency
  10. api/routes/documents.py — Add permission + tenant enforcement
  11. api/routes/metrics.py — Add permission dependency
  12. api/routes/graph.py — Sanitize error responses
  13. api/routes/health.py — Sanitize error responses

Phase D: Webhook + MCP
  14. webhooks/dispatcher.py — Integrate SSRF validation
  15. mcp/server.py — Add input validation + injection detection

Phase E: Infrastructure
  16. docker-compose.yml — Bind ports to 127.0.0.1
  17. k8s/networkpolicy.yaml — Create
  18. k8s/kustomization.yaml — Add networkpolicy

Phase F: Tests
  19-22. All test files
```

---

## Revision History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-02-20 | design-agent | Initial design for security hardening |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_SECURITY_HARDENING_AUDIT.md`

# DEFINE: Security Hardening Audit

> Comprehensive security audit of GraphMind against 50+ attack vectors across OWASP Top 10, business logic flaws, infrastructure security, and advanced modern attacks.

## Metadata

| Attribute         | Value                  |
| ----------------- | ---------------------- |
| **Feature**       | SECURITY_HARDENING_AUDIT |
| **Date**          | 2026-02-20             |
| **Author**        | define-agent (Claude)  |
| **Status**        | Ready for Design       |
| **Clarity Score** | 14/15                  |

---

## Problem Statement

GraphMind is an AI knowledge platform that processes user queries, ingests documents, and interfaces with Neo4j/Qdrant/Ollama. While the codebase has solid foundational security (API key auth, rate limiting, Pydantic validation, injection detection), there are **critical gaps** in RBAC enforcement, SSRF protection, error information leakage, CSRF protection, and secrets management that could be exploited in a production environment.

---

## Target Users

| User | Role | Pain Point |
| --- | --- | --- |
| Platform Operator | DevOps/SRE | Needs confidence that production deployment is secure against common attack vectors |
| API Consumer | Developer | Needs assurance that multi-tenant data isolation works and their data is protected |
| Security Auditor | InfoSec | Needs to verify compliance with OWASP Top 10 and industry best practices |

---

## Current Security Posture: Full Audit Results

### SEVERITY LEGEND
- **CRITICAL**: Exploitable now, data breach or RCE risk
- **HIGH**: Significant vulnerability requiring near-term fix
- **MEDIUM**: Defense-in-depth gap, exploit requires additional conditions
- **LOW**: Best practice improvement, minimal direct risk
- **INFO**: Informational finding, no immediate risk

---

## CATEGORY 1: Minimize Attack Surface Area

### 1.1 Input Validation (Injection Protection)

| Check | Status | Details |
| --- | --- | --- |
| **SQL Injection** | **PROTECTED** | No raw SQL in codebase. Uses Neo4j parameterized queries (`$param` syntax) and Qdrant client SDK. All Neo4j queries in `graph_builder.py`, `graph_retriever.py`, `graph.py`, `documents.py` use `$` parameters correctly. |
| **Cypher Injection** | **PROTECTED** | All Neo4j queries use parameterized `$variable` syntax (e.g., `graph_retriever.py:31`, `graph_builder.py:21-51`). The injection detector also catches `MERGE...SET` patterns (`injection_detector.py:35`). |
| **NoSQL Injection** | **PROTECTED** | Qdrant uses typed SDK calls (`FieldCondition`, `MatchValue`), not raw queries. No MongoDB in stack. |
| **Command Injection (RCE)** | **PROTECTED** | No `os.system()`, `subprocess`, or `eval()` calls found in the codebase. |
| **Prompt Injection** | **PROTECTED** | `InjectionDetector` (`injection_detector.py`) with 16 regex patterns + NeMo Guardrails (`guardrails.py`) as a second layer. Feature-flagged via `injection_detection_enabled` (ON by default). |
| **XSS (via API)** | **PROTECTED** | API returns JSON only. Pydantic serialization auto-escapes. No HTML rendering on server side. |
| **LDAP Injection** | **N/A** | No LDAP in architecture. |
| **XXE (XML External Entity)** | **N/A** | No XML parsing in codebase. Supported ingestion formats are text-based (md, pdf, html, txt, py, ts, js). |
| **HTTP Request Smuggling** | **LOW** | Uvicorn + FastAPI handle request parsing correctly. No proxy splitting observed. In K8s, nginx ingress adds a layer of parsing. |

### 1.2 Public Endpoints

| Check | Status | Details |
| --- | --- | --- |
| **Unauthenticated API routes** | **MEDIUM** | Public paths: `/api/v1/health`, `/docs`, `/redoc`, `/openapi.json`, `/metrics` (`main.py:103`). The `/metrics` endpoint exposes Prometheus data (request counts, latencies, circuit breaker states) to anyone without auth. |
| **Rate limiting** | **PROTECTED** | Sliding-window per-IP rate limiter (`main.py:131-175`) bounded to 10,000 clients. Default 60 RPM. Configurable via `settings.rate_limit_rpm`. |
| **Body size limit** | **PROTECTED** | `BodySizeLimitMiddleware` (`main.py:183-201`) rejects requests >15MB. |
| **OpenAPI/Docs exposure** | **MEDIUM** | `/docs` and `/redoc` are accessible in production. Should be disabled when `API_KEY` is set. |

### 1.3 Security by Obscurity / IDOR

| Check | Status | Details |
| --- | --- | --- |
| **IDOR (Sequential IDs)** | **PROTECTED** | All entity IDs use UUID4 (`schemas.py:15-16`): `str(uuid.uuid4())`. Not sequential/enumerable. |
| **Object-level authorization** | **HIGH** | No per-object ownership check. The `documents.py:46-79` endpoint filters by `tenant_id` parameter but **trusts the client-supplied `tenant_id`** without verifying it against the authenticated API key. An attacker with a valid key can pass any `tenant_id` to access other tenants' documents. |

---

## CATEGORY 2: Least Privilege

| Check | Status | Details |
| --- | --- | --- |
| **RBAC defined** | **PROTECTED** | Full RBAC model with Admin/Editor/Viewer roles and 10 granular permissions (`rbac.py:13-48`). |
| **RBAC enforced on routes** | **CRITICAL** | RBAC is **defined but NOT enforced**. The `APIKeyMiddleware` (`main.py:102-123`) only checks if the API key matches a single global key. It does NOT resolve the key through `RBACRegistry`, does NOT check permissions per endpoint, and does NOT extract `tenant_id`. The entire RBAC system is dead code. |
| **Docker non-root** | **PROTECTED** | Dockerfile runs as `graphmind` user (`Dockerfile:25-26,42`). |
| **K8s SecurityContext** | **PROTECTED** | `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `drop: ALL` capabilities (`deployment.yaml:30-85`). Excellent. |
| **K8s ServiceAccount** | **PROTECTED** | `automountServiceAccountToken: false` (`serviceaccount.yaml:9`). |
| **Database permissions** | **MEDIUM** | Application uses a single Neo4j user (`neo4j`) which is the admin user. Should use a dedicated read-write user with limited permissions. |

---

## CATEGORY 3: Secure Defaults

| Check | Status | Details |
| --- | --- | --- |
| **Auth disabled by default** | **HIGH** | When `API_KEY` is empty (the default), authentication is completely bypassed (`main.py:107-108`). This means a fresh deployment has **zero authentication**. Debug mode also activates when auth is disabled (`main.py:230`), exposing stack traces. |
| **CORS configuration** | **PROTECTED** | Explicit origins only (`config.py:128`), `allow_credentials=False`, limited methods/headers (`main.py:234-239`). |
| **Feature flags defaults** | **PROTECTED** | Security features (injection detection) enabled by default; experimental features (webhooks, chaos) disabled (`features.py:37-55`). |
| **TLS enforcement** | **PROTECTED** | K8s ingress has `ssl-redirect: "true"` (`ingress.yaml:11`), cert-manager with Let's Encrypt (`ingress.yaml:15`). |
| **Docker Compose ports** | **MEDIUM** | Development `docker-compose.yml` exposes all service ports to host: Neo4j `7474:7474`, `7687:7687`, Qdrant `6333:6333`, Postgres `5432:5432`, Langfuse `3000:3000`, Ollama `11434:11434`. These should bind to `127.0.0.1` for local dev. |

---

## CATEGORY 4: Secrets Management

| Check | Status | Details |
| --- | --- | --- |
| **.env in .gitignore** | **PROTECTED** | `.env`, `.env.local`, `.env.production` all in `.gitignore` (`.gitignore:10-12`). |
| **Hardcoded credentials** | **PROTECTED** | No hardcoded passwords or API keys in source code. All secrets via env vars (`config.py:110-125`). |
| **K8s secrets template** | **MEDIUM** | `k8s/secret.yaml` contains **base64-encoded placeholder values** committed to git (`secret.yaml:20-40`). While they say "change-me", the file itself is committed. Should use Sealed Secrets or External Secrets Operator. The file includes clear warnings (lines 1-7). |
| **Docker secrets support** | **PROTECTED** | `docker-compose.secrets.yml` supports Docker secrets with file-based injection. |
| **Frontend credential exposure** | **N/A** | Dashboard is Streamlit (server-side Python). No client-side JavaScript with embedded secrets. |
| **API key in Streamlit** | **LOW** | `dashboard/app.py:14-22` makes API calls without authentication headers. If `API_KEY` is set, the dashboard will get 401 errors. No API key management in dashboard. |

---

## CATEGORY 5: Business Logic Flaws

| Check | Status | Details |
| --- | --- | --- |
| **Race Conditions** | **LOW** | No financial transactions. Potential race in `response_cache` and `cost_tracker` (in-memory dicts) under concurrent requests, but impact is limited to cache inconsistency, not data corruption. |
| **Parameter Tampering** | **MEDIUM** | `QueryRequest.engine` validated to `{langgraph, crewai}` (`schemas.py:96-102`). `top_k` bounded `1-100`. `IngestRequest.content` bounded to 10MB. However, `doc_type` field is NOT validated against `supported_formats` in the API schema (`schemas.py:121` - just `str`). |
| **Negative Value Injection** | **PROTECTED** | `top_k` has `ge=1` constraint. Pagination has `ge=1` for page and `ge=1, le=100` for per_page (`documents.py:49-51`). No financial fields. |
| **Payment Bypass** | **N/A** | No payment processing in GraphMind. |
| **Content-Hash Dedup Bypass** | **LOW** | Deduplication uses SHA-256 content hash (`ingest.py:40`). Resistant to collision attacks for practical purposes. |

---

## CATEGORY 6: Web & API Vulnerabilities

| Check | Status | Details |
| --- | --- | --- |
| **Broken Access Control** | **CRITICAL** | Same as RBAC finding. All routes accessible with any valid API key. No role-based route protection. |
| **JWT Attacks** | **N/A** | No JWT in the system. Uses API key (Bearer token) authentication. |
| **Mass Assignment** | **PROTECTED** | Pydantic models define exact fields. Extra fields are rejected by default in strict mode. `Settings` has `extra="ignore"` which is appropriate for config. |
| **CSRF** | **LOW** | API is stateless (no cookies/sessions). Authentication via `Authorization` header only. CORS configured. CSRF is not applicable for token-based APIs. |
| **SSRF** | **HIGH** | The `WebhookDispatcher` (`dispatcher.py:81-82`) makes HTTP requests to user-registered URLs with no URL validation. An attacker who can register webhooks could target internal services (Neo4j, Qdrant, Ollama, Langfuse). The MCP server also makes external HTTP requests. The Streamlit dashboard has a user-configurable `api_url` (`dashboard/app.py:175-179`) that could be pointed at internal services. |
| **Open Redirect** | **N/A** | No redirect functionality in the API. |

---

## CATEGORY 7: Cross-Site Attacks

| Check | Status | Details |
| --- | --- | --- |
| **XSS (Stored)** | **LOW** | API stores document content and entity descriptions in Neo4j/Qdrant. Content is returned as JSON, not rendered as HTML by the API. Streamlit uses `st.markdown()` which could render injected markdown, but Streamlit sanitizes HTML by default. |
| **XSS (Reflected/DOM)** | **LOW** | API error messages include truncated user input (`query.py:72`, `errors.py:158-159`). Returned as JSON, not HTML. Low risk. |
| **CSRF** | **PROTECTED** | Token-based auth, no cookies. See above. |
| **SSRF** | **HIGH** | See webhook finding above. |

---

## CATEGORY 8: Authentication Attacks

| Check | Status | Details |
| --- | --- | --- |
| **Brute Force** | **MEDIUM** | Rate limiter limits to 60 RPM per IP, which provides some protection. However, there's no **auth-specific** rate limiting (e.g., lockout after N failed attempts). No audit logging of failed auth attempts in the middleware (the `AuditLogger` has `log_auth_failure` but it's never called). |
| **Credential Stuffing** | **MEDIUM** | Single API key model means a leaked key gives full access. No key rotation mechanism. No key scoping (all keys are equivalent). |
| **Session Fixation** | **N/A** | No sessions. Stateless API. |
| **OAuth Misconfiguration** | **N/A** | No OAuth. |
| **API Key Timing Attack** | **LOW** | `APIKeyMiddleware` uses `!=` string comparison (`main.py:114`) which is vulnerable to timing attacks in theory. Should use `hmac.compare_digest()`. |

---

## CATEGORY 9: Network & Infrastructure

| Check | Status | Details |
| --- | --- | --- |
| **MITM** | **PROTECTED** | TLS enforced via K8s ingress with cert-manager. |
| **DoS/DDoS** | **PROTECTED** | Rate limiting (60 RPM), body size limit (15MB), bounded rate limiter memory (10K clients). K8s HPA for scaling. PDB for availability. |
| **DNS Spoofing** | **N/A** | Infrastructure-level concern, not application-level. |
| **Subdomain Takeover** | **N/A** | No subdomains in the application. |
| **Container Security** | **PROTECTED** | Non-root user, read-only filesystem, dropped capabilities, resource limits. Multi-stage Docker build minimizes attack surface. |
| **K8s Network Policies** | **MEDIUM** | No NetworkPolicy resources defined. Any pod in the cluster can reach GraphMind's internal services (Neo4j, Qdrant, etc.) |

---

## CATEGORY 10: Advanced/Modern Attacks

| Check | Status | Details |
| --- | --- | --- |
| **Prototype Pollution** | **N/A** | Python backend, not JavaScript. No prototype pollution risk. |
| **Insecure Deserialization** | **PROTECTED** | Uses `yaml.safe_load()` (`config.py:23`, `injection_detector.py:50`), not `yaml.load()`. Pydantic handles all JSON parsing. No pickle/marshal usage. |
| **XXE** | **N/A** | No XML parsing. |
| **HTTP Request Smuggling** | **LOW** | FastAPI/Uvicorn has no known smuggling vulnerabilities. Nginx ingress adds standard parsing. |
| **ReDoS (Regex DoS)** | **LOW** | Injection detector has 16 compiled regexes (`injection_detector.py:18-36`). All patterns are simple with no catastrophic backtracking risk. |

---

## CATEGORY 11: Information Leakage

| Check | Status | Details |
| --- | --- | --- |
| **Stack traces in production** | **HIGH** | When `API_KEY` is empty (default), `debug=True` is set (`main.py:230`), causing full Python tracebacks in error responses (`errors.py:114-116`). Even when debug is off, error messages may leak internal details (e.g., `graph.py:76` returns `str(exc)` which may include Neo4j connection strings). |
| **Health endpoint information** | **MEDIUM** | `/api/v1/health` returns internal service names, connection status, and error details (`health.py:34-35,47-48,59-60`). Error messages include exception text that may reveal infrastructure details. |
| **Metrics exposure** | **MEDIUM** | `/metrics` endpoint is unauthenticated (`main.py:103`), exposing request patterns, latencies, circuit breaker states, and provider information. |
| **Logging sensitive data** | **LOW** | Query questions are logged up to 200 chars (`query.py:30`, `audit.py:59`). Filenames logged during ingestion. No PII-specific masking. |

---

## CATEGORY 12: MCP Server Security

| Check | Status | Details |
| --- | --- | --- |
| **No authentication** | **HIGH** | `mcp/server.py` has zero authentication. The MCP tool calls (`call_tool()`, line 122) accept any input without validation. Anyone with access to the MCP stdio interface can ingest documents and query the knowledge base. |
| **No input validation** | **HIGH** | MCP tool arguments are not validated through Pydantic schemas. Direct dict access (`arguments["question"]`, `arguments["content"]`) without length/type checks (`server.py:142-143,181-182`). |
| **No injection detection** | **HIGH** | MCP query tool bypasses the injection detector that protects the REST API (`server.py:153` calls `run_query` directly without injection check). |

---

## Summary: Vulnerability Matrix

| Severity | Count | Key Issues |
| --- | --- | --- |
| **CRITICAL** | 2 | RBAC not enforced (dead code), Broken Access Control |
| **HIGH** | 5 | Auth disabled by default, SSRF via webhooks, info leakage in debug mode, MCP server unauthenticated, MCP bypasses injection detection |
| **MEDIUM** | 7 | Metrics/docs exposure, tenant_id spoofing, DB admin user, Docker port binding, K8s secrets template, K8s NetworkPolicy missing, brute force protection |
| **LOW** | 7 | Timing attack on API key, doc_type not validated, logging PII, dashboard no auth, cache race conditions, API key no rotation, XSS via Streamlit markdown |
| **N/A** | 12 | Not applicable to this architecture (JWT, OAuth, LDAP, XML, etc.) |

---

## Goals

What success looks like (prioritized):

| Priority | Goal |
| --- | --- |
| **MUST** | Enforce RBAC on all API routes (connect existing RBAC system to middleware) |
| **MUST** | Fix default auth configuration (require API_KEY or fail-safe) |
| **MUST** | Add SSRF protection to webhook dispatcher (URL allowlist/denylist) |
| **MUST** | Protect MCP server with input validation and injection detection |
| **MUST** | Fix information leakage in error responses and health endpoint |
| **SHOULD** | Add timing-safe API key comparison (`hmac.compare_digest`) |
| **SHOULD** | Add auth-failure rate limiting and audit logging |
| **SHOULD** | Validate `doc_type` against `supported_formats` in API schema |
| **SHOULD** | Bind Docker Compose ports to 127.0.0.1 for local dev |
| **SHOULD** | Add K8s NetworkPolicy for pod-to-pod isolation |
| **COULD** | Implement API key rotation mechanism |
| **COULD** | Add per-tenant rate limiting via RBAC |
| **COULD** | Migrate K8s secrets to Sealed Secrets or External Secrets Operator |
| **COULD** | Disable `/docs`, `/redoc` when auth is enabled |

---

## Success Criteria

Measurable outcomes:

- [ ] All 6 API routes enforce RBAC permission checks (0 unprotected routes)
- [ ] Zero stack traces leaked in production error responses
- [ ] Webhook URL validation rejects private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, localhost)
- [ ] MCP server validates all tool inputs through Pydantic schemas
- [ ] MCP query tool runs injection detection before executing queries
- [ ] API key comparison uses constant-time comparison (`hmac.compare_digest`)
- [ ] Auth failure audit events are logged with client IP
- [ ] `/metrics` endpoint requires authentication
- [ ] All 221 existing tests still pass after security changes
- [ ] New security tests cover each vulnerability fix (minimum 15 new tests)

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
| --- | --- | --- | --- | --- |
| AT-001 | RBAC enforcement | A Viewer-role API key | POST /api/v1/ingest | Returns 403 Forbidden |
| AT-002 | RBAC enforcement | An Editor-role API key | POST /api/v1/ingest | Returns 200 OK |
| AT-003 | Auth required | No API key configured | Application starts | Fails with clear error message (not silently open) |
| AT-004 | SSRF protection | Webhook URL is `http://127.0.0.1:7687` | Webhook dispatch | Rejects with "private IP not allowed" |
| AT-005 | SSRF protection | Webhook URL is `https://hooks.example.com` | Webhook dispatch | Delivers normally |
| AT-006 | Info leakage | Error occurs in production | API returns error | No stack trace, generic message, request_id only |
| AT-007 | Health endpoint | Unauthenticated request | GET /api/v1/health | Returns status only (not error details) |
| AT-008 | MCP injection | MCP query with "ignore all previous instructions" | MCP tool called | Injection detected and blocked |
| AT-009 | Timing-safe auth | Wrong API key | Authorization header sent | Constant-time comparison (verified in code review) |
| AT-010 | Tenant isolation | API key for tenant A | GET /documents?tenant_id=B | Returns 403 or empty results |
| AT-011 | Metrics auth | No API key | GET /metrics | Returns 401 |
| AT-012 | Doc type validation | `doc_type: "exe"` | POST /api/v1/ingest | Returns 400 validation error |

---

## Out of Scope

Explicitly NOT included in this security hardening:

- **Social engineering attacks** (phishing, vishing, baiting) - organizational concern, not code
- **Physical security** - not application-level
- **DDoS at network level** - handled by cloud provider / CDN
- **Client-side browser attacks** - no browser-facing frontend (Streamlit is server-side)
- **Supply chain attacks** - dependency auditing is a separate concern (already handled by CI pip-audit)
- **DNS spoofing / cache poisoning** - infrastructure-level
- **Credential stuffing at scale** - requires external WAF
- **Full penetration test** - this is a code audit, not a pentest

---

## Constraints

| Type | Constraint | Impact |
| --- | --- | --- |
| Technical | Must maintain backward compatibility with existing API key auth | RBAC enforcement adds to, not replaces, current auth |
| Technical | Python 3.11+ only | Can use modern stdlib features |
| Technical | 221 existing tests must continue to pass | All changes must be backward-compatible in test config |
| Timeline | No external timeline pressure | Can implement methodically |

---

## Technical Context

| Aspect | Value | Notes |
| --- | --- | --- |
| **Deployment Location** | `src/graphmind/` | Security fixes across api/, safety/, webhooks/, mcp/ |
| **KB Domains** | N/A | No external KB needed, all fixes are in existing codebase |
| **IaC Impact** | K8s NetworkPolicy addition + Docker Compose port binding | Minor infra changes |

---

## Assumptions

| ID | Assumption | If Wrong, Impact | Validated? |
| --- | --- | --- | --- |
| A-001 | Single API key auth is sufficient for current scale | Would need JWT/OAuth | [x] |
| A-002 | RBAC registry can remain in-memory for now | Would need DB-backed registry at scale | [ ] |
| A-003 | MCP server runs locally (not internet-facing) | Would need full auth on MCP | [ ] |
| A-004 | Streamlit dashboard is internal-only | Would need dashboard auth | [ ] |

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
| --- | --- | --- |
| Problem | 3 | Crystal clear - specific vulnerabilities identified with file:line references |
| Users | 3 | Three distinct user types with clear pain points |
| Goals | 3 | MoSCoW prioritized with 14 specific goals |
| Success | 3 | 10 measurable criteria with numbers |
| Scope | 2 | Scope is clear but some items (like K8s NetworkPolicy) need more design detail |
| **Total** | **14/15** | |

---

## Open Questions

1. Should the application **refuse to start** when `API_KEY` is not set, or should it start in read-only mode?
2. Should RBAC registry be backed by a database, or is in-memory sufficient for current scale?
3. Is the MCP server intended to be internet-facing or local-only?
4. Should we add API key rotation (key versioning) in this phase or defer?

---

## Revision History

| Version | Date | Author | Changes |
| --- | --- | --- | --- |
| 1.0 | 2026-02-20 | define-agent | Initial comprehensive security audit with 50+ attack vectors |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_SECURITY_HARDENING_AUDIT.md`

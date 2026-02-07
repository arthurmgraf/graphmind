# GraphMind Roadmap

Production hardening and feature roadmap for the GraphMind platform.
Items are organized by priority tier and engineering discipline.

---

## Tier 1 — Production-Critical

Changes required before any real workload is served in production.

### Resilience & Reliability

- [ ] **Graceful shutdown with connection cleanup** — Close Neo4j drivers, Qdrant clients, and httpx sessions in the FastAPI lifespan `shutdown` phase. Currently resources are created but never explicitly released on process termination.
- [ ] **Connection pooling for Neo4j and Qdrant** — Replace per-request instantiation with singleton pools managed at the application level via FastAPI dependency injection. Eliminates connection storms under concurrent load.
- [ ] **Retry with jitter on graph operations** — `graph_builder.add_entities()` and `add_relations()` currently fail on the first transient error. Add tenacity-based retry with exponential backoff + jitter for all Neo4j write operations.
- [ ] **Structured error responses** — Replace raw `HTTPException(detail=str(exc))` with a standard error envelope (`{"error": {"code": ..., "message": ..., "request_id": ...}}`) across all endpoints.

### Observability

- [ ] **Distributed trace propagation** — Pass `trace_id` from the Langfuse trace through every agent node, retriever call, and LLM invocation so that a single query produces a connected trace tree, not isolated spans.
- [ ] **OpenTelemetry integration** — Add OTLP exporter alongside Langfuse for vendor-neutral tracing. Enables Jaeger, Grafana Tempo, or Datadog as backends without code changes.
- [ ] **Structured logging with trace context** — Inject `request_id` and `trace_id` into every structlog event. This makes log correlation trivial in production log aggregators (ELK, Loki).
- [ ] **Alerting thresholds** — Define alert rules: primary LLM failure rate > 10%, p95 latency > 5 s, evaluation score average < 0.6. Expose these as Prometheus-compatible `/metrics` endpoint.

### Security

- [ ] **Secret rotation support** — Move API keys and database passwords to a secrets manager (AWS Secrets Manager, HashiCorp Vault, or at minimum Docker secrets). Current env vars have no rotation path.
- [ ] **Input sanitization beyond NeMo** — Add a lightweight prompt injection detector that runs synchronously before the guardrails layer. Check for common injection patterns (`ignore previous instructions`, `you are now`, `system prompt`) with regex, independent of the LLM-based NeMo check.
- [ ] **Request body size limits** — Configure FastAPI/Uvicorn max body size (default is unlimited). The Pydantic `max_length` on `IngestRequest.content` catches it at validation, but the full payload is already in memory by then.

---

## Tier 2 — Engineering Excellence

Improvements that elevate the project from "working" to "well-engineered".

### Data Engineering

- [ ] **Content-hash deduplication at storage layer** — Use the `content_hash` (SHA-256) already computed in the pipeline to check Qdrant/Neo4j for existing documents before re-ingesting. Return the existing `document_id` on duplicate.
- [ ] **Async job queue for ingestion** — Replace synchronous ingestion endpoint with a task queue (Celery + Redis or `arq`). Return a `202 Accepted` with a job ID; poll `/api/v1/jobs/{id}` for status. Large documents currently block the API worker.
- [ ] **Schema evolution for Neo4j** — Maintain a `migrations/` directory with numbered Cypher scripts. Run migrations at startup or via CLI (`graphmind-migrate`). Currently adding a new entity property requires manual graph surgery.
- [ ] **Chunk-level deduplication** — Before embedding, compute MinHash or SimHash of each chunk to detect near-duplicate content across documents. Avoids polluting the vector store with redundant information.
- [ ] **Backpressure on embedding batch size** — When `embed_batch()` receives >100 texts, split into sub-batches of 32 to avoid Ollama OOM. The current implementation sends the entire list in one HTTP request.

### AI Engineering

- [ ] **Prompt versioning and registry** — Move prompts from module-level constants (`EVALUATOR_SYSTEM`, `PLANNER_SYSTEM`) into a config-driven registry with version tracking. Log the prompt version used for each query in Langfuse for reproducibility.
- [ ] **A/B testing infrastructure** — Add an `experiment_id` parameter to `QueryRequest`. Split traffic between prompt variants or engine configurations. Record per-experiment metrics (eval score, latency, cost) for comparison.
- [ ] **Embedding model hot-swap** — Make the embedding model configurable per-collection in Qdrant. Support running multiple embedding models simultaneously and migrating collections from one model to another without downtime.
- [ ] **Evaluation regression suite** — Maintain a golden dataset of 50+ question/answer pairs with ground truth. Run the suite in CI on every prompt or model change. Fail the build if faithfulness drops below baseline.
- [ ] **Streaming responses (SSE)** — Add a `/api/v1/query/stream` endpoint using Server-Sent Events. Stream synthesizer output tokens as they arrive from the LLM instead of waiting for the full response.

### Testing

- [ ] **Integration tests with Testcontainers** — Replace mocked DB tests with real containers (Qdrant, Neo4j, Ollama) spun up in CI. Test the full ingestion-to-query pipeline end-to-end.
- [ ] **Adversarial test suite** — Add tests for: oversized documents (>10 MB), Unicode edge cases in entity names, prompt injection via query, concurrent duplicate ingestion, embedding service timeout, malformed JSON from LLM.
- [ ] **Load testing with Locust** — Write a `locustfile.py` that simulates realistic query patterns (80% simple Q&A, 15% complex analysis, 5% ingestion). Establish baseline throughput and latency targets.
- [ ] **Mutation testing** — Run `mutmut` or `cosmic-ray` against the evaluation scoring logic to verify that tests actually catch logic errors, not just structural correctness.

---

## Tier 3 — Scale & Operations

Features needed when operating at scale or in a team setting.

### Infrastructure

- [ ] **Kubernetes manifests** — Create `k8s/` directory with Deployment, Service, ConfigMap, Secret, HPA, and PDB manifests. Support horizontal scaling of the API service and vertical scaling of Ollama.
- [ ] **CI/CD pipeline** — GitHub Actions workflow with: lint (ruff), type check (mypy), unit tests, integration tests, Docker build, and automatic deploy to staging on merge to `main`.
- [ ] **Multi-environment configuration** — Support `dev`, `staging`, `production` profiles with different LLM providers, safety thresholds, and rate limits. Use Pydantic `Settings` with `env_file` per environment.
- [ ] **Backup and restore** — Automated daily backups of Neo4j (neo4j-admin dump) and Qdrant (snapshot API). Documented restore procedure with tested recovery time.
- [ ] **GPU support for Ollama** — Add `deploy.resources.reservations.devices` to docker-compose for GPU passthrough. Enable CUDA-accelerated embedding generation.

### Platform Features

- [ ] **Multi-tenancy** — Add `tenant_id` to all schemas, vector payloads, and Neo4j labels. Scope queries and ingestion to a specific tenant. Separate API keys per tenant.
- [ ] **Webhook notifications** — Fire webhooks on ingestion completion, evaluation failure, or provider fallback. Configurable per-tenant via API.
- [ ] **Document versioning** — Track document versions using `content_hash`. Support rollback to previous versions. Show diff between versions in the dashboard.
- [ ] **Conversation memory** — Add session-based context accumulation. Subsequent queries in the same session reference previous answers for multi-turn dialogue.
- [ ] **Knowledge graph visualization** — Add a Neo4j-powered graph explorer to the Streamlit dashboard. Visualize entity relationships, traversal paths, and retrieval provenance.

---

## Current State (v0.1.0)

| Dimension | Status | Score |
|-----------|--------|-------|
| Architecture | Dual-engine orchestration, hybrid retrieval, self-evaluation | 9/10 |
| LLM Routing | Circuit breaker, per-provider metrics, 3-tier cascade | 8/10 |
| Data Pipeline | Content hash, bounded concurrency, size validation | 7/10 |
| API Layer | Auth, rate limiting, request logging, CORS config | 8/10 |
| Observability | Langfuse tracing wired, real cost tracking, metrics | 7/10 |
| Security | API key auth, NeMo guardrails, input validation | 7/10 |
| Testing | 85 unit tests, comprehensive mocking, CI-ready | 7/10 |
| Infrastructure | Docker Compose, health checks on all 5 services | 8/10 |
| Documentation | README, 5 ADRs, 7 docs, architecture diagrams | 9/10 |
| **Overall** | | **7.8/10** |

Completing Tier 1 items brings the project to **9/10**.
Completing Tier 2 items brings it to **production-grade 10/10**.

# ADR-007: Async Job Queue Selection (arq over Celery)

## Status
Accepted

## Context
GraphMind's document ingestion pipeline involves several long-running, CPU-and-IO-bound operations:

1. **Document loading and chunking**: Parsing PDFs (PyMuPDF), HTML, and code files into semantic chunks (512 chars, 50 overlap).
2. **Entity and relation extraction**: LLM calls for each chunk to identify entities (7 types) and relations (6 types).
3. **Embedding generation**: Batch embedding via Ollama (`nomic-embed-text`, 768 dimensions) with retry and backoff.
4. **Graph storage**: MERGE operations into Neo4j for entities and relations.
5. **Vector storage**: Upsert into Qdrant.

Currently, the `POST /api/v1/ingest` endpoint processes documents synchronously within the HTTP request. For large documents, this can take minutes, risking HTTP timeout and blocking the API server. The `IngestionPipeline` uses `asyncio.Semaphore` for bounded concurrency within a single request but has no mechanism for background processing or job queuing.

A background job queue is needed to:
- Accept ingestion requests immediately (return a job ID) and process them asynchronously.
- Provide job status tracking (pending, running, completed, failed).
- Handle retries for transient failures (LLM rate limits, embedding timeouts).
- Support concurrency limits to avoid overwhelming Ollama and LLM providers.

Two main candidates were evaluated:

**Celery**: The de facto Python job queue. Mature, feature-rich, large ecosystem. Requires a message broker (Redis or RabbitMQ). Synchronous by default; async support via `asyncio` bridge is available but not native.

**arq**: A lightweight async-native job queue built on Redis and asyncio. Small API surface, first-class `async`/`await` support, built-in job result storage, cron-like scheduling.

## Decision
Use **arq** as the background job queue for the following reasons:

1. **Async-native design**: GraphMind is built entirely on `async`/`await` (FastAPI, async Neo4j driver, async Qdrant client, httpx AsyncClient for embeddings). arq runs jobs as native coroutines, avoiding the `sync_to_async` bridges that Celery would require.

2. **Minimal infrastructure**: arq requires only Redis, which is a single additional service. Celery would also require Redis (or RabbitMQ) plus typically a separate result backend. GraphMind already runs 5 Docker services; adding only Redis (rather than Redis + RabbitMQ) minimizes infrastructure footprint.

3. **Small API surface**: arq's API is simple: define an async function, enqueue it with `await pool.enqueue_job()`, and query results. This matches the project's preference for explicit, understandable code over framework magic.

4. **Built-in features**: Job retries with configurable backoff, job timeouts, job results stored in Redis with TTL, and health checks are all built in.

5. **Concurrency control**: arq's worker supports `max_jobs` to limit concurrent processing, replacing the current `asyncio.Semaphore` approach with a more robust mechanism.

### Integration design

```
POST /api/v1/ingest
    --> Validate request (Pydantic)
    --> Enqueue job via arq: await pool.enqueue_job("ingest_document", content, filename, doc_type)
    --> Return immediately: {"job_id": "...", "status": "pending"}

GET /api/v1/ingest/{job_id}
    --> Query arq job result
    --> Return: {"job_id": "...", "status": "completed|running|failed", "result": {...}}

arq Worker
    --> Picks up "ingest_document" job
    --> Runs IngestionPipeline.process() (existing async code, no changes needed)
    --> Stores result in Redis (auto-expires after 24h)
```

### Redis service addition

```yaml
# docker-compose.yml addition
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  restart: unless-stopped
  mem_limit: 128m
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 3
```

## Consequences
- **Non-blocking ingestion**: Large document ingestion no longer blocks the HTTP request. Clients receive a job ID immediately and poll for completion.
- **Reliability**: Failed ingestion jobs are automatically retried with backoff, handling transient LLM and embedding failures.
- **Observability**: Job status is queryable via a new API endpoint. arq logs job start/completion/failure events.
- **Async compatibility**: No sync-to-async bridges needed. The existing `IngestionPipeline.process()` coroutine runs directly in the arq worker.
- **Infrastructure cost**: One additional Docker service (Redis, ~128 MB). Redis also opens the path for shared rate limiting across API workers (see ADR-010).
- **Learning curve**: arq is less well-known than Celery. Documentation is smaller, and community support is more limited. However, the API is simple enough that this is a minor concern.
- **Not using Celery**: Celery's larger ecosystem (Flower monitoring, beat scheduler, extensive backends) is not available. If the project later needs complex workflow orchestration beyond simple job queuing, this decision may need to be revisited.

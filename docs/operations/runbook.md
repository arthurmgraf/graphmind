# Operations Runbook

This runbook covers day-to-day operational procedures for the GraphMind platform. It is intended for operators and on-call engineers responsible for keeping the system running.

---

## Table of Contents

1. [Service Start / Stop / Restart](#service-start--stop--restart)
2. [Health Check Interpretation](#health-check-interpretation)
3. [Log Query Examples](#log-query-examples)
4. [Secret Rotation Procedures](#secret-rotation-procedures)
5. [Scaling Guide](#scaling-guide)
6. [Common Troubleshooting](#common-troubleshooting)

---

## Service Start / Stop / Restart

### Infrastructure Services (Docker Compose)

GraphMind runs five infrastructure services via Docker Compose: Qdrant, Neo4j, PostgreSQL, Langfuse, and Ollama.

```bash
# Start all infrastructure services (detached)
docker compose up -d

# Verify all containers are healthy
docker compose ps

# Stop all services (preserves data volumes)
docker compose down

# Stop and DELETE all data volumes (destructive)
docker compose down -v

# Restart a single service (e.g., neo4j)
docker compose restart neo4j

# View logs for a specific service
docker compose logs -f neo4j --tail=100
```

After starting infrastructure, pull the embedding model:

```bash
make pull-models
# Equivalent to: docker exec ollama ollama pull nomic-embed-text
```

### Application Services

```bash
# Start the FastAPI server (development, with hot-reload)
make run
# Equivalent to: uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload

# Start the Streamlit dashboard
make dashboard
# Equivalent to: streamlit run src/graphmind/dashboard/app.py --server.port 8501

# Start the MCP server (stdio transport for IDE integrations)
make mcp
# Equivalent to: python -m graphmind.mcp.server
```

### Full Stack Startup Sequence

1. Start infrastructure: `make infra` (runs `docker compose up -d`, waits 10 seconds)
2. Pull embedding model: `make pull-models`
3. Start API server: `make run`
4. (Optional) Start dashboard: `make dashboard`

### Full Stack Shutdown

1. Stop the API server: `Ctrl+C` in the uvicorn terminal
2. Stop the dashboard: `Ctrl+C` in the Streamlit terminal
3. Stop infrastructure: `make infra-down` (runs `docker compose down`)

---

## Health Check Interpretation

### Endpoint

```
GET /api/v1/health
```

This endpoint is public (no API key required) and returns a JSON response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "neo4j": "healthy",
    "qdrant": "healthy",
    "ollama": "healthy"
  }
}
```

### Status Values

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| `ok` | All three services (Neo4j, Qdrant, Ollama) report healthy. | None. |
| `degraded` | One or more services are unhealthy. | Check the `services` map for the failing service and investigate. |

### Per-Service Status

| Service | Health Check Method | "healthy" Means | "unhealthy: ..." Means |
|---------|-------------------|-----------------|----------------------|
| **neo4j** | Runs `RETURN 1` via async driver session | Neo4j is accepting Bolt connections and executing Cypher. | Cannot connect or query failed. Check Neo4j container logs and password configuration. |
| **qdrant** | Calls `get_collections()` via async client | Qdrant HTTP API is responding on port 6333. | Qdrant is unreachable. Check container status and port mapping. |
| **ollama** | HTTP GET to `{OLLAMA_BASE_URL}/api/tags` | Ollama API is responding and can list models. | Ollama is unreachable or crashing. Check container status and memory limits. |

### Caching

Health check results are cached for **15 seconds** (`_CACHE_TTL = 15.0`) to prevent connection storms from load balancer probes or monitoring tools. If you need a fresh check, wait 15 seconds between calls.

### Docker-Level Health Checks

Each Docker service also has its own container-level health check:

| Service | Check Command | Interval | Start Period |
|---------|--------------|----------|--------------|
| Qdrant | `curl -sf http://localhost:6333/readyz` | 15s | 10s |
| Neo4j | `wget -qO- http://localhost:7474` | 15s | 30s |
| PostgreSQL | `pg_isready -U graphmind` | 10s | 0s |
| Langfuse | `wget -qO- http://localhost:3000/api/public/health` | 20s | 30s |
| Ollama | `curl -sf http://localhost:11434/api/tags` | 15s | 15s |

Check container health status with:

```bash
docker compose ps
# Look for "(healthy)" or "(unhealthy)" in the STATUS column
```

---

## Log Query Examples

GraphMind uses Python `logging` and `structlog` for application logs. All request logs include a `request_id` for correlation.

### Finding Errors

```bash
# Tail API server logs and filter for errors
uvicorn graphmind.api.main:app 2>&1 | grep -i "error\|exception\|failed"

# Search Docker service logs for errors
docker compose logs neo4j 2>&1 | grep -i "error\|exception"
docker compose logs qdrant 2>&1 | grep -i "error"
docker compose logs ollama 2>&1 | grep -i "error"
```

### Tracing a Request

Every request gets an `X-Request-ID` header (auto-generated 8-char UUID if not provided by the caller). Use it to trace a single request through the logs:

```bash
# Find all log lines for a specific request
uvicorn graphmind.api.main:app 2>&1 | grep "request_id=a1b2c3d4"
```

Log format for each request:

```
INFO: POST /api/v1/query 200 1523ms request_id=a1b2c3d4
```

### Checking Provider Failures

The LLM router logs warnings when a provider fails, including the provider name, elapsed time, and error:

```bash
# Filter for provider fallback events
uvicorn graphmind.api.main:app 2>&1 | grep "Provider.*failed"

# Example output:
# WARNING: Provider groq failed after 5023 ms: RateLimitError(...)
# INFO: LLM response via gemini (1200 ms)
```

### Checking Circuit Breaker State

```bash
# Filter for circuit breaker events
uvicorn graphmind.api.main:app 2>&1 | grep -i "circuit\|half-open\|probe"

# Example output:
# DEBUG: Circuit open for groq, skipping
# INFO: Half-open probe succeeded for groq, circuit closed
```

### Checking Ingestion Events

The ingestion pipeline uses structlog with bound context (document_id, filename, content_hash):

```bash
# Filter for ingestion-related events
uvicorn graphmind.api.main:app 2>&1 | grep "ingestion_\|chunking_\|entity_\|relation_\|vector_\|graph_"
```

### Langfuse Trace Exploration

For detailed LLM call tracing (inputs, outputs, token counts, costs), use the Langfuse web UI:

```
http://localhost:3000
```

Navigate to **Traces** to see per-query execution traces with spans for orchestrator start/end, including eval scores and cost.

---

## Secret Rotation Procedures

All secrets are provided via environment variables (`.env` file). No secrets are hardcoded.

### GROQ_API_KEY

1. Generate a new API key at [console.groq.com](https://console.groq.com).
2. Update `.env`: set `GROQ_API_KEY=<new-key>`.
3. Restart the API server (`Ctrl+C` then `make run`).
4. Verify by sending a test query and checking logs for `LLM response via groq`.
5. Revoke the old key in the Groq console.

### GEMINI_API_KEY

1. Generate a new API key at [aistudio.google.com](https://aistudio.google.com).
2. Update `.env`: set `GEMINI_API_KEY=<new-key>`.
3. Restart the API server.
4. Verify by temporarily disabling Groq (set `GROQ_API_KEY=""`) and sending a query.
5. Re-enable Groq and revoke the old Gemini key.

### NEO4J_PASSWORD

1. Update the Neo4j password inside the container:
   ```bash
   docker exec -it <neo4j-container> cypher-shell -u neo4j -p <old-password> \
     "ALTER CURRENT USER SET PASSWORD FROM '<old-password>' TO '<new-password>'"
   ```
2. Update `.env`: set `NEO4J_PASSWORD=<new-password>`.
3. Restart the API server and verify health check shows `neo4j: healthy`.

### POSTGRES_PASSWORD

1. Stop Langfuse: `docker compose stop langfuse`.
2. Connect to PostgreSQL and change the password:
   ```bash
   docker exec -it <postgres-container> psql -U graphmind -c \
     "ALTER USER graphmind WITH PASSWORD '<new-password>';"
   ```
3. Update `.env`: set `POSTGRES_PASSWORD=<new-password>`.
4. Restart both PostgreSQL and Langfuse: `docker compose restart postgres langfuse`.
5. Verify Langfuse is accessible at `http://localhost:3000`.

### LANGFUSE_NEXTAUTH_SECRET and LANGFUSE_SALT

1. Generate new random values:
   ```bash
   openssl rand -base64 32   # for LANGFUSE_NEXTAUTH_SECRET
   openssl rand -base64 32   # for LANGFUSE_SALT
   ```
2. Update `.env` with the new values.
3. Restart Langfuse: `docker compose restart langfuse`.
4. Note: Changing the salt will invalidate existing hashed data in Langfuse. Plan for re-authentication of Langfuse users.

### API_KEY (GraphMind API Authentication)

1. Generate a new key: `openssl rand -hex 32`.
2. Update `.env`: set `API_KEY=<new-key>`.
3. Restart the API server.
4. Update all clients to use the new `Authorization: Bearer <new-key>` header.
5. The health endpoint (`/api/v1/health`) does not require authentication and will continue working during rotation.

---

## Scaling Guide

### Horizontal API Scaling (FastAPI)

The FastAPI application is stateless. In-memory state (rate limiter windows, metrics history, cost tracker) is per-process and will be partitioned across instances.

**Steps:**

1. Run multiple uvicorn workers behind a reverse proxy:
   ```bash
   # With gunicorn + uvicorn workers
   gunicorn graphmind.api.main:app -w 4 -k uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:8000
   ```

2. Place behind a load balancer (NGINX, Traefik, AWS ALB):
   ```nginx
   upstream graphmind {
       server 127.0.0.1:8001;
       server 127.0.0.1:8002;
       server 127.0.0.1:8003;
       server 127.0.0.1:8004;
   }

   server {
       listen 80;
       location / {
           proxy_pass http://graphmind;
       }
   }
   ```

3. **Rate limiting caveat**: The in-memory `RateLimitMiddleware` uses a per-process `OrderedDict`. With multiple workers, each process tracks its own rate limits. For consistent rate limiting across processes, migrate to Redis-backed rate limiting (see ADR-010).

4. **Metrics caveat**: The `MetricsCollector` singleton is per-process. For aggregated metrics across workers, export to Prometheus or use shared storage.

### Vertical Ollama Scaling

Ollama is CPU-bound for embeddings (nomic-embed-text) and memory-bound for LLM inference (phi3:mini).

**Increase memory limit:**
```yaml
# In docker-compose.yml
ollama:
  mem_limit: 4g  # Increase from default 1g
```

**Enable GPU acceleration:**
```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**Dedicated embedding service:** For high-throughput embedding, consider running a separate Ollama instance dedicated to embedding, with its own resource allocation:

```yaml
ollama-embed:
  image: ollama/ollama:latest
  ports:
    - "11435:11434"
  mem_limit: 2g
  # Update EMBEDDINGS__BASE_URL to point here
```

### Qdrant Scaling

- **Single node**: Increase `mem_limit` in `docker-compose.yml` (default 512 MB).
- **Cluster mode**: Deploy Qdrant in cluster mode for horizontal scaling with sharding and replication. See Qdrant documentation for cluster setup.

### Neo4j Scaling

- **Community edition** (current): Single-instance only. Scale vertically by increasing heap (`NEO4J_server_memory_heap_max__size`) and page cache (`NEO4J_server_memory_pagecache_size`).
- **Enterprise edition**: Supports causal clustering for horizontal read scaling.

---

## Common Troubleshooting

### Connection Refused to Neo4j (port 7687)

**Symptoms:** Health check reports `neo4j: unhealthy: ConnectionRefusedError`. Queries fail with graph retrieval errors.

**Diagnosis:**
```bash
docker compose ps neo4j            # Check if running
docker compose logs neo4j --tail=50  # Check startup logs
```

**Common causes and fixes:**
1. **Container not running**: `docker compose up -d neo4j`
2. **Still starting** (30s start period): Wait and retry. Neo4j takes up to 30 seconds to initialize.
3. **Wrong password**: Verify `NEO4J_PASSWORD` in `.env` matches what Neo4j was initialized with. If the password was changed after initial setup, you may need to reset the volume: `docker compose down -v` then `docker compose up -d` (destructive -- deletes all graph data).
4. **Port conflict**: Another process is using port 7687. Check with `netstat -tlnp | grep 7687`.

### Connection Refused to Qdrant (port 6333)

**Symptoms:** Health check reports `qdrant: unhealthy`. Vector search returns no results.

**Diagnosis:**
```bash
docker compose ps qdrant
docker compose logs qdrant --tail=50
curl http://localhost:6333/readyz
```

**Common causes and fixes:**
1. **Container not running**: `docker compose up -d qdrant`
2. **Out of memory**: Qdrant may OOM with large collections. Increase `mem_limit` beyond 512 MB.
3. **Corrupted storage**: If Qdrant fails to start after an unclean shutdown, check logs for storage errors. As a last resort, delete the volume: `docker volume rm graphmind_qdrant_data` (destructive).

### Out of Memory (OOM)

**Symptoms:** Containers are killed by Docker (exit code 137). `docker compose ps` shows containers in "Exited (137)" state.

**Total memory budget** (all services): ~3.3 GB.

| Service | Default Limit | Can Increase To |
|---------|--------------|-----------------|
| Qdrant | 512 MB | 1-2 GB for large collections |
| Neo4j | 1 GB | 2-4 GB for large graphs |
| PostgreSQL | 256 MB | 512 MB |
| Langfuse | 512 MB | 1 GB |
| Ollama | 1 GB | 4-8 GB for larger models |

**Fix:** Increase `mem_limit` in `docker-compose.yml` for the affected service. If the host machine has limited RAM, consider stopping unused services.

### Slow Queries

**Symptoms:** Query latency exceeds 10 seconds. Dashboard shows high p95 latency.

**Diagnosis:**
1. Check which provider is being used (log line: `LLM response via <provider> (<ms> ms)`).
2. Check for circuit breaker activations (provider fallback adds latency).
3. Check the retry count in the response (retries multiply total latency).

**Common causes and fixes:**
1. **LLM provider latency**: Groq is typically fastest (100-500ms). If falling back to Ollama, expect 2-10x slower responses. Ensure `GROQ_API_KEY` is set.
2. **Retry loops**: If eval scores are consistently below 0.7, every query incurs up to 2 retries. Check if the knowledge base has relevant content for the queries being asked.
3. **Embedding latency**: Ollama embedding is CPU-bound. For faster embeddings, enable GPU or use a dedicated embedding service.
4. **Large graph traversals**: If Neo4j graph expansion is slow, reduce `retrieval.graph_hops` from 2 to 1 in `config/settings.yaml`.

### Ollama Model Not Found

**Symptoms:** Embedding calls fail with "model not found" errors.

**Fix:**
```bash
# Pull the required embedding model
make pull-models
# Or manually:
docker exec ollama ollama pull nomic-embed-text

# Verify the model is available
docker exec ollama ollama list
```

### Rate Limiting (HTTP 429)

**Symptoms:** API returns `{"error":{"code":"RATE_LIMIT_EXCEEDED","message":"Rate limit exceeded"}}` with status 429.

**Diagnosis:** The default rate limit is 60 requests per minute per client IP.

**Fixes:**
1. **Increase limit**: Set `RATE_LIMIT_RPM=120` in `.env` and restart the API server.
2. **Disable**: Set `RATE_LIMIT_RPM=0` to disable rate limiting entirely.
3. **Client-side**: Implement exponential backoff in the calling client.

### All LLM Providers Exhausted

**Symptoms:** API returns `RuntimeError: All LLM providers exhausted`.

**Diagnosis:**
1. Check if all circuit breakers are open (provider failures have tripped the circuit).
2. Check API key validity for Groq and Gemini.
3. Check if Ollama is running and has the required model.

**Fix:**
1. Verify API keys in `.env`.
2. Restart the API server to reset circuit breaker state.
3. Ensure at least one provider is reachable.

---

## Related Documentation

- [Deployment](../deployment.md) -- Infrastructure and configuration details
- [Architecture](../architecture.md) -- System design and component interactions
- [Incident Playbook](./incident-playbook.md) -- Structured incident response procedures
- [Backup and Restore](./restore.md) -- Data backup and recovery procedures

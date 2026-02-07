# Deployment and Production

This document covers infrastructure details, environment configuration, production considerations, and operational guidance for running GraphMind.

## Architecture Overview

```
                    +---------------+
                    |    Clients    |
                    | (API/MCP/UI)  |
                    +-------+-------+
                            |
               +------------+------------+
               |            |            |
      +--------v---+  +----v----+  +----v-----+
      |  FastAPI   |  |Streamlit|  |MCP Server|
      |  :8000     |  |  :8501  |  |  (stdio) |
      +--------+---+  +----+----+  +----+-----+
               |            |            |
               +------------+------------+
                            |
               +------------v------------+
               |    Orchestrator Layer   |
               |   LangGraph / CrewAI    |
               +------------+------------+
                            |
          +-----------------+-----------------+
          |                 |                 |
    +-----v-----+   +------v------+   +------v------+
    |  LLM      |   |  Retrieval  |   |  Knowledge  |
    |  Routing   |   |  Layer      |   |  Graph      |
    |Groq/Gemini|   |Vector+Graph |   |  Builder    |
    |  /Ollama  |   |  +RRF       |   |             |
    +-----------+   +------+------+   +------+------+
                           |                  |
               +-----------+------------------+
               |           |                  |
         +-----v----+ +---v----+       +------v-----+
         |  Qdrant  | | Ollama |       |   Neo4j    |
         |  :6333   | | :11434 |       |   :7687    |
         +----------+ +--------+       +------------+
```

For a detailed architecture breakdown, see [Architecture](./architecture.md).

## Local Development

```bash
# 1. Start all infrastructure (5 Docker services, ~3.3 GB RAM)
docker compose up -d

# 2. Pull embedding model
make pull-models

# 3. Start API server (with hot reload)
uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start dashboard (separate terminal)
make dashboard
```

## Docker Compose Services

All infrastructure runs via Docker Compose with 5 services:

| Service | Image | Port(s) | Memory | Purpose |
|---------|-------|---------|--------|---------|
| Qdrant | qdrant/qdrant:v1.12.1 | 6333, 6334 | 512 MB | Vector search (cosine similarity) |
| Neo4j | neo4j:5.26-community | 7474, 7687 | 1 GB | Knowledge graph (APOC plugin enabled) |
| PostgreSQL | postgres:15-alpine | 5432 | 256 MB | Langfuse backend database |
| Langfuse | langfuse/langfuse:2 | 3000 | 512 MB | LLM observability and tracing |
| Ollama | ollama/ollama:latest | 11434 | 1 GB | Local embeddings (nomic-embed-text) |

**Total memory**: approximately **3.3 GB** for all infrastructure services.

Neo4j is configured with:
- Heap max size: 512 MB
- Page cache size: 256 MB
- APOC plugin enabled for advanced graph operations

PostgreSQL includes a health check (`pg_isready`) that Langfuse depends on, ensuring Langfuse only starts after the database is ready.

## Environment Variables

All secrets are provided via `.env` file or environment variables. **No defaults are hardcoded for sensitive values.** Docker Compose uses `:?` syntax to fail fast if required variables are missing.

### Required Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for primary LLM (Llama 3.3 70B) |
| `NEO4J_PASSWORD` | Neo4j database password |
| `POSTGRES_PASSWORD` | PostgreSQL password (used by Langfuse) |
| `LANGFUSE_NEXTAUTH_SECRET` | Random secret for Langfuse auth |
| `LANGFUSE_SALT` | Random salt for Langfuse hashing |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (empty) | Google Gemini API key (enables LLM fallback) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL |
| `QDRANT_HOST` | `localhost` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USERNAME` | `neo4j` | Neo4j username |
| `POSTGRES_HOST` | `localhost` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `graphmind` | PostgreSQL database name |
| `POSTGRES_USER` | `graphmind` | PostgreSQL username |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse URL |
| `LANGFUSE_PUBLIC_KEY` | (empty) | Langfuse public key (for tracing) |
| `LANGFUSE_SECRET_KEY` | (empty) | Langfuse secret key (for tracing) |

## Production Considerations

### Security

- **CORS** is restricted to `localhost:8501` (Streamlit) and `localhost:3000` (Langfuse) -- update for production domains
- **No hardcoded secrets** -- all sensitive values require explicit `.env` configuration
- **Docker Compose fail-fast** -- `:?` syntax ensures required variables are set before services start
- **NeMo Guardrails** filter jailbreak attempts and PII in input/output via Colang flows
- **Neo4j queries** use parameterized Cypher variables (no string interpolation), preventing injection
- **Pydantic validation** on all API request/response models

### LLM Routing and Resilience

The `LLMRouter` provides automatic cascading failover:
1. **Groq** (primary) -- Llama 3.3 70B, fastest inference, free tier
2. **Gemini** (fallback) -- Gemini 2.0 Flash, reliable fallback, generous free tier
3. **Ollama** (local fallback) -- phi3:mini, offline capability, zero API cost

Each provider is lazily initialized and cached. If a provider fails, the router automatically tries the next one in the chain.

### Scaling

- **FastAPI**: Stateless; can be scaled horizontally behind a load balancer (NGINX, Traefik, etc.)
- **Qdrant**: Supports sharding and replication in cluster mode for production vector search
- **Neo4j**: Community edition is single-instance; Enterprise edition supports clustering and causal consistency
- **Ollama**: CPU-bound for embeddings; consider GPU instances or a dedicated embedding service for production throughput
- **Langfuse**: Can be pointed to an external PostgreSQL cluster for high availability

### Monitoring and Observability

GraphMind provides three layers of observability:

**Langfuse** (http://localhost:3000):
- Traces every LLM call with full input/output logging
- Tracks token usage and cost per provider
- Manages prompt versions
- Provides a web UI for trace exploration

**MetricsCollector** (`graphmind.observability.metrics`):
- Tracks query latency (average, p95 percentile)
- Monitors evaluation score distribution
- Records retry rates
- Maintains a bounded query history

**CostTracker** (`graphmind.observability.cost_tracker`):
- Records per-query token usage
- Aggregates costs by provider (Groq, Gemini, Ollama)
- Generates cost summaries

**Health endpoint** (`GET /api/v1/health`):
- Checks Neo4j connectivity (via driver verify)
- Checks Qdrant connectivity (via get_collections)
- Checks Ollama availability (via HTTP GET)
- Reports individual service status and overall system health (`ok` or `degraded`)

### Configuration

All settings are managed by Pydantic Settings with YAML overlay from `config/settings.yaml`. Environment variables override YAML values.

```yaml
retrieval:
  vector_top_k: 20       # Number of vector search results
  graph_hops: 2           # Knowledge graph expansion depth
  rrf_k: 60              # RRF fusion constant
  final_top_n: 10        # Final results after fusion

agents:
  max_retries: 2          # Max retry attempts on low eval score
  eval_threshold: 0.7     # Minimum score to accept an answer

ingestion:
  chunk_size: 512         # Characters per chunk
  chunk_overlap: 50       # Overlap between consecutive chunks
```

## Shutting Down

```bash
# Stop infrastructure (preserves data volumes)
docker compose down

# Stop and remove volumes (DELETES ALL DATA)
docker compose down -v
```

## Data Persistence

Docker named volumes persist data across container restarts:

| Volume | Contents |
|--------|----------|
| `qdrant_data` | Vector embeddings and collection metadata |
| `neo4j_data` | Knowledge graph nodes, relationships, indexes |
| `postgres_data` | Langfuse traces, evaluation data, metadata |
| `ollama_data` | Downloaded embedding models (nomic-embed-text) |

To back up data, use Docker volume backup commands or database-native export tools:
- **Neo4j**: `neo4j-admin dump` or APOC export
- **Qdrant**: Qdrant snapshots API
- **PostgreSQL**: `pg_dump`

## Related Documentation

- [Getting Started](./getting-started.md) -- Initial setup and installation
- [Running](./running.md) -- Starting all services
- [Architecture](./architecture.md) -- Detailed system design
- [Testing](./testing.md) -- Running the test suite before deploying

# Deployment & Production

## Architecture Overview

```
                    ┌─────────────┐
                    │   Clients   │
                    │ (API/MCP/UI)│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
     ┌────────▼───┐  ┌────▼────┐  ┌────▼─────┐
     │  FastAPI   │  │Streamlit│  │MCP Server│
     │  :8000     │  │  :8501  │  │  (stdio) │
     └────────┬───┘  └────┬────┘  └────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
              ┌────────────▼────────────┐
              │   Orchestrator Layer    │
              │  LangGraph / CrewAI     │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   ┌─────▼─────┐   ┌──────▼──────┐   ┌──────▼──────┐
   │  LLM      │   │  Retrieval  │   │  Knowledge  │
   │  Routing   │   │  Layer      │   │  Graph      │
   │Groq/Gemini│   │Vector+Graph │   │  Builder    │
   │  /Ollama  │   │  +RRF       │   │             │
   └───────────┘   └──────┬──────┘   └──────┬──────┘
                          │                  │
              ┌───────────┼──────────────────┤
              │           │                  │
        ┌─────▼────┐ ┌───▼────┐      ┌──────▼─────┐
        │  Qdrant  │ │ Ollama │      │   Neo4j    │
        │  :6333   │ │ :11434 │      │   :7687    │
        └──────────┘ └────────┘      └────────────┘
```

## Local Development

```bash
# 1. Start all infrastructure
docker compose up -d

# 2. Pull embedding model
make pull-models

# 3. Start API server (with hot reload)
uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start dashboard (separate terminal)
make dashboard
```

## Docker Compose Services

All infrastructure runs via Docker Compose:

| Service | Image | Port | Memory | Purpose |
|---------|-------|------|--------|---------|
| Qdrant | qdrant/qdrant:v1.12.1 | 6333, 6334 | 512MB | Vector search |
| Neo4j | neo4j:5.26-community | 7474, 7687 | 1GB | Knowledge graph |
| PostgreSQL | postgres:15-alpine | 5432 | 256MB | Langfuse backend |
| Langfuse | langfuse/langfuse:2 | 3000 | 512MB | Observability |
| Ollama | ollama/ollama:latest | 11434 | 1GB | Local embeddings |

**Total memory**: ~3.3GB for all infrastructure services.

## Environment Variables

All secrets must be set via `.env` file or environment variables. **No defaults are hardcoded for sensitive values.**

### Required

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for primary LLM |
| `NEO4J_PASSWORD` | Neo4j database password |
| `POSTGRES_PASSWORD` | PostgreSQL password (for Langfuse) |
| `LANGFUSE_NEXTAUTH_SECRET` | Random secret for Langfuse auth |
| `LANGFUSE_SALT` | Random salt for Langfuse |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (empty) | Google Gemini API key |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama base URL |
| `QDRANT_HOST` | localhost | Qdrant hostname |
| `QDRANT_PORT` | 6333 | Qdrant port |
| `NEO4J_URI` | bolt://localhost:7687 | Neo4j connection URI |
| `LANGFUSE_HOST` | http://localhost:3000 | Langfuse URL |
| `LANGFUSE_PUBLIC_KEY` | (empty) | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | (empty) | Langfuse secret key |

## Production Considerations

### Security
- CORS is restricted to `localhost:8501` (Streamlit) and `localhost:3000` (Langfuse)
- No secrets are hardcoded - all require explicit `.env` configuration
- Docker Compose uses `:?` syntax to fail fast if required vars are missing
- NeMo Guardrails filter jailbreak attempts and PII in input/output
- Neo4j queries use parameterized variables (no string interpolation)

### Scaling
- **FastAPI**: Can be scaled horizontally behind a load balancer
- **Qdrant**: Supports sharding and replication in cluster mode
- **Neo4j**: Community edition is single-instance; Enterprise supports clustering
- **Ollama**: CPU-bound; consider GPU instances for production embeddings

### Monitoring
- **Langfuse** (http://localhost:3000): Traces every LLM call, tracks costs, manages prompts
- **Metrics**: `MetricsCollector` tracks latency, p95, eval scores, retry rates
- **Cost tracking**: `CostTracker` records per-query token usage and costs by provider
- **Health endpoint**: `GET /api/v1/health` checks Neo4j, Qdrant, and Ollama connectivity

### Configuration
All settings are in `config/settings.yaml` with environment variable overrides:

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
# Stop infrastructure
docker compose down

# Stop and remove volumes (deletes all data)
docker compose down -v
```

## Data Persistence

Docker volumes persist data across restarts:
- `qdrant_data` - Vector embeddings and collections
- `neo4j_data` - Knowledge graph nodes and relationships
- `postgres_data` - Langfuse traces and metadata
- `ollama_data` - Downloaded embedding models

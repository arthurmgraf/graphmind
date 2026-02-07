# Getting Started

This guide walks you through setting up GraphMind from scratch. By the end, you will have all infrastructure running and be ready to ingest documents and query them.

## Prerequisites

- **Python 3.11+**
- **Docker** and **Docker Compose** (for infrastructure services)
- **Groq API key** (free at [console.groq.com](https://console.groq.com)) -- required for the primary LLM
- Optional: **Gemini API key** (free at [aistudio.google.com](https://aistudio.google.com)) -- used as LLM fallback

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/arthurmgraf/graphmind.git
cd graphmind
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

### 3. Install the project

```bash
# Full installation (dev + eval dependencies)
pip install -e ".[dev,eval]"

# Or just development dependencies
pip install -e ".[dev]"
```

The `dev` extra installs pytest, ruff, and mypy. The `eval` extra adds DeepEval, RAGAS, LiteLLM, and datasets for running evaluation benchmarks.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```dotenv
# Required
GROQ_API_KEY=gsk_your_actual_key_here
NEO4J_PASSWORD=your_secure_password
POSTGRES_PASSWORD=your_secure_password
LANGFUSE_NEXTAUTH_SECRET=any_random_string
LANGFUSE_SALT=any_random_string

# Optional (enables Gemini fallback)
GEMINI_API_KEY=your_gemini_api_key_here
```

**Minimum required variables:**

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Primary LLM inference (Groq Llama 3.3 70B) |
| `NEO4J_PASSWORD` | Neo4j graph database authentication |
| `POSTGRES_PASSWORD` | PostgreSQL backend for Langfuse |
| `LANGFUSE_NEXTAUTH_SECRET` | Random secret for Langfuse auth |
| `LANGFUSE_SALT` | Random salt for Langfuse hashing |

Docker Compose uses the `:?` syntax, so it will fail fast with a clear error if any required variable is missing.

### 5. Start infrastructure services

```bash
docker compose up -d
```

This starts 5 services totaling approximately **3.3 GB RAM**:

| Service | Port(s) | Memory | Purpose |
|---------|---------|--------|---------|
| Qdrant | 6333, 6334 | 512 MB | Vector database for semantic search |
| Neo4j | 7474 (UI), 7687 (Bolt) | 1 GB | Knowledge graph storage |
| PostgreSQL | 5432 | 256 MB | Langfuse backend database |
| Langfuse | 3000 | 512 MB | LLM observability and tracing |
| Ollama | 11434 | 1 GB | Local embeddings (nomic-embed-text, 768 dimensions) |

### 6. Pull the embedding model

```bash
make pull-models
# or manually:
docker exec ollama ollama pull nomic-embed-text
```

This downloads the `nomic-embed-text` model (~274 MB) into the Ollama container. This model generates 768-dimensional embeddings used for vector retrieval.

### 7. Verify services are healthy

```bash
# Check all containers are running
docker compose ps

# Quick health check via API (after starting the FastAPI server)
curl http://localhost:8000/api/v1/health
```

The health endpoint checks connectivity to Neo4j, Qdrant, and Ollama and reports each service status individually.

## Project Structure Overview

```
graphmind/
├── src/graphmind/
│   ├── agents/             # LangGraph agent nodes (planner, retriever, synthesizer, evaluator, orchestrator)
│   ├── crew/               # CrewAI agents, tasks, tools, and crew orchestrator
│   ├── api/                # FastAPI routes (query, ingest, health/stats)
│   ├── dashboard/          # Streamlit 4-page web UI
│   ├── evaluation/         # DeepEval + RAGAS evaluation suite
│   ├── ingestion/          # Document loading, semantic chunking, pipeline
│   ├── knowledge/          # Entity/relation extraction, Neo4j graph builder
│   ├── mcp/                # MCP server with 4 tools
│   ├── observability/      # Langfuse tracing, CostTracker, MetricsCollector
│   ├── retrieval/          # Vector, graph, and hybrid (RRF) retrieval + embedder
│   ├── safety/             # NeMo Guardrails with Colang flows
│   ├── config.py           # Pydantic Settings with YAML overlay
│   ├── llm_router.py       # Multi-provider LLM routing (Groq -> Gemini -> Ollama)
│   └── schemas.py          # 13 shared Pydantic models
├── tests/                  # 85 unit tests across 10 test files + 2 integration test files
├── docker-compose.yml      # 5 infrastructure services
├── Makefile                # Common commands
└── pyproject.toml          # Project metadata, dependencies, entry points
```

## Next Steps

- [Running the Application](./running.md) -- Start the API, dashboard, and MCP server
- [Ingesting Documents](./ingestion.md) -- Load documents into the knowledge base (7 formats supported)
- [Querying](./querying.md) -- Ask questions with LangGraph or CrewAI engines
- [Testing](./testing.md) -- Run the 85-test suite
- [Architecture](./architecture.md) -- Understand the system design and component interactions
- [Deployment](./deployment.md) -- Production considerations and configuration

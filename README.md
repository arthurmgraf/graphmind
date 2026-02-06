# GraphMind - Autonomous Knowledge Agent Platform

Agentic RAG system combining Knowledge Graphs with hybrid retrieval, self-evaluating LangGraph agents, and MCP server integration.

## Architecture

```
Query --> [Planner] --> [Retriever] --> [Synthesizer] --> [Evaluator] -+-> Answer
              ^              |                               |         |
              |         Vector (Qdrant)                  score < 0.7   |
              |         Graph (Neo4j)                        |         |
              |              |                          [Rewrite] -----+
              |         RRF Fusion
              +----- retry loop (max 2) -----+
```

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM Routing | Groq / Gemini / Ollama | Multi-provider with cascading fallback |
| Vector Store | Qdrant | Semantic similarity search |
| Graph DB | Neo4j | Entity-relationship traversal |
| Embeddings | Ollama (nomic-embed-text) | 768-dim local embeddings |
| Agents | LangGraph + CrewAI | Dual-engine orchestration (state machine + role-based crew) |
| Safety | NeMo Guardrails | Input/output filtering via Colang flows |
| Observability | Langfuse | Tracing, cost tracking, evaluation |
| Evaluation | DeepEval + RAGAS | Faithfulness, relevancy, groundedness metrics |
| API | FastAPI | REST endpoints for query, ingest, health |
| MCP Server | Model Context Protocol | IDE integration (Claude Code, Cursor, VS Code) |
| Dashboard | Streamlit | Web UI for queries, ingestion, and monitoring |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Groq API key (free at console.groq.com)

### Setup

```bash
# 1. Clone and install
git clone <repo-url>
cd graphmind
pip install -e ".[dev,eval]"

# 2. Start infrastructure
docker compose up -d

# 3. Pull embedding model
make pull-models

# 4. Set environment variables
export GROQ_API_KEY="your-key-here"
# Optional: export GEMINI_API_KEY="your-key-here"
```

### Run

```bash
# FastAPI server
make run
# or: graphmind

# Streamlit dashboard
make dashboard
# or: graphmind-dashboard

# MCP server (for IDE integration)
make mcp
# or: graphmind-mcp
```

### Ingest Documents

```bash
# Via CLI
graphmind-ingest path/to/document.md --type md

# Via API
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"content": "# My Doc\n\nContent here.", "filename": "doc.md", "doc_type": "md"}'
```

### Query

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is LangGraph?", "top_k": 10, "engine": "langgraph"}'

# Use CrewAI engine instead
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare CrewAI and LangGraph", "engine": "crewai"}'
```

## Project Structure

```
graphmind/
├── config/                  # YAML configuration
├── docs/adrs/              # Architecture Decision Records
├── eval/                   # Benchmark datasets and reports
├── src/graphmind/
│   ├── agents/             # LangGraph agent nodes + orchestrator
│   ├── crew/               # CrewAI agents, tasks, tools, and crew
│   ├── api/                # FastAPI routes
│   ├── dashboard/          # Streamlit web UI
│   ├── evaluation/         # DeepEval + RAGAS evaluation
│   ├── ingestion/          # Document loading, chunking, pipeline
│   ├── knowledge/          # Entity/relation extraction, graph builder
│   ├── mcp/                # MCP server
│   ├── observability/      # Langfuse tracing, cost tracking, metrics
│   ├── retrieval/          # Vector, graph, hybrid retrieval + embedder
│   ├── safety/             # NeMo Guardrails configuration
│   ├── config.py           # Pydantic Settings configuration
│   ├── llm_router.py       # Multi-provider LLM routing
│   └── schemas.py          # Shared Pydantic models
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── docker-compose.yml      # Qdrant, Neo4j, Postgres, Langfuse, Ollama
├── Makefile                # Common commands
└── pyproject.toml          # Project metadata and dependencies
```

## Development

```bash
# Run unit tests
make test

# Run all tests with coverage
make test-all

# Lint and format
make lint
make format

# Run evaluation benchmark
make eval
```

## MCP Integration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "graphmind": {
      "command": "graphmind-mcp",
      "args": []
    }
  }
}
```

Available tools: `query`, `ingest`, `graph_stats`, `health`.

## Configuration

All settings are configurable via `config/settings.yaml` or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Groq API key for primary LLM |
| `GEMINI_API_KEY` | - | Google Gemini API key (optional) |
| `NEO4J_PASSWORD` | - | Neo4j password (required) |
| `LANGFUSE_PUBLIC_KEY` | - | Langfuse public key (optional) |
| `LANGFUSE_SECRET_KEY` | - | Langfuse secret key (optional) |

## Architecture Decision Records

- [ADR-001](docs/adrs/001-multi-provider-llm-routing.md) - Multi-Provider LLM Routing
- [ADR-002](docs/adrs/002-hybrid-retrieval-with-rrf.md) - Hybrid Retrieval with RRF
- [ADR-003](docs/adrs/003-langgraph-agentic-rag.md) - LangGraph Agentic RAG
- [ADR-004](docs/adrs/004-mcp-server-integration.md) - MCP Server Integration
- [ADR-005](docs/adrs/005-crewai-dual-engine.md) - Dual Engine (LangGraph + CrewAI)

## License

MIT

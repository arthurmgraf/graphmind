# GraphMind

**Autonomous Knowledge Agent Platform** -- Agentic RAG powered by Knowledge Graphs, dual-engine orchestration, and self-evaluating retrieval pipelines.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-85%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Architecture

GraphMind runs two orchestration engines over a shared hybrid retrieval layer.
Queries enter through the API, select an engine, and pass through self-evaluation
before returning an answer.

```
                          +------------------+
                          |   FastAPI / MCP   |
                          |   Streamlit UI    |
                          +--------+---------+
                                   |
                          engine = ?
                     +-------------+-------------+
                     |                           |
          +----------v----------+     +----------v----------+
          |      LangGraph      |     |       CrewAI        |
          |   (state machine)   |     |  (role-based crew)  |
          |                     |     |                     |
          |  Planner            |     |  Research Agent     |
          |    |                |     |  Analysis Agent     |
          |  Retriever Agent    |     |  Synthesis Agent    |
          |    |                |     |  QA Agent           |
          |  Synthesizer        |     |                     |
          |    |                |     |  Sequential process |
          |  Evaluator          |     |  with shared tools  |
          |    |                |     |                     |
          |  score < 0.7 ?      |     +----------+----------+
          |   yes -> retry (x2) |                |
          |   no  -> done       |                |
          +----------+----------+     +----------+
                     |                           |
                     +-------------+-------------+
                                   |
                    +--------------v--------------+
                    |    Hybrid Retrieval Layer    |
                    |                             |
                    |  +--------+   +---------+   |
                    |  | Qdrant |   |  Neo4j  |   |
                    |  | Vector |   |  Graph  |   |
                    |  +---+----+   +----+----+   |
                    |      |             |        |
                    |      +------+------+        |
                    |             |                |
                    |        RRF Fusion            |
                    +--------------+---------------+
                                   |
                    +--------------v--------------+
                    |       LLM Router            |
                    |  Groq -> Gemini -> Ollama   |
                    |    (cascading fallback)      |
                    +-----------------------------+
```

---

## Key Features

- **Dual Orchestration Engines** -- LangGraph state machine for deterministic pipelines; CrewAI role-based crew for collaborative multi-agent reasoning. Choose per query.
- **Hybrid Retrieval with RRF** -- Combines Qdrant vector similarity search with Neo4j graph traversal, fused via Reciprocal Rank Fusion for higher recall and precision.
- **Self-Evaluation Loop** -- The LangGraph evaluator scores every answer. Scores below 0.7 trigger an automatic rewrite and re-query cycle (max 2 retries).
- **Multi-Provider LLM Routing** -- Cascading fallback across Groq, Google Gemini, and Ollama. If the primary provider is down or rate-limited, the next one picks up seamlessly.
- **Knowledge Graph Construction** -- Automated entity and relation extraction from ingested documents, building a Neo4j graph that enriches retrieval context.
- **7-Format Document Ingestion** -- Markdown, PDF, TXT, HTML, DOCX, CSV, and JSON loaders with configurable chunking strategies.
- **NeMo Guardrails** -- Input and output safety filtering via Colang flows to enforce content policies.
- **Full Observability** -- Langfuse tracing, per-request cost tracking, and metrics collection across every pipeline stage.
- **Evaluation Suite** -- DeepEval and RAGAS benchmarks measuring faithfulness, relevancy, and groundedness.
- **MCP Server** -- Model Context Protocol integration for IDE tools (Claude Code, Cursor, VS Code).
- **Streamlit Dashboard** -- Web UI for querying, document ingestion, knowledge graph statistics, and system health monitoring.
- **85 Unit Tests** passing across 10 test files.

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Orchestration | **LangGraph** + **CrewAI** | Dual-engine: state machine + role-based multi-agent crew |
| LLM Routing | **Groq** / **Gemini** / **Ollama** | Multi-provider with cascading fallback |
| Vector Store | **Qdrant** | Semantic similarity search |
| Graph Database | **Neo4j** | Entity-relationship traversal |
| Embeddings | **Ollama** (nomic-embed-text) | 768-dim local embeddings |
| Safety | **NeMo Guardrails** | Input/output filtering via Colang flows |
| Observability | **Langfuse** | Tracing, cost tracking, evaluation |
| Evaluation | **DeepEval** + **RAGAS** | Faithfulness, relevancy, groundedness metrics |
| API | **FastAPI** | REST endpoints for query, ingest, health |
| MCP Server | **Model Context Protocol** | IDE integration (Claude Code, Cursor, VS Code) |
| Dashboard | **Streamlit** | Web UI for queries, ingestion, and monitoring |
| Configuration | **Pydantic Settings** | Type-safe config with YAML overlay |
| Data Models | **Pydantic v2** | 13 shared models across the platform |
| Infrastructure | **Docker Compose** | Qdrant, Neo4j, PostgreSQL, Langfuse, Ollama |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Groq API key (free at [console.groq.com](https://console.groq.com))

### 1. Clone and install

```bash
git clone https://github.com/arthurmgraf/graphmind.git
cd graphmind
pip install -e ".[dev,eval]"
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This launches Qdrant, Neo4j, PostgreSQL, Langfuse, and Ollama.

### 3. Pull the embedding model

```bash
make pull-models
```

### 4. Configure environment variables

```bash
export GROQ_API_KEY="your-key-here"
# Optional:
export GEMINI_API_KEY="your-key-here"
export NEO4J_PASSWORD="your-password"
```

### 5. Run

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

### 6. Ingest documents

```bash
# Via CLI
graphmind-ingest path/to/document.md --type md

# Via API
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"content": "# My Doc\n\nContent here.", "filename": "doc.md", "doc_type": "md"}'
```

### 7. Query

```bash
# LangGraph engine (default)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is LangGraph?", "top_k": 10, "engine": "langgraph"}'

# CrewAI engine
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare CrewAI and LangGraph", "engine": "crewai"}'
```

---

## Project Structure

```
graphmind/
├── config/                          # YAML configuration files
├── diagrams/
│   └── generated/                   # Exported diagrams (architecture, agents, data-flow)
├── docs/
│   ├── adrs/                        # Architecture Decision Records (5 ADRs)
│   ├── getting-started.md
│   ├── running.md
│   ├── querying.md
│   ├── ingestion.md
│   ├── testing.md
│   ├── deployment.md
│   └── BUILD_REPORT.md
├── eval/                            # Benchmark datasets and reports
├── src/graphmind/
│   ├── agents/                      # LangGraph nodes + orchestrator
│   │   ├── planner.py               #   Query planning and decomposition
│   │   ├── retriever_agent.py       #   Hybrid retrieval execution
│   │   ├── synthesizer.py           #   Answer generation
│   │   ├── evaluator.py             #   Self-evaluation with retry logic
│   │   ├── orchestrator.py          #   LangGraph state machine wiring
│   │   └── states.py                #   TypedDict state definitions
│   ├── crew/                        # CrewAI multi-agent crew
│   │   ├── agents.py                #   Role definitions (Research, Analysis, Synthesis, QA)
│   │   ├── tasks.py                 #   Task specifications
│   │   ├── tools.py                 #   Shared tool wrappers
│   │   └── crew.py                  #   Crew assembly and kickoff
│   ├── api/                         # FastAPI application
│   │   ├── main.py                  #   App factory and middleware
│   │   └── routes/                  #   query, ingest, health endpoints
│   ├── dashboard/                   # Streamlit web UI
│   │   └── app.py                   #   Query, ingest, graph stats, system health
│   ├── ingestion/                   # Document processing pipeline
│   │   ├── loaders.py               #   7 format loaders (MD, PDF, TXT, HTML, DOCX, CSV, JSON)
│   │   ├── chunker.py               #   Configurable text chunking
│   │   └── pipeline.py              #   End-to-end ingestion orchestration
│   ├── knowledge/                   # Knowledge graph construction
│   │   ├── entity_extractor.py      #   LLM-based entity extraction
│   │   ├── relation_extractor.py    #   LLM-based relation extraction
│   │   ├── graph_builder.py         #   Neo4j graph population
│   │   └── graph_schema.cypher      #   Graph schema definition
│   ├── retrieval/                   # Hybrid retrieval layer
│   │   ├── embedder.py              #   Ollama embedding client
│   │   ├── vector_retriever.py      #   Qdrant vector search
│   │   ├── graph_retriever.py       #   Neo4j graph traversal
│   │   └── hybrid_retriever.py      #   RRF fusion of vector + graph results
│   ├── safety/                      # NeMo Guardrails
│   │   ├── guardrails.py            #   Guardrails integration
│   │   ├── config.py                #   Safety configuration
│   │   ├── config.yml               #   NeMo config file
│   │   └── rails.co                 #   Colang flow definitions
│   ├── observability/               # Monitoring and tracing
│   │   ├── langfuse_client.py       #   Langfuse integration
│   │   ├── cost_tracker.py          #   Per-request cost tracking
│   │   └── metrics.py               #   Metrics collection
│   ├── evaluation/                  # Evaluation framework
│   │   ├── deepeval_suite.py        #   DeepEval test suite
│   │   ├── ragas_eval.py            #   RAGAS evaluation metrics
│   │   ├── eval_models.py           #   Evaluation data models
│   │   └── benchmark.py             #   Benchmark runner
│   ├── mcp/                         # Model Context Protocol server
│   │   └── server.py                #   MCP tool definitions
│   ├── config.py                    # Pydantic Settings with YAML overlay
│   ├── llm_router.py               # Multi-provider LLM routing with fallback
│   └── schemas.py                   # 13 shared Pydantic models
├── tests/
│   ├── unit/                        # 85 unit tests across 10 files
│   │   ├── test_agents.py
│   │   ├── test_chunker.py
│   │   ├── test_config.py
│   │   ├── test_cost_tracker.py
│   │   ├── test_crew.py
│   │   ├── test_deepeval_suite.py
│   │   ├── test_hybrid_retriever.py
│   │   ├── test_loaders.py
│   │   ├── test_metrics.py
│   │   └── test_schemas.py
│   ├── integration/                 # Integration tests
│   └── conftest.py                  # Shared fixtures
├── docker-compose.yml               # Qdrant, Neo4j, PostgreSQL, Langfuse, Ollama
├── Makefile                         # Common commands
└── pyproject.toml                   # Project metadata and dependencies
```

---

## Development

### Testing

```bash
# Run all unit tests (85 tests across 10 files)
make test

# Run with coverage report
make test-all

# Run a specific test file
pytest tests/unit/test_agents.py -v
```

### Linting and Formatting

```bash
make lint
make format
```

### Evaluation Benchmark

```bash
# Run DeepEval + RAGAS evaluation suite
make eval
```

---

## Orchestration Engines

GraphMind provides two orchestration engines. Choose per query via the `engine` parameter.

### LangGraph -- State Machine Pipeline

A deterministic, graph-based pipeline where each node performs a single step. The evaluator node implements a self-correction loop: if the answer scores below **0.7**, it rewrites the query and retries (up to **2 times**).

| Node | Responsibility |
|---|---|
| **Planner** | Decomposes the query into sub-questions and a retrieval strategy |
| **Retriever Agent** | Executes hybrid retrieval (vector + graph + RRF) |
| **Synthesizer** | Generates a grounded answer from retrieved context |
| **Evaluator** | Scores the answer; triggers retry loop if quality is insufficient |

### CrewAI -- Role-Based Multi-Agent Crew

A collaborative crew of specialized agents that execute tasks sequentially, delegating and sharing context through CrewAI's built-in mechanisms.

| Agent | Role |
|---|---|
| **Research Agent** | Retrieves and ranks relevant information |
| **Analysis Agent** | Identifies patterns, contradictions, and gaps |
| **Synthesis Agent** | Composes a coherent, well-structured answer |
| **QA Agent** | Validates accuracy and completeness |

### When to Use Which

| Criteria | LangGraph | CrewAI |
|---|---|---|
| Deterministic flow | Yes | No |
| Self-evaluation retry | Built-in | Via QA agent |
| Multi-perspective analysis | Single pipeline | Multiple agents collaborate |
| Best for | Factual Q&A, precise retrieval | Complex analysis, comparison tasks |

---

## MCP Integration

GraphMind exposes an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server for integration with AI-powered IDEs and tools.

### Configuration

Add the following to your MCP client settings (Claude Code, Cursor, VS Code, etc.):

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

### Available Tools

| Tool | Description |
|---|---|
| `query` | Ask a question against the knowledge base |
| `ingest` | Ingest a document into the system |
| `graph_stats` | Retrieve knowledge graph statistics (entities, relations, counts) |
| `health` | Check system health status of all components |

---

## Documentation

| Document | Description |
|---|---|
| [Getting Started](docs/getting-started.md) | Installation and initial setup guide |
| [Running](docs/running.md) | How to run the API, dashboard, and MCP server |
| [Querying](docs/querying.md) | Query API reference and engine selection |
| [Ingestion](docs/ingestion.md) | Document ingestion formats and pipeline details |
| [Testing](docs/testing.md) | Test suite structure, running tests, writing new tests |
| [Deployment](docs/deployment.md) | Production deployment guide |
| [Build Report](docs/BUILD_REPORT.md) | Full project build report |

---

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [ADR-001](docs/adrs/001-multi-provider-llm-routing.md) | Multi-Provider LLM Routing with cascading fallback |
| [ADR-002](docs/adrs/002-hybrid-retrieval-with-rrf.md) | Hybrid Retrieval with Reciprocal Rank Fusion |
| [ADR-003](docs/adrs/003-langgraph-agentic-rag.md) | LangGraph Agentic RAG pipeline design |
| [ADR-004](docs/adrs/004-mcp-server-integration.md) | MCP Server Integration for IDE tooling |
| [ADR-005](docs/adrs/005-crewai-dual-engine.md) | Dual Engine architecture (LangGraph + CrewAI) |

---

## Diagrams

Architecture and data-flow diagrams are maintained as Excalidraw source files and exported
to the `diagrams/generated/` directory, organized into three categories:

```
diagrams/generated/
├── agents/          # Agent interaction and delegation flows
├── architecture/    # High-level system architecture
└── data-flow/       # Data ingestion and retrieval pipelines
```

---

## Configuration

All settings are managed via `config/settings.yaml` with environment variable overrides.
Configuration is loaded through Pydantic Settings, providing type safety and validation.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | -- | Groq API key (primary LLM provider) |
| `GEMINI_API_KEY` | No | -- | Google Gemini API key (fallback LLM) |
| `NEO4J_PASSWORD` | Yes | -- | Neo4j database password |
| `LANGFUSE_PUBLIC_KEY` | No | -- | Langfuse public key for observability |
| `LANGFUSE_SECRET_KEY` | No | -- | Langfuse secret key for observability |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant vector store URL |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j connection URI |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama API base URL |

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Author

**Arthur Maia Graf** -- [arthurmgraf@hotmail.com](mailto:arthurmgraf@hotmail.com)

GitHub: [github.com/arthurmgraf/graphmind](https://github.com/arthurmgraf/graphmind)

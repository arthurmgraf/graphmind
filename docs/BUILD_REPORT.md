# GraphMind - Build Report

## Overview

GraphMind is an Autonomous Knowledge Agent Platform that implements Agentic RAG (Retrieval-Augmented Generation) with Knowledge Graphs, hybrid retrieval, self-evaluating agents, and MCP server integration. It features a dual orchestration engine (LangGraph + CrewAI), 7 document format support, and a comprehensive observability stack.

**Repository**: https://github.com/arthurmgraf/graphmind

## Key Metrics

| Metric | Value |
|--------|-------|
| Unit tests | 85 passing across 10 test files |
| Integration tests | 5 across 2 test files |
| Document formats | 7 (PDF, MD, HTML, TXT, PY, TS, JS) |
| Docker services | 5 (~3.3 GB RAM) |
| Pydantic models | 13 shared schemas |
| API endpoints | 4 (query, ingest, health, stats) |
| MCP tools | 4 (query, ingest, graph_stats, health) |
| Dashboard pages | 4 (Query, Ingest, Knowledge Graph, System) |
| CLI entry points | 5 (graphmind, graphmind-dashboard, graphmind-mcp, graphmind-ingest, graphmind-eval) |

## Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Primary LLM | Groq (Llama 3.3 70B) | Fastest inference, free tier, high quality |
| Secondary LLM | Google Gemini 2.0 Flash | Reliable fallback, generous free tier |
| Fallback LLM | Ollama (phi3:mini) | Offline capability, zero cost |
| Vector Store | Qdrant v1.12.1 | High-performance vector search, gRPC support |
| Graph Database | Neo4j 5.26-community | Mature graph DB, Cypher query language, APOC plugin |
| Embeddings | Ollama (nomic-embed-text) | Local, 768 dimensions, no API costs |
| Agent Framework | LangGraph (default) | State machines with cyclic graphs for retry loops |
| Multi-Agent | CrewAI (via engine param) | Role-based crew with 4 agents, 3 custom tools |
| Safety | NVIDIA NeMo Guardrails | Colang flows for jailbreak/PII filtering |
| Observability | Langfuse v2 | Open-source tracing, cost tracking |
| Cost Tracking | CostTracker | Per-query token usage, provider aggregation |
| Metrics | MetricsCollector | Latency, p95, retry rate, query history |
| Evaluation | DeepEval + RAGAS | LLM-as-judge: relevancy, groundedness, completeness |
| API | FastAPI | Async, auto-docs (Swagger/ReDoc), Pydantic validation |
| Dashboard | Streamlit | 4-page UI: Query, Ingest, Knowledge Graph, System |
| MCP | Model Context Protocol | IDE integration (Claude Code, Cursor, VS Code) |
| Config | Pydantic Settings + YAML | Type-safe settings with env var overrides |
| Infra | Docker Compose | 5 services: Qdrant, Neo4j, PostgreSQL, Langfuse, Ollama |
| Build System | Hatchling | PEP 517 build backend |
| Linting | Ruff | Fast Python linter/formatter (line length 100, Python 3.11 target) |
| Type Checking | mypy | Strict mode with `disallow_untyped_defs` |
| Testing | pytest + pytest-asyncio | Auto async mode, coverage reporting |

## Architecture Decisions

1. **Multi-Provider LLM Routing** (ADR-001): Cascading fallback through Groq -> Gemini -> Ollama ensures resilience. Providers are lazily initialized and cached.
2. **Hybrid Retrieval with RRF** (ADR-002): Combines vector similarity (Qdrant, top-k=20) and graph traversal (Neo4j, 2 hops) via Reciprocal Rank Fusion (k=60).
3. **LangGraph Agentic RAG** (ADR-003): Self-evaluating pipeline with conditional retry loop. Evaluation scores answers on relevancy (40%) + groundedness (40%) + completeness (20%) with threshold 0.7.
4. **MCP Server** (ADR-004): Stdio-based MCP server enables IDE integration with 4 tools.
5. **Dual Engine** (ADR-005): CrewAI as alternative engine with 4 role-based agents (Research Planner, Knowledge Retriever, Answer Synthesizer, Quality Evaluator) and 3 custom tools (HybridSearchTool, GraphExpansionTool, EvaluateAnswerTool).

## Module Inventory

### Core (3 files)
- `config.py` -- Pydantic Settings with YAML overlay, 9 nested config sections (LLM primary/secondary/fallback, embeddings, vector store, graph DB, retrieval, agents, ingestion)
- `schemas.py` -- 13 shared Pydantic models (Entity, EntityType, Relation, DocumentChunk, DocumentMetadata, RetrievalResult, Citation, QueryRequest, QueryResponse, IngestRequest, IngestResponse, GraphStats, HealthResponse)
- `llm_router.py` -- LLMRouter with 3-provider cascade (Groq/Gemini/Ollama), lazy initialization, sync and async invoke

### Ingestion (4 files)
- `loaders.py` -- DocumentLoader supporting 7 formats: PDF (PyMuPDF), MD, HTML, TXT, PY, TS, JS
- `chunker.py` -- SemanticChunker with paragraph/sentence splitting, 512-char chunks, 50-char overlap
- `pipeline.py` -- IngestionPipeline orchestrating load -> chunk -> extract -> embed -> store
- `__init__.py`

### Knowledge Graph (5 files)
- `entity_extractor.py` -- LLM-based entity extraction (concept, technology, person, organization, framework, pattern, other)
- `relation_extractor.py` -- LLM-based relation extraction (uses, depends_on, extends, implements, part_of, related_to)
- `graph_builder.py` -- Neo4j MERGE operations for idempotent entity/relation upserts, stats retrieval
- `graph_schema.cypher` -- DDL: uniqueness constraints, indexes, full-text search
- `__init__.py`

### Retrieval (5 files)
- `embedder.py` -- Ollama embedding client (async, batch support, nomic-embed-text, 768 dimensions)
- `vector_retriever.py` -- Qdrant vector search with collection management (cosine similarity)
- `graph_retriever.py` -- Neo4j graph expansion (configurable hops) and text search
- `hybrid_retriever.py` -- RRF fusion of vector + graph results with deduplication
- `__init__.py`

### Agents / LangGraph (7 files)
- `states.py` -- AgentState TypedDict with 12 fields
- `planner.py` -- Query decomposition into 1-4 sub-questions
- `retriever_agent.py` -- Hybrid retrieval for each sub-question
- `synthesizer.py` -- Context-grounded answer generation with citations
- `evaluator.py` -- LLM-as-judge scoring: relevancy (40%) + groundedness (40%) + completeness (20%)
- `orchestrator.py` -- LangGraph StateGraph with conditional retry loop, engine routing to CrewAI
- `__init__.py`

### Crew / CrewAI (5 files)
- `tools.py` -- 3 custom CrewAI tools: HybridSearchTool, GraphExpansionTool, EvaluateAnswerTool
- `agents.py` -- 4 agent factory functions: Research Planner, Knowledge Retriever, Answer Synthesizer, Quality Evaluator
- `tasks.py` -- 4 task factory functions: planning, retrieval, synthesis, evaluation (with context chains)
- `crew.py` -- GraphMindCrew orchestrator with sequential process, retry loop, question rewriting
- `__init__.py`

### Safety (4 files)
- `guardrails.py` -- NeMo Guardrails wrapper with `check_input` and `check_output` async functions
- `config.py` -- Registers Groq as NeMo Guardrails LLM provider
- `config.yml` -- NeMo Guardrails YAML config (Groq/Llama 3.3 70B, input/output flows)
- `rails.co` -- Colang flow definitions: jailbreak detection, PII filtering, knowledge question routing

### Observability (4 files)
- `langfuse_client.py` -- Langfuse tracing with context manager and span logging
- `cost_tracker.py` -- Per-query cost tracking with provider aggregation and summaries
- `metrics.py` -- MetricsCollector with latency avg/p95, retry rate, eval score tracking, bounded history
- `__init__.py`

### Evaluation (5 files)
- `eval_models.py` -- GroqEvalModel and GeminiEvalModel wrappers for LLM-as-judge
- `deepeval_suite.py` -- LLM-as-judge evaluation with 3 dimensions (relevancy, groundedness, completeness)
- `ragas_eval.py` -- RAGAS framework integration for faithfulness and relevancy
- `benchmark.py` -- Benchmark runner with CLI entry point, JSONL dataset loading, report generation
- `__init__.py`

### API (6 files)
- `main.py` -- FastAPI app with CORS, lifespan events, uvicorn runner
- `routes/query.py` -- POST /api/v1/query (supports `engine` param for LangGraph/CrewAI)
- `routes/ingest.py` -- POST /api/v1/ingest (7 document formats)
- `routes/health.py` -- GET /api/v1/health (Neo4j, Qdrant, Ollama checks), GET /api/v1/stats
- `routes/__init__.py`
- `__init__.py`

### MCP Server (2 files)
- `server.py` -- MCP server with 4 tools: query (with engine param), ingest, graph_stats, health
- `__init__.py`

### Dashboard (2 files)
- `app.py` -- Streamlit UI with 4 pages (Query, Ingest, Knowledge Graph, System), configurable API URL
- `__init__.py`

## Test Coverage

### Unit Tests (85 tests, 10 files)

| File | Tests | What It Validates |
|------|-------|-------------------|
| `test_config.py` | 9 | Settings defaults, lru_cache caching, nested config sections |
| `test_schemas.py` | 11 | All 13 Pydantic models: creation, defaults, auto-UUIDs, enums |
| `test_chunker.py` | 7 | Empty text, long text, metadata, sequential indices, unique IDs, overlap |
| `test_loaders.py` | 9 | All 7 format loading, file vs. content, code wrapping, error handling |
| `test_cost_tracker.py` | 6 | Recording, aggregation, summary structure, provider grouping |
| `test_metrics.py` | 7 | Avg latency, p95, retry rate, history limits, recent queries |
| `test_deepeval_suite.py` | 7 | JSON parsing, markdown fences, fallback, threshold, reports |
| `test_hybrid_retriever.py` | 5 | RRF formula, overlap dedup, empty lists, score correctness |
| `test_agents.py` | 14 | Planner decomposition, synthesis, eval scoring/fallback, retry, rewrite, graph building |
| `test_crew.py` | 10 | 3 CrewAI tools, 4 agent factories, 4 task factories, context chains, error handling |

### Integration Tests (2 files)

| File | Tests | What It Validates |
|------|-------|-------------------|
| `test_ingestion_pipeline.py` | 3 | End-to-end load + chunk for MD, long docs, code |
| `test_eval_suite.py` | 2 | Benchmark evaluation from JSONL, missing file errors |

## Infrastructure

Docker Compose provides 5 services totaling ~3.3 GB RAM:

| Service | Image | Port(s) | Memory | Details |
|---------|-------|---------|--------|---------|
| Qdrant | qdrant/qdrant:v1.12.1 | 6333, 6334 | 512 MB | Vector search, cosine similarity |
| Neo4j | neo4j:5.26-community | 7474, 7687 | 1 GB | APOC plugin, heap 512 MB, page cache 256 MB |
| PostgreSQL | postgres:15-alpine | 5432 | 256 MB | Langfuse backend, health check enabled |
| Langfuse | langfuse/langfuse:2 | 3000 | 512 MB | Depends on PostgreSQL health check |
| Ollama | ollama/ollama:latest | 11434 | 1 GB | nomic-embed-text (768 dimensions) |

4 Docker named volumes: `qdrant_data`, `neo4j_data`, `postgres_data`, `ollama_data`.

## File Count Summary

| Category | Count |
|----------|-------|
| Source code files | 51 |
| Unit test files | 10 |
| Integration test files | 2 |
| Configuration files | 3 (settings.yaml, docker-compose.yml, pyproject.toml) |
| Safety config files | 3 (config.py, config.yml, rails.co) |
| Documentation files | 8 (README, BUILD_REPORT, architecture, getting-started, running, querying, ingestion, testing, deployment) |
| Infrastructure files | 2 (docker-compose.yml, Makefile) |
| Evaluation data | 1 (benchmark_dataset.jsonl with 10 entries) |

## Entry Points

| Command | Module | Purpose |
|---------|--------|---------|
| `graphmind` | `graphmind.api.main:run` | Start FastAPI server (port 8000) |
| `graphmind-dashboard` | `graphmind.dashboard.app:main` | Start Streamlit dashboard (port 8501) |
| `graphmind-mcp` | `graphmind.mcp.server:main` | Start MCP server (stdio transport) |
| `graphmind-ingest` | `graphmind.ingestion.pipeline:cli` | CLI document ingestion |
| `graphmind-eval` | `graphmind.evaluation.benchmark:cli` | Run evaluation benchmark |

## Documentation

| Document | Purpose |
|----------|---------|
| [Getting Started](./getting-started.md) | Installation, environment setup, infrastructure |
| [Running](./running.md) | Starting API, dashboard, MCP server |
| [Querying](./querying.md) | Dual engine usage, pipeline details, evaluation |
| [Ingestion](./ingestion.md) | 7 formats, pipeline stages, configuration |
| [Testing](./testing.md) | 85 unit tests, fixtures, linting, benchmarks |
| [Deployment](./deployment.md) | Docker services, env vars, production guidance |
| [Architecture](./architecture.md) | System layers, component interaction, tech stack |

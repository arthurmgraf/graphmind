# GraphMind - Build Report

## Overview

GraphMind is an Autonomous Knowledge Agent Platform that implements Agentic RAG (Retrieval-Augmented Generation) with Knowledge Graphs, hybrid retrieval, self-evaluating LangGraph agents, and MCP server integration.

## Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Primary LLM | Groq (Llama 3.3 70B) | Fastest inference, free tier, high quality |
| Secondary LLM | Google Gemini 2.0 Flash | Reliable fallback, generous free tier |
| Fallback LLM | Ollama (phi3:mini) | Offline capability, zero cost |
| Vector Store | Qdrant | High-performance vector search, gRPC support |
| Graph Database | Neo4j | Mature graph DB, Cypher query language, APOC |
| Embeddings | Ollama (nomic-embed-text) | Local, 768 dimensions, no API costs |
| Agent Framework | LangGraph | State machines with cyclic graphs for retry loops |
| Safety | NVIDIA NeMo Guardrails | Colang flows for input/output filtering |
| Observability | Langfuse | Open-source tracing, cost tracking |
| Evaluation | DeepEval + RAGAS | Faithfulness, relevancy, groundedness metrics |
| API | FastAPI | Async, auto-docs, Pydantic validation |
| Dashboard | Streamlit | Rapid prototyping, built-in charting |
| MCP | Model Context Protocol | IDE integration standard |
| Config | Pydantic Settings + YAML | Type-safe, env var overrides |
| Infra | Docker Compose | 5 services: Qdrant, Neo4j, Postgres, Langfuse, Ollama |

## Architecture Decisions

1. **Multi-Provider LLM Routing** (ADR-001): Cascading fallback through Groq -> Gemini -> Ollama ensures resilience.
2. **Hybrid Retrieval with RRF** (ADR-002): Combines vector similarity and graph traversal via Reciprocal Rank Fusion.
3. **LangGraph Agentic RAG** (ADR-003): Self-evaluating pipeline with retry loop improves answer quality.
4. **MCP Server** (ADR-004): Stdio-based MCP server enables IDE integration.

## Module Inventory

### Core (3 files)
- `config.py` - Pydantic Settings with YAML overlay, nested config sections
- `schemas.py` - 13 shared Pydantic models (Entity, Relation, DocumentChunk, QueryRequest/Response, etc.)
- `llm_router.py` - LLMRouter with 3-provider cascade, sync/async invoke

### Ingestion (4 files)
- `loaders.py` - DocumentLoader supporting PDF, MD, HTML, TXT, PY, TS, JS
- `chunker.py` - SemanticChunker with paragraph splitting, sentence merging, overlap
- `pipeline.py` - IngestionPipeline orchestrating load -> chunk -> extract -> store
- `__init__.py`

### Knowledge Graph (5 files)
- `entity_extractor.py` - LLM-based entity extraction with structured output
- `relation_extractor.py` - LLM-based relation extraction with validation
- `graph_builder.py` - Neo4j MERGE operations for entities and relations
- `graph_schema.cypher` - DDL: uniqueness constraint, indexes, full-text search
- `__init__.py`

### Retrieval (5 files)
- `embedder.py` - Ollama embedding client (async, batch support)
- `vector_retriever.py` - Qdrant vector search with collection management
- `graph_retriever.py` - Neo4j graph expansion and text search
- `hybrid_retriever.py` - RRF fusion of vector + graph results
- `__init__.py`

### Agents (7 files)
- `states.py` - AgentState TypedDict with 12 fields
- `planner.py` - Query decomposition into sub-questions (max 4)
- `retriever_agent.py` - Hybrid retrieval for each sub-question
- `synthesizer.py` - Context-grounded answer generation with citations
- `evaluator.py` - LLM-based scoring (relevancy, groundedness, completeness)
- `orchestrator.py` - LangGraph state machine with conditional retry loop
- `__init__.py`

### Safety (4 files)
- `guardrails.py` - NeMo Guardrails wrapper for input/output checking
- `config.py` - Guardrails provider configuration
- `config.yml` - NeMo Guardrails YAML config
- `rails.co` - Colang flow definitions

### Observability (4 files)
- `langfuse_client.py` - Langfuse tracing with context manager and span logging
- `cost_tracker.py` - Per-query cost tracking with provider aggregation
- `metrics.py` - MetricsCollector with latency, p95, retry rate, history
- `__init__.py`

### Evaluation (5 files)
- `eval_models.py` - GroqEvalModel and GeminiEvalModel wrappers
- `deepeval_suite.py` - LLM-as-judge evaluation with 3 dimensions
- `ragas_eval.py` - RAGAS framework integration
- `benchmark.py` - Benchmark runner with CLI and report generation
- `__init__.py`

### API (6 files)
- `main.py` - FastAPI app with CORS, lifespan, uvicorn runner
- `routes/query.py` - POST /api/v1/query
- `routes/ingest.py` - POST /api/v1/ingest
- `routes/health.py` - GET /api/v1/health, GET /api/v1/stats
- `routes/__init__.py`
- `__init__.py`

### MCP Server (2 files)
- `server.py` - MCP server with 4 tools (query, ingest, graph_stats, health)
- `__init__.py`

### Dashboard (2 files)
- `app.py` - Streamlit UI with 4 pages (Query, Ingest, Knowledge Graph, System)
- `__init__.py`

## Test Coverage

### Unit Tests (8 files)
- `test_config.py` - Settings defaults and caching
- `test_schemas.py` - All 13 Pydantic model creation and defaults
- `test_chunker.py` - Chunking edge cases, metadata, indices
- `test_loaders.py` - All format loading, file vs content, error handling
- `test_cost_tracker.py` - Recording, aggregation, summary
- `test_metrics.py` - Latency, p95, retry rate, history limits
- `test_deepeval_suite.py` - JSON parsing, fallbacks, report generation
- `test_hybrid_retriever.py` - RRF fusion formula, deduplication, edge cases
- `test_agents.py` - Planner decomposition, evaluator scoring, retry logic

### Integration Tests (2 files)
- `test_ingestion_pipeline.py` - End-to-end load + chunk for various formats
- `test_eval_suite.py` - Benchmark evaluation from JSONL files

## Infrastructure

Docker Compose provides 5 services:
- **Qdrant** v1.12.1 (ports 6333/6334, 512MB)
- **Neo4j** 5.26-community (ports 7474/7687, 1GB, APOC plugin)
- **PostgreSQL** 15-alpine (port 5432, 256MB, Langfuse backend)
- **Langfuse** v2 (port 3000, 512MB)
- **Ollama** latest (port 11434, 1GB)

## File Count Summary

| Category | Files |
|----------|-------|
| Source code | 40+ |
| Tests | 10 |
| Configuration | 3 (settings.yaml, docker-compose.yml, pyproject.toml) |
| Documentation | 6 (README, BUILD_REPORT, 4 ADRs) |
| Infrastructure | 2 (docker-compose.yml, Makefile) |
| Evaluation data | 1 (benchmark_dataset.jsonl with 10 entries) |

## Entry Points

| Command | Module | Purpose |
|---------|--------|---------|
| `graphmind` | `graphmind.api.main:run` | Start FastAPI server |
| `graphmind-mcp` | `graphmind.mcp.server:main` | Start MCP server |
| `graphmind-ingest` | `graphmind.ingestion.pipeline:cli` | CLI document ingestion |
| `graphmind-eval` | `graphmind.evaluation.benchmark:cli` | Run evaluation benchmark |
| `graphmind-dashboard` | `graphmind.dashboard.app:main` | Start Streamlit dashboard |

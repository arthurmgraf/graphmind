# Architecture Overview

This document provides a comprehensive view of GraphMind's system architecture, component interactions, dual engine design, and technology choices.

## System Layers

```
+=====================================================================+
|                         CLIENT LAYER                                 |
|  +-------------+    +------------------+    +--------------------+   |
|  | REST API    |    | Streamlit        |    | MCP Server         |   |
|  | (curl, SDK) |    | Dashboard :8501  |    | (Claude Code,      |   |
|  |             |    | 4 pages          |    |  Cursor, VS Code)  |   |
|  +------+------+    +--------+---------+    +---------+----------+   |
|         |                    |                        |              |
+=========|====================|========================|==============+
          |                    |                        |
+=========v====================v========================v==============+
|                         API LAYER                                    |
|  +----------------------------------------------------------------+  |
|  |                    FastAPI :8000                                |  |
|  |  POST /api/v1/query   POST /api/v1/ingest                     |  |
|  |  GET  /api/v1/health  GET  /api/v1/stats                      |  |
|  |  Pydantic models (13) | CORS | Swagger/ReDoc                  |  |
|  +-------------------------------+--------------------------------+  |
|                                  |                                   |
+==========|=======================|===================================+
           |                       |
+==========v=======================v===================================+
|                     SAFETY LAYER                                     |
|  +----------------------------------------------------------------+  |
|  |                NeMo Guardrails                                 |  |
|  |  Colang flows: jailbreak detection, PII filtering              |  |
|  |  Provider: Groq (Llama 3.3 70B)                               |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
+======================================================================+
           |
+==========v===========================================================+
|                   ORCHESTRATION LAYER                                 |
|                                                                      |
|  +----------------------------+  +--------------------------------+  |
|  |     LangGraph (default)    |  |      CrewAI (via engine)       |  |
|  |                            |  |                                |  |
|  | Plan -> Retrieve ->        |  | Research Planner               |  |
|  |   Synthesize -> Evaluate   |  | Knowledge Retriever            |  |
|  |        |                   |  | Answer Synthesizer             |  |
|  |   [Rewrite if < 0.7]      |  | Quality Evaluator              |  |
|  |                            |  |                                |  |
|  | StateGraph + conditional   |  | Sequential process +           |  |
|  | edges + retry loop         |  | context chains + retry         |  |
|  +----------------------------+  +--------------------------------+  |
|                                                                      |
+======================================================================+
           |                    |                    |
+==========v===========+========v==========+=========v=================+
|     LLM ROUTING      |   RETRIEVAL       |   KNOWLEDGE GRAPH        |
|                       |                   |   BUILDING               |
| Groq (primary)        | Vector Search     | Entity Extraction        |
|   Llama 3.3 70B       |   Qdrant top-20   |   7 entity types         |
|                       |   cosine sim.     |                          |
| Gemini (fallback)     |                   | Relation Extraction      |
|   Gemini 2.0 Flash    | Graph Expansion   |   6 relation types       |
|                       |   Neo4j 2-hop     |                          |
| Ollama (local)        |                   | Graph Builder            |
|   phi3:mini           | RRF Fusion        |   Neo4j MERGE ops        |
|                       |   k=60            |                          |
+-----------------------+-------------------+--------------------------+
           |                    |                    |
+==========v===========+========v==========+=========v=================+
|     EMBEDDING         |   VECTOR STORE    |   GRAPH DATABASE         |
|                       |                   |                          |
| Ollama                | Qdrant v1.12.1    | Neo4j 5.26-community     |
| nomic-embed-text      | :6333             | :7474 (UI) :7687 (Bolt)  |
| 768 dimensions        | cosine similarity | APOC plugin              |
| :11434                | graphmind_docs    | Cypher queries           |
+-----------------------+-------------------+--------------------------+
                                |
+=======================================================================+
|                     OBSERVABILITY LAYER                                |
|                                                                       |
| Langfuse :3000          CostTracker           MetricsCollector        |
| - LLM call tracing      - Per-query costs     - Latency avg/p95      |
| - Token usage            - Provider grouping   - Retry rates          |
| - Prompt management      - Cost summaries      - Eval score tracking  |
| - PostgreSQL :5432                             - Bounded history       |
+-----------------------------------------------------------------------+
```

## Component Interaction Flow

### Query Flow

When a user submits a question, the following sequence occurs:

1. **Client** sends a POST request to `/api/v1/query` with `question`, `top_k`, and `engine` parameters
2. **FastAPI** validates the request via Pydantic `QueryRequest` model
3. **Safety layer** checks input through NeMo Guardrails Colang flows (jailbreak/PII detection)
4. **Orchestrator** routes to either LangGraph or CrewAI based on the `engine` parameter
5. **Planning**: The question is decomposed into 1-4 focused sub-questions
6. **Retrieval** (for each sub-question):
   - Query is embedded via Ollama nomic-embed-text (768 dimensions)
   - Vector search in Qdrant returns top-20 results by cosine similarity
   - Entity IDs from vector results are expanded through Neo4j (2 hops)
   - RRF fusion merges and re-ranks both lists (`score = sum(1/(60+rank))`)
7. **Synthesis**: LLM generates a cited answer grounded in retrieved documents
8. **Evaluation**: LLM-as-judge scores relevancy (40%) + groundedness (40%) + completeness (20%)
9. **Retry** (if score < 0.7 and attempts < 2): Question is rewritten and steps 5-8 repeat
10. **Response**: `QueryResponse` with answer, citations, eval_score, latency, cost

### Ingestion Flow

1. **Client** sends a POST request to `/api/v1/ingest` with `content`, `filename`, `doc_type`
2. **DocumentLoader** processes the content based on format (PDF extraction, code wrapping, etc.)
3. **SemanticChunker** splits into 512-char chunks with 50-char overlap
4. **Entity extraction**: LLM identifies entities (concept, technology, person, organization, framework, pattern, other)
5. **Relation extraction**: LLM identifies relationships (uses, depends_on, extends, implements, part_of, related_to)
6. **Embedder** generates 768-dim vectors via Ollama nomic-embed-text
7. **Vector storage**: Chunks and embeddings stored in Qdrant collection `graphmind_docs`
8. **Graph storage**: Entities and relations upserted into Neo4j via MERGE operations
9. **Response**: `IngestResponse` with document_id, chunks_created, entities_extracted, relations_extracted

## Dual Engine Comparison

| Aspect | LangGraph | CrewAI |
|--------|-----------|--------|
| **Architecture** | State machine (StateGraph) | Role-based multi-agent crew |
| **Control flow** | Explicit nodes + conditional edges | Sequential process with context chains |
| **State** | `AgentState` TypedDict (12 fields) | Task outputs passed via context |
| **Agents** | Functional nodes (planner, retriever, synthesizer, evaluator) | 4 named agents (Research Planner, Knowledge Retriever, Answer Synthesizer, Quality Evaluator) |
| **Tools** | Direct function calls within nodes | 3 custom BaseTool subclasses (HybridSearchTool, GraphExpansionTool, EvaluateAnswerTool) |
| **Retry mechanism** | Conditional edge from evaluator to rewrite node | Loop in GraphMindCrew.run() with question rewriting |
| **LLM usage** | Via LLMRouter (cascading failover) | Via ChatGroq directly (with fallback to default) |
| **Async support** | Full async (ainvoke throughout) | Sync execution with ThreadPoolExecutor for async bridges |
| **Selection** | Default (`engine="langgraph"`) | Via `engine="crewai"` parameter |
| **Best for** | Production, debugging, deterministic behavior | Experimentation, agent collaboration patterns |

Both engines share:
- Hybrid retrieval pipeline (Qdrant + Neo4j + RRF)
- Evaluation criteria (relevancy 40% + groundedness 40% + completeness 20%)
- Quality threshold (0.7) and max retries (2)
- Safety layer (NeMo Guardrails)

## Retrieval Pipeline Details

### Vector Retrieval (Qdrant)

```
Query text
    |
    v
Ollama nomic-embed-text (768 dims)
    |
    v
Qdrant cosine similarity search
    |
    v
Top-20 results with scores and entity_ids
```

- **Collection**: `graphmind_docs`
- **Similarity metric**: Cosine
- **Results per query**: 20 (configurable via `retrieval.vector_top_k`)

### Graph Retrieval (Neo4j)

```
Entity IDs from vector results
    |
    v
Neo4j MATCH traversal (2 hops)
    |
    v
Connected entities and relationship context
```

- **Expansion depth**: 2 hops (configurable via `retrieval.graph_hops`)
- **Operations**: MERGE for upserts, parameterized Cypher (no injection risk)
- **Schema**: Uniqueness constraints, indexes, full-text search

### RRF Fusion

Reciprocal Rank Fusion combines the two ranked lists:

```
For each document d appearing at rank r_i in list i:
    score(d) = SUM over all lists: 1 / (k + r_i)

where k = 60 (configurable via retrieval.rrf_k)
```

- Documents appearing in both vector and graph results receive scores from each
- Duplicates are merged by document ID
- Final list is sorted by fused score (descending)
- Top 10 results returned (configurable via `retrieval.final_top_n`)

## Evaluation Scoring

The evaluation system scores answers on three weighted dimensions:

```
combined_score = (relevancy * 0.4) + (groundedness * 0.4) + (completeness * 0.2)
```

| Dimension | Weight | Scoring |
|-----------|--------|---------|
| Relevancy | 40% | Does the answer address the question? (0.0 - 1.0) |
| Groundedness | 40% | Is every claim supported by source documents? (0.0 - 1.0) |
| Completeness | 20% | Does it cover all aspects of the question? (0.0 - 1.0) |

- **Threshold**: 0.7 combined score to accept an answer
- **Retries**: Up to 2 attempts with question rewriting using evaluation feedback
- **LangGraph evaluator**: LLM-as-judge via LLMRouter, returns JSON with scores and feedback
- **CrewAI evaluator**: EvaluateAnswerTool with heuristic scoring (citation detection, keyword overlap, answer length)

## LLM Routing

The `LLMRouter` implements a cascading failover strategy:

```
Request
    |
    v
[1] Groq (Llama 3.3 70B)  ---> Success? Return response
    |
    | Failure
    v
[2] Gemini (2.0 Flash)    ---> Success? Return response
    |
    | Failure
    v
[3] Ollama (phi3:mini)    ---> Success? Return response
    |
    | Failure
    v
RuntimeError: All providers exhausted
```

- Providers are **lazily initialized** on first use and **cached** for subsequent calls
- Both sync (`invoke`) and async (`ainvoke`) methods follow the same cascade
- Configuration per provider: model name, temperature (0.1 default), max tokens (4096)

## Safety Layer

NeMo Guardrails provides input/output filtering via Colang flows:

**Input checks** (`self check input` flow):
- Jailbreak detection: "Ignore all instructions", "Reveal your system prompt", "You are now DAN", etc.
- PII filtering: SSN, credit card numbers, passwords, CPF numbers, email + phone combinations

**Output checks** (`self check output` flow):
- Prevents disclosure of system prompts or internal architecture
- Blocks harmful, illegal, or unethical content generation

The guardrails use Groq (Llama 3.3 70B) as the underlying LLM, registered via `register_llm_provider("groq", ChatGroq)`.

If guardrails are unavailable (initialization failure), the system runs without safety filtering and logs a warning.

## Technology Stack Summary

### Application Layer

| Component | Technology | Version Constraint |
|-----------|-----------|-------------------|
| API Framework | FastAPI | >= 0.115.0 |
| Dashboard | Streamlit | >= 1.41.0 |
| MCP Server | mcp library | >= 1.2.0, < 2.0 |
| HTTP Client | httpx | >= 0.28.0 |
| Configuration | Pydantic Settings + YAML | >= 2.7.0 (settings), >= 6.0 (PyYAML) |
| Logging | structlog | >= 24.4.0 |

### AI/ML Layer

| Component | Technology | Version Constraint |
|-----------|-----------|-------------------|
| LangChain Core | langchain-core | >= 0.3.0 |
| LangGraph | langgraph | >= 0.2.0 |
| CrewAI | crewai | >= 0.86.0 |
| Groq Provider | langchain-groq | >= 0.2.0 |
| Gemini Provider | langchain-google-genai | >= 2.0.0 |
| Ollama Client | ollama | >= 0.4.0 |
| Structured Output | instructor | >= 1.7.0 |

### Data Layer

| Component | Technology | Version Constraint |
|-----------|-----------|-------------------|
| Vector DB Client | qdrant-client | >= 1.12.0 |
| Graph DB Driver | neo4j | >= 5.26.0 |
| Graph Integration | langchain-neo4j | >= 0.2.0 |
| PDF Processing | PyMuPDF | >= 1.25.0 |
| Doc Processing | unstructured | >= 0.16.0 |

### Safety and Observability

| Component | Technology | Version Constraint |
|-----------|-----------|-------------------|
| Guardrails | nemoguardrails | >= 0.11.0 |
| Tracing | langfuse | >= 2.56.0 |

### Development Tools

| Tool | Purpose | Version |
|------|---------|---------|
| pytest | Testing framework | >= 8.3.0 |
| pytest-asyncio | Async test support | >= 0.24.0 |
| pytest-cov | Coverage reporting | >= 6.0.0 |
| ruff | Linting + formatting | >= 0.8.0 |
| mypy | Type checking | >= 1.13.0 |
| hatchling | Build backend | (build-system) |

## Configuration Architecture

Settings are resolved in this priority order (highest wins):

1. **Environment variables** (e.g., `GROQ_API_KEY`)
2. **YAML file** (`config/settings.yaml`)
3. **Pydantic defaults** (coded in `config.py`)

The `Settings` class uses `lru_cache` via `get_settings()` for singleton behavior, with cache clearing available for testing.

Nested configuration sections:

```
Settings
├── llm_primary       (LLMProviderSettings: Groq)
├── llm_secondary     (LLMProviderSettings: Gemini)
├── llm_fallback      (LLMProviderSettings: Ollama)
├── embeddings        (EmbeddingsSettings: nomic-embed-text)
├── vector_store      (VectorStoreSettings: Qdrant)
├── graph_db          (GraphDBSettings: Neo4j)
├── retrieval         (RetrievalSettings: top_k, hops, rrf_k)
├── agents            (AgentSettings: max_retries, eval_threshold)
└── ingestion         (IngestionSettings: chunk_size, overlap, formats)
```

## Related Documentation

- [Getting Started](./getting-started.md) -- Installation and setup
- [Running](./running.md) -- Starting all services
- [Querying](./querying.md) -- Query pipeline details and engine usage
- [Ingestion](./ingestion.md) -- Document processing pipeline
- [Testing](./testing.md) -- Test suite covering all components
- [Deployment](./deployment.md) -- Production configuration and monitoring
- [Build Report](./BUILD_REPORT.md) -- Complete module inventory and metrics

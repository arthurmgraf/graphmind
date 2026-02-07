# Testing

GraphMind uses **pytest** with **pytest-asyncio** for its test suite. The project has **85 unit tests** across **10 test files** plus 2 integration test files, covering all major subsystems.

## Running Tests

```bash
# Unit tests only (fast, no external services needed)
make test
# or: pytest tests/unit -v --tb=short

# Integration tests (requires Docker services running)
make test-integration
# or: pytest tests/integration -v --tb=short -m integration

# All tests with coverage report
make test-all
# or: pytest -v --tb=short --cov=src/graphmind --cov-report=term-missing

# Run a specific test file
pytest tests/unit/test_config.py -v

# Run a specific test class
pytest tests/unit/test_agents.py::TestPlannerNode -v

# Run a specific test
pytest tests/unit/test_chunker.py::TestSemanticChunker::test_single_short_text -v
```

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures (7 fixtures)
├── unit/                                # 85 tests across 10 files
│   ├── test_config.py                   # Settings defaults and caching
│   ├── test_schemas.py                  # All 13 Pydantic models
│   ├── test_chunker.py                  # SemanticChunker edge cases
│   ├── test_loaders.py                  # DocumentLoader all 7 formats
│   ├── test_cost_tracker.py             # Cost recording and aggregation
│   ├── test_metrics.py                  # MetricsCollector latency/p95/retry
│   ├── test_deepeval_suite.py           # LLM-as-judge evaluation
│   ├── test_hybrid_retriever.py         # RRF fusion formula
│   ├── test_agents.py                   # Planner, synthesizer, evaluator, retry
│   └── test_crew.py                     # CrewAI tools, agents, tasks
└── integration/
    ├── test_ingestion_pipeline.py       # Load + chunk end-to-end
    └── test_eval_suite.py               # Benchmark from JSONL files
```

## What Each Test File Covers

### Unit Tests (85 tests, 10 files)

| File | Tests | What It Validates |
|------|-------|-------------------|
| `test_config.py` | 9 | Settings defaults, `lru_cache` caching, nested config sections (LLM, retrieval, agents, ingestion) |
| `test_schemas.py` | 11 | All 13 Pydantic models: creation with defaults, auto-generated UUIDs, EntityType enum, QueryRequest/QueryResponse, IngestRequest/IngestResponse, GraphStats, HealthResponse |
| `test_chunker.py` | 7 | Empty text handling, single short text, long text splitting, metadata generation, sequential indices, unique chunk IDs, overlap correctness |
| `test_loaders.py` | 9 | MD/TXT/HTML/PY/TS/JS loading, file vs. content mode, code block wrapping, error handling for unsupported formats |
| `test_cost_tracker.py` | 6 | Recording cost entries, aggregation by provider, summary structure, provider grouping, empty tracker behavior |
| `test_metrics.py` | 7 | Average latency calculation, p95 percentile, retry rate tracking, history size limits, recent queries list |
| `test_deepeval_suite.py` | 7 | JSON parsing of LLM evaluator output, markdown fence stripping, fallback scoring on parse failure, threshold comparison, report generation |
| `test_hybrid_retriever.py` | 5 | RRF fusion formula correctness, overlap deduplication across vector+graph lists, empty input lists, score ordering, k parameter effect |
| `test_agents.py` | 14 | Planner decomposition, synthesizer generation, evaluator JSON parsing, evaluator fallback, retry logic, rewrite node, orchestrator graph building |
| `test_crew.py` | 10 | HybridSearchTool/GraphExpansionTool/EvaluateAnswerTool creation and execution, agent factory functions, task creation, context chain validation, error handling |

### Integration Tests (2 files)

| File | Tests | What It Validates |
|------|-------|-------------------|
| `test_ingestion_pipeline.py` | 3 | End-to-end load + chunk for markdown, long documents, and code files |
| `test_eval_suite.py` | 2 | Benchmark evaluation from JSONL dataset files, missing file error handling |

## Fixtures (conftest.py)

The shared `conftest.py` provides 7 fixtures available to all tests:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `_clear_settings_cache` | autouse | Clears the `get_settings()` `lru_cache` before and after each test |
| `settings` | function | Fresh `Settings` instance with cache cleared |
| `mock_llm_response` | function | `MagicMock` with `.content = "Test LLM response"` |
| `mock_router` | function | Mocked `LLMRouter` with async (`ainvoke`) and sync (`invoke`) methods |
| `sample_chunks` | function | 2 `DocumentChunk` instances (LangGraph and Neo4j content) |
| `sample_entities` | function | 3 `Entity` instances (LangGraph/framework, Neo4j/technology, LangChain/framework) |
| `sample_relations` | function | 1 `Relation` (LangGraph extends LangChain) |
| `sample_retrieval_results` | function | 3 `RetrievalResult` instances with vector and graph sources |

The conftest also sets dummy API keys (`test-key`) via `os.environ.setdefault` so that tests can instantiate `Settings` without real credentials.

## Evaluation Benchmark

Run the full evaluation benchmark against the 10-question dataset:

```bash
# Via Make
make eval

# Via CLI
graphmind-eval

# With custom dataset and threshold
graphmind-eval --dataset path/to/custom.jsonl --threshold 0.8
```

The benchmark evaluates each question/answer pair using LLM-as-judge scoring on three dimensions:
- **Relevancy** (40% weight): Does the answer address the question?
- **Groundedness** (40% weight): Is every claim supported by source documents?
- **Completeness** (20% weight): Does it cover all aspects?

The evaluation threshold is **0.7** (combined score). Results are saved to `eval/reports/latest_benchmark.json`.

The evaluation system supports two LLM judge implementations:
- **GroqEvalModel**: Uses Groq for fast evaluation
- **GeminiEvalModel**: Uses Gemini as fallback

## Linting and Formatting

```bash
# Check for issues (ruff check + format check)
make lint
# or: ruff check src/ tests/ && ruff format --check src/ tests/

# Auto-fix formatting and lint issues
make format
# or: ruff format src/ tests/ && ruff check --fix src/ tests/
```

Ruff is configured in `pyproject.toml` with:
- Target: Python 3.11
- Line length: 100
- Selected rules: E, F, I, N, UP, B, SIM

## Type Checking

```bash
mypy src/graphmind
```

Configured with `disallow_untyped_defs = true` and `warn_return_any = true` in `pyproject.toml`.

## CI Notes

- Tests marked `@pytest.mark.integration` require Docker services running (Qdrant, Neo4j, Ollama)
- Tests marked `@pytest.mark.eval` run the evaluation benchmark (slow, requires LLM API keys)
- **Unit tests run without any external dependencies** -- all LLM calls and database access are mocked
- The `conftest.py` sets dummy API keys so `Settings` can be instantiated safely
- `asyncio_mode = "auto"` is set in `pyproject.toml`, so async tests do not need explicit markers

## Related Documentation

- [Getting Started](./getting-started.md) -- Installation including dev dependencies
- [Architecture](./architecture.md) -- Understanding the components being tested
- [Querying](./querying.md) -- The pipeline that test_agents and test_crew validate
- [Ingestion](./ingestion.md) -- The pipeline that test_loaders and test_chunker validate

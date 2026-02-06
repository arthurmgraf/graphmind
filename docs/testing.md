# Testing

GraphMind uses pytest with pytest-asyncio for its test suite.

## Running Tests

```bash
# Unit tests only (fast, no external services needed)
make test
# or: pytest tests/unit -v --tb=short

# Integration tests (may need Docker services)
make test-integration
# or: pytest tests/integration -v --tb=short -m integration

# All tests with coverage
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
├── conftest.py                          # Shared fixtures
├── unit/
│   ├── test_config.py                   # Settings defaults and caching
│   ├── test_schemas.py                  # All Pydantic models
│   ├── test_chunker.py                  # SemanticChunker edge cases
│   ├── test_loaders.py                  # DocumentLoader all formats
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

### Unit Tests

| File | Tests | What it validates |
|------|-------|-------------------|
| `test_config.py` | 9 | Settings defaults, caching, nested config sections |
| `test_schemas.py` | 11 | All 13 Pydantic models: creation, defaults, auto-IDs |
| `test_chunker.py` | 7 | Empty text, long text, metadata, sequential indices, unique IDs |
| `test_loaders.py` | 9 | MD/TXT/HTML/PY/TS/JS loading, file vs content, error handling |
| `test_cost_tracker.py` | 6 | Recording, aggregation, summary structure, provider grouping |
| `test_metrics.py` | 7 | Avg latency, p95, retry rate, history limits, recent queries |
| `test_deepeval_suite.py` | 7 | JSON parsing, markdown fences, fallback, threshold, reports |
| `test_hybrid_retriever.py` | 5 | RRF formula, overlap dedup, empty lists, score correctness |
| `test_agents.py` | 8 | Planner decomposition, synthesis, eval scoring, retry logic |
| `test_crew.py` | 10 | CrewAI tools, agent creation, task creation, context chains |

### Integration Tests

| File | Tests | What it validates |
|------|-------|-------------------|
| `test_ingestion_pipeline.py` | 3 | End-to-end load + chunk for MD, long docs, code |
| `test_eval_suite.py` | 2 | Benchmark evaluation from JSONL, missing file errors |

## Fixtures (conftest.py)

Available fixtures for all tests:

| Fixture | Description |
|---------|-------------|
| `settings` | Fresh `Settings` instance (cache cleared per test) |
| `mock_router` | Mocked LLMRouter with async/sync invoke |
| `mock_llm_response` | MagicMock with `.content = "Test LLM response"` |
| `sample_chunks` | 2 DocumentChunk instances |
| `sample_entities` | 3 Entity instances (LangGraph, Neo4j, LangChain) |
| `sample_relations` | 1 Relation (LangGraph extends LangChain) |
| `sample_retrieval_results` | 3 RetrievalResult instances |

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

The benchmark evaluates each question/answer pair using LLM-as-judge scoring on relevancy, groundedness, and completeness. Results are saved to `eval/reports/latest_benchmark.json`.

## Linting

```bash
# Check for issues
make lint
# or: ruff check src/ tests/ && ruff format --check src/ tests/

# Auto-fix
make format
# or: ruff format src/ tests/ && ruff check --fix src/ tests/
```

## Type Checking

```bash
mypy src/graphmind
```

## CI Notes

- Tests marked `@pytest.mark.integration` require Docker services running
- Tests marked `@pytest.mark.eval` run the evaluation benchmark (slow)
- Unit tests run without any external dependencies
- The `conftest.py` sets dummy API keys (`test-key`) via `os.environ.setdefault`

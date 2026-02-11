# Contributing to GraphMind

Thank you for your interest in contributing to GraphMind. This guide covers everything you need to get started: development environment setup, code style, testing requirements, the pull request process, and how to propose architectural changes.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Code Style Guide](#code-style-guide)
3. [Testing Requirements](#testing-requirements)
4. [Pull Request Process](#pull-request-process)
5. [ADR Process](#adr-process)
6. [Commit Message Conventions](#commit-message-conventions)

---

## Development Environment Setup

### Prerequisites

- Python 3.11 or later
- Docker and Docker Compose (for infrastructure services)
- Git

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd graphmind

# Install the project in editable mode with all development and evaluation dependencies
make setup
# Equivalent to: pip install -e ".[dev,eval]"

# Install pre-commit hooks
pre-commit install

# Copy the environment template and fill in your secrets
cp .env.example .env
# Edit .env with your API keys (GROQ_API_KEY, NEO4J_PASSWORD, etc.)

# Start infrastructure services
make infra

# Pull the required embedding model
make pull-models

# Verify everything works
make check
# Runs: ruff check + ruff format --check + pytest tests/unit
```

### Development Dependencies

The `[dev]` extra installs:

| Tool | Purpose | Version |
|------|---------|---------|
| pytest | Test framework | >= 8.3.0 |
| pytest-asyncio | Async test support | >= 0.24.0 |
| pytest-cov | Coverage reporting | >= 6.0.0 |
| ruff | Linting and formatting | >= 0.8.0 |
| mypy | Static type checking | >= 1.13.0 |
| pre-commit | Git hook management | (latest) |

### Directory Structure

```
graphmind/
├── src/graphmind/          # Main application source code
│   ├── api/                # FastAPI routes and middleware
│   ├── agents/             # LangGraph orchestrator nodes
│   ├── crew/               # CrewAI agents, tasks, and tools
│   ├── retrieval/          # Vector/graph retrieval and embedding
│   ├── knowledge/          # Entity and relation extraction, graph builder
│   ├── ingestion/          # Document loading, chunking, pipeline
│   ├── safety/             # NeMo Guardrails configuration
│   ├── observability/      # Metrics, cost tracking, Langfuse client
│   ├── evaluation/         # LLM-as-judge eval and benchmarks
│   ├── dashboard/          # Streamlit UI
│   └── mcp/                # MCP server for IDE integration
├── tests/
│   ├── conftest.py         # Shared fixtures (7 fixtures)
│   ├── unit/               # 85 unit tests (10 files)
│   └── integration/        # Integration tests (2 files)
├── config/                 # YAML configuration
├── docs/                   # Documentation
│   ├── adrs/               # Architecture Decision Records
│   └── operations/         # Operational runbooks
└── docker-compose.yml      # Infrastructure services
```

---

## Code Style Guide

### Linting and Formatting (ruff)

GraphMind uses [ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Configuration is in `pyproject.toml`:

- **Target**: Python 3.11
- **Line length**: 100 characters
- **Selected rule sets**: E (pycodestyle errors), F (pyflakes), I (isort), N (naming), UP (pyupgrade), B (bugbear), SIM (simplify)

```bash
# Check for lint and formatting issues
make lint
# Equivalent to: ruff check src/ tests/ && ruff format --check src/ tests/

# Auto-fix formatting and fixable lint issues
make format
# Equivalent to: ruff format src/ tests/ && ruff check --fix src/ tests/
```

### Type Checking (mypy)

GraphMind uses strict type checking with mypy:

```bash
mypy src/graphmind
```

Configuration in `pyproject.toml`:
- `disallow_untyped_defs = true` -- All functions must have type annotations.
- `warn_return_any = true` -- Warn when returning `Any`.

**Guidelines:**
- All public functions and methods must have complete type annotations.
- Use `from __future__ import annotations` at the top of every module for PEP 604 union syntax (`X | None`).
- Use `typing.Any` sparingly. Prefer specific types.

### General Code Conventions

- **Imports**: Use absolute imports. Group by standard library, third-party, and local (enforced by ruff `I` rules).
- **Docstrings**: Use triple-quoted docstrings for modules, classes, and public functions. Follow NumPy docstring style for parameters/returns.
- **Async**: Use `async`/`await` throughout the application layer. Use `asyncio.Semaphore` for concurrency control.
- **Error handling**: Catch specific exceptions, not bare `except`. Log warnings for recoverable errors, raise for unrecoverable ones.
- **Logging**: Use `logging.getLogger(__name__)` for standard modules. Use `structlog.get_logger(__name__)` in the ingestion pipeline.
- **Configuration**: Never hardcode secrets. All configurable values go in `config.py` (Pydantic Settings) or `config/settings.yaml`.
- **Pydantic models**: Use `Field(...)` for required fields with validation constraints (`min_length`, `max_length`, `ge`, `le`).

---

## Testing Requirements

### Running Tests

```bash
# Unit tests only (fast, no external services needed)
make test
# Equivalent to: pytest tests/unit -v --tb=short

# Integration tests (requires Docker services running)
make test-integration
# Equivalent to: pytest tests/integration -v --tb=short -m integration

# All tests with coverage report
make test-all
# Equivalent to: pytest -v --tb=short --cov=src/graphmind --cov-report=term-missing
```

### Test Requirements for Contributions

1. **All PRs must pass existing tests.** No regressions allowed.
2. **New features must include unit tests.** Cover the happy path and at least one error/edge case.
3. **Bug fixes must include a regression test** that fails without the fix and passes with it.
4. **Unit tests must not require external services.** Mock all LLM calls, database connections, and HTTP requests. The `conftest.py` provides fixtures for common mocks.
5. **Coverage gate**: Aim for >= 80% coverage on new code. Use `make test-all` to check coverage.

### Test Structure

- Place unit tests in `tests/unit/test_<module>.py`.
- Place integration tests in `tests/integration/test_<feature>.py`.
- Mark integration tests with `@pytest.mark.integration`.
- Mark evaluation tests with `@pytest.mark.eval`.
- Async tests are auto-detected (`asyncio_mode = "auto"` in `pyproject.toml`).

### Available Test Fixtures

The `conftest.py` provides 7 shared fixtures. Use them instead of creating duplicate mocks:

| Fixture | Description |
|---------|-------------|
| `settings` | Fresh `Settings` instance with cleared cache |
| `mock_llm_response` | `MagicMock` with `.content = "Test LLM response"` |
| `mock_router` | Mocked `LLMRouter` with async and sync methods |
| `sample_chunks` | 2 `DocumentChunk` instances |
| `sample_entities` | 3 `Entity` instances |
| `sample_relations` | 1 `Relation` instance |
| `sample_retrieval_results` | 3 `RetrievalResult` instances |

---

## Pull Request Process

### Before Submitting

1. **Create a feature branch** from `master`:
   ```bash
   git checkout -b feat/my-feature master
   ```

2. **Run the full check suite** locally:
   ```bash
   make check
   # Runs: lint + unit tests
   ```

3. **Run type checking**:
   ```bash
   mypy src/graphmind
   ```

4. **Ensure no secrets** are committed (check `.env` is in `.gitignore`).

### PR Checklist

Before requesting review, confirm the following:

- [ ] Code passes `make lint` with no warnings or errors.
- [ ] Code passes `make test` with no failures.
- [ ] New code has type annotations (passes `mypy`).
- [ ] New features have corresponding unit tests.
- [ ] Bug fixes include a regression test.
- [ ] Documentation is updated if the change affects public APIs, configuration, or operational procedures.
- [ ] No secrets, API keys, or credentials are included in the diff.
- [ ] Commit messages follow the [conventional commits](#commit-message-conventions) format.
- [ ] ADR written if the change involves a significant architectural decision (see [ADR Process](#adr-process)).

### Review Process

1. Open a PR against `master` with a clear title and description.
2. At least one approval is required before merging.
3. Reviewers will check: correctness, test coverage, code style, documentation, and security.
4. Address review feedback by pushing additional commits (do not force-push during review).
5. After approval, squash-merge to keep a clean history on `master`.

### What Reviewers Look For

- **Correctness**: Does the code do what it claims? Are edge cases handled?
- **Tests**: Are there enough tests? Do they test behavior, not implementation details?
- **Types**: Are type annotations complete and correct?
- **Error handling**: Are exceptions caught appropriately? Are error messages useful?
- **Security**: Are inputs validated? Are secrets protected? Is there injection risk?
- **Performance**: Are there unnecessary allocations, N+1 queries, or unbounded data structures?
- **Consistency**: Does the code follow existing patterns in the codebase?

---

## ADR Process

Architecture Decision Records (ADRs) document significant design choices and their rationale. Use an ADR when:

- Introducing a new technology or dependency.
- Choosing between multiple design alternatives.
- Making a decision that is difficult or costly to reverse.
- Changing an existing architectural pattern.

### ADR Format

ADRs are stored in `docs/adrs/` with sequential numbering. Follow this template:

```markdown
# ADR-NNN: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-NNN]

## Context
[Why is this decision needed? What problem are we solving?
What constraints or requirements drive this decision?]

## Decision
[What did we decide to do? Be specific about the chosen approach.
Include technical details, not just high-level direction.]

## Consequences
- **[Positive consequence]**: [Description]
- **[Positive consequence]**: [Description]
- **[Negative consequence / trade-off]**: [Description]
```

### Existing ADRs

| ADR | Title | Status |
|-----|-------|--------|
| 001 | Multi-Provider LLM Routing with Cascading Fallback | Accepted |
| 002 | Hybrid Retrieval with RRF | Accepted |
| 003 | LangGraph Agentic RAG | Accepted |
| 004 | MCP Server Integration | Accepted |
| 005 | Dual Orchestration Engine (LangGraph + CrewAI) | Accepted |
| 006 | Structured Logging with structlog + OTEL Correlation | Accepted |
| 007 | Async Job Queue Selection (arq) | Accepted |
| 008 | Multi-Tenancy Isolation Model | Accepted |
| 009 | Secret Management Migration Path | Accepted |
| 010 | Rate Limiting Architecture | Accepted |

### Creating a New ADR

1. Determine the next number (check `docs/adrs/` for the highest existing number).
2. Create `docs/adrs/NNN-short-title.md` using the template above.
3. Set status to `Proposed`.
4. Include the ADR in your PR for review.
5. Once the PR is merged, update status to `Accepted`.

---

## Commit Message Conventions

GraphMind follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | A new feature | `feat: add rate limiting middleware` |
| `fix` | A bug fix | `fix: handle empty embedding response` |
| `docs` | Documentation only changes | `docs: add operations runbook` |
| `test` | Adding or fixing tests | `test: add circuit breaker unit tests` |
| `refactor` | Code change that neither fixes a bug nor adds a feature | `refactor: extract embedder retry logic` |
| `perf` | Performance improvement | `perf: add LRU cache to embedder` |
| `chore` | Build process or tooling changes | `chore: update ruff to 0.9.0` |
| `ci` | CI configuration changes | `ci: add mypy to pre-commit hooks` |

### Scopes (optional)

Use the module name as the scope when the change is focused on a single module:

- `api`, `agents`, `crew`, `retrieval`, `knowledge`, `ingestion`, `safety`, `observability`, `evaluation`, `dashboard`, `mcp`, `config`

### Examples

```
feat(api): add request body size limit middleware
fix(retrieval): handle dimension mismatch in embedder
docs(operations): add backup and restore procedures
test(agents): add evaluator fallback scoring tests
refactor(llm_router): extract circuit breaker into separate class
perf(embedder): add SHA-256 based LRU cache for embeddings
chore: update Docker Compose health check intervals
```

### Rules

1. Use the imperative mood ("add", not "added" or "adds").
2. Do not capitalize the first letter of the description.
3. Do not end the description with a period.
4. Keep the first line under 72 characters.
5. Use the body to explain **what** and **why**, not **how**.
6. Reference issue numbers in the footer: `Closes #42`.

---

## Related Documentation

- [Getting Started](./getting-started.md) -- Initial setup for users
- [Testing](./testing.md) -- Detailed test suite documentation
- [Architecture](./architecture.md) -- System design overview
- [ADRs](./adrs/) -- Architecture Decision Records

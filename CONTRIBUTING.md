# Contributing to GraphMind

Thank you for your interest in contributing to GraphMind\!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/arthurmgraf/graphmind.git
   cd graphmind
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scriptsctivate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Start infrastructure:
   ```bash
   docker compose up -d
   ```

5. Run the application:
   ```bash
   uvicorn src.api.main:app --reload
   ```

## Code Standards

- **Linting**: `ruff check src/ tests/`
- **Type checking**: `mypy src/ --strict`
- **Formatting**: `ruff format src/ tests/`
- **Testing**: `pytest tests/ -v`

All code must pass linting, type checking, and tests before merge.

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires Docker)
pytest tests/integration/ -v

# Coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

Minimum coverage threshold: 80%

## Pull Request Process

1. Fork the repository and create a branch from `main`
2. Make your changes with tests
3. Ensure CI passes (lint + type check + tests)
4. Write a clear PR description explaining the "why"
5. Request a review

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks

## Architecture Decision Records

For significant architectural changes, create an ADR in `docs/adr/`. See existing ADRs for format reference.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

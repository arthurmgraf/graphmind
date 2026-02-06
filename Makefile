.PHONY: setup dev infra infra-down pull-models test lint check run mcp dashboard eval clean

setup:
	pip install -e ".[dev,eval]"

dev:
	pip install -e ".[dev]"

infra:
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 10
	@echo "Services ready. Run 'make pull-models' next."

infra-down:
	docker compose down

pull-models:
	docker exec ollama ollama pull nomic-embed-text
	@echo "Embedding model ready."

test:
	pytest tests/unit -v --tb=short

test-integration:
	pytest tests/integration -v --tb=short -m integration

test-all:
	pytest -v --tb=short --cov=src/graphmind --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

check: lint test

run:
	uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload

mcp:
	python -m graphmind.mcp.server

dashboard:
	streamlit run src/graphmind/dashboard/app.py --server.port 8501

eval:
	python -m graphmind.evaluation.benchmark

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov dist build *.egg-info

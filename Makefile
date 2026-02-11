.PHONY: setup dev infra infra-down infra-gpu pull-models test test-integration test-adversarial test-load test-all lint format typecheck security-scan check run run-worker mcp dashboard eval prod prod-logs clean

# ---------- Setup ----------
setup:
	pip install -e ".[dev,eval]"
	pre-commit install

dev:
	pip install -e ".[dev]"

# ---------- Infrastructure ----------
infra:
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 10
	@echo "Services ready. Run 'make pull-models' next."

infra-down:
	docker compose down

infra-gpu:
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-logs:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f graphmind-api

pull-models:
	docker exec ollama ollama pull nomic-embed-text
	@echo "Embedding model ready."

# ---------- Testing ----------
test:
	pytest tests/unit -v --tb=short

test-integration:
	pytest tests/integration -v --tb=short -m integration

test-adversarial:
	pytest tests/adversarial -v --tb=short -m adversarial

test-load:
	locust -f tests/load/locustfile.py --headless -u 10 -r 2 --run-time 30s

test-all:
	pytest -v --tb=short --cov=src/graphmind --cov-report=term-missing --cov-fail-under=80

# ---------- Code quality ----------
lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/

security-scan:
	pip-audit --strict --desc on

check: lint typecheck test

# ---------- Run ----------
run:
	uvicorn graphmind.api.main:app --host 0.0.0.0 --port 8000 --reload

run-worker:
	arq graphmind.workers.ingest_worker.WorkerSettings

mcp:
	python -m graphmind.mcp.server

dashboard:
	streamlit run src/graphmind/dashboard/app.py --server.port 8501

eval:
	python -m graphmind.evaluation.benchmark

# ---------- Cleanup ----------
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov dist build *.egg-info

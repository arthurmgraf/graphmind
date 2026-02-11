# ============================================================================
# GraphMind API — Multi-stage Docker build
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-only dependencies
RUN pip install --no-cache-dir hatchling

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Non-root user
RUN groupadd -r graphmind && useradd -r -g graphmind -d /app graphmind

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy config files
COPY config/ config/

# Metadata labels
LABEL org.opencontainers.image.title="GraphMind API"
LABEL org.opencontainers.image.description="Autonomous Knowledge Agent Platform"
LABEL org.opencontainers.image.version="0.2.0"
LABEL org.opencontainers.image.source="https://github.com/graphmind/graphmind"

# Switch to non-root user
USER graphmind

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3     CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()" || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "graphmind.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

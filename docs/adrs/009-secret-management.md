# ADR-009: Secret Management (Environment Variables to Docker Secrets to Vault)

## Status
Accepted

## Context
GraphMind manages several secrets that are critical for operation:

| Secret | Purpose | Compromise Impact |
|--------|---------|-------------------|
| `GROQ_API_KEY` | Primary LLM provider authentication | Unauthorized API usage, cost exposure |
| `GEMINI_API_KEY` | Secondary LLM provider authentication | Unauthorized API usage, cost exposure |
| `NEO4J_PASSWORD` | Knowledge graph database access | Data read/write/delete |
| `POSTGRES_PASSWORD` | Langfuse backend database access | Trace data read/write/delete |
| `LANGFUSE_NEXTAUTH_SECRET` | Langfuse session signing | Session forgery |
| `LANGFUSE_SALT` | Langfuse password hashing | Hash weakening |
| `API_KEY` | GraphMind API authentication | Unauthorized platform access |

Currently, all secrets are managed via environment variables loaded from a `.env` file. The `Settings` class (Pydantic Settings) reads them at startup. Docker Compose uses `${VAR:?message}` syntax to fail fast if required secrets are missing.

**Current state (environment variables):**
- Simple and universal. Works in development and CI.
- `.env` file must be protected by filesystem permissions and excluded from version control (`.gitignore`).
- Secrets are visible in `docker inspect`, `/proc/<pid>/environ`, and process listing on the host.
- No audit trail for secret access.
- No automatic rotation.
- The `model_validator` in `Settings` warns (but does not fail) if LLM API keys are missing.

**Production concerns:**
- Environment variables are the most common source of secret leaks in containerized deployments.
- No separation between who can deploy and who can manage secrets.
- Secret rotation requires restarting all services.

## Decision
Adopt a three-phase migration path for secret management, moving from environment variables to Docker secrets to HashiCorp Vault as the platform matures:

### Phase 1: Environment Variables (Current)

Suitable for local development and small deployments. Already implemented.

**Hardening measures (already in place or to be added):**
- `.env` is in `.gitignore`.
- Docker Compose uses `:?` fail-fast syntax for required secrets.
- `model_validator` warns about missing secrets at startup.
- `APIKeyMiddleware` protects authenticated endpoints.
- No secrets are logged (structlog/logging do not include secret values).

### Phase 2: Docker Secrets

For single-host Docker deployments and Docker Swarm. Docker secrets are mounted as files in `/run/secrets/` inside containers, avoiding exposure via environment variables or `docker inspect`.

**Implementation:**

```yaml
# docker-compose.yml changes
services:
  api:
    secrets:
      - groq_api_key
      - gemini_api_key
      - neo4j_password
      - postgres_password
      - api_key

secrets:
  groq_api_key:
    file: ./secrets/groq_api_key.txt
  gemini_api_key:
    file: ./secrets/gemini_api_key.txt
  neo4j_password:
    file: ./secrets/neo4j_password.txt
  postgres_password:
    file: ./secrets/postgres_password.txt
  api_key:
    file: ./secrets/api_key.txt
```

**Settings class change:**

Extend `Settings` to read from `/run/secrets/<name>` if the environment variable is empty:

```python
@model_validator(mode="after")
def _load_docker_secrets(self) -> Self:
    secret_fields = ["groq_api_key", "gemini_api_key", "neo4j_password",
                     "postgres_password", "api_key"]
    for field_name in secret_fields:
        if not getattr(self, field_name):
            secret_path = Path(f"/run/secrets/{field_name}")
            if secret_path.exists():
                setattr(self, field_name, secret_path.read_text().strip())
    return self
```

### Phase 3: HashiCorp Vault

For production deployments requiring audit trails, automatic rotation, dynamic secrets, and fine-grained access control.

**Integration approach:**
- Use the `hvac` Python client to fetch secrets from Vault at application startup.
- Vault agent sidecar can alternatively inject secrets as files (compatible with Phase 2's file-reading logic).
- Enable Vault's audit log for compliance.
- Use Vault's database secrets engine for dynamic PostgreSQL and Neo4j credentials with automatic rotation.
- Use Vault's KV secrets engine for API keys.

**Settings class change:**

Add a `secrets_backend` configuration option:

```python
class Settings(BaseSettings):
    secrets_backend: str = "env"  # "env" | "docker" | "vault"
    vault_addr: str = ""
    vault_token: str = ""
    vault_mount: str = "secret"
```

## Consequences
- **Incremental adoption**: Each phase builds on the previous one. No big-bang migration required. Phase 1 (current) is already working. Phase 2 requires minimal code changes. Phase 3 requires a new dependency (`hvac`) and Vault infrastructure.
- **Backward compatibility**: Environment variables continue to work in all phases. Docker secrets and Vault are additive, not replacing.
- **Security improvement**: Phase 2 removes secrets from environment variables and `docker inspect`. Phase 3 adds audit trails, automatic rotation, and dynamic credentials.
- **Operational complexity**: Phase 2 adds a `secrets/` directory to manage. Phase 3 adds Vault as a critical infrastructure dependency (Vault itself must be highly available).
- **Development experience**: Developers continue using `.env` files locally. Docker secrets and Vault are only relevant for staging/production deployments.
- **Secret rotation**: Phase 1 requires service restarts. Phase 2 requires recreating Docker secrets and restarting services. Phase 3 supports automatic rotation via Vault leases (no restart needed for database credentials with Vault's dynamic secrets engine).

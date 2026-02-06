# Getting Started

## Prerequisites

- **Python 3.11+**
- **Docker** and **Docker Compose** (for infrastructure services)
- **Groq API key** (free at [console.groq.com](https://console.groq.com))
- Optional: **Gemini API key** (free at [aistudio.google.com](https://aistudio.google.com))

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/arthurmgraf/graphmind.git
cd graphmind
```

### 2. Create a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. Install the project

```bash
# Full installation (dev + eval)
pip install -e ".[dev,eval]"

# Or just dev
pip install -e ".[dev]"
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
GROQ_API_KEY=gsk_your_actual_key_here
NEO4J_PASSWORD=your_secure_password
POSTGRES_PASSWORD=your_secure_password
LANGFUSE_NEXTAUTH_SECRET=any_random_string
LANGFUSE_SALT=any_random_string
```

At minimum you need:
- `GROQ_API_KEY` - for LLM inference
- `NEO4J_PASSWORD` - for the graph database
- `POSTGRES_PASSWORD` - for Langfuse's backend database
- `LANGFUSE_NEXTAUTH_SECRET` and `LANGFUSE_SALT` - any random strings for Langfuse auth

### 5. Start infrastructure services

```bash
docker compose up -d
```

This starts 5 services:
| Service | Port | Purpose |
|---------|------|---------|
| Qdrant | 6333 | Vector database |
| Neo4j | 7474 (UI), 7687 (Bolt) | Graph database |
| PostgreSQL | 5432 | Langfuse backend |
| Langfuse | 3000 | Observability dashboard |
| Ollama | 11434 | Local embeddings |

### 6. Pull the embedding model

```bash
make pull-models
# or manually:
docker exec ollama ollama pull nomic-embed-text
```

### 7. Verify services are healthy

```bash
# Check all containers are running
docker compose ps

# Quick health check via API (after starting the server)
curl http://localhost:8000/api/v1/health
```

## Next Steps

- [Running the Application](./running.md) - Start the API, dashboard, and MCP server
- [Ingesting Documents](./ingestion.md) - Load documents into the knowledge base
- [Querying](./querying.md) - Ask questions with LangGraph or CrewAI engines
- [Testing](./testing.md) - Run the test suite

# Querying the Knowledge Base

GraphMind supports two orchestration engines for answering questions: **LangGraph** (default) and **CrewAI**. Both engines share the same hybrid retrieval pipeline, LLM routing strategy, and evaluation criteria.

## Dual Engine Overview

### LangGraph (default)

A state machine built with LangGraph's `StateGraph` providing explicit, deterministic control flow:

```
Plan --> Retrieve --> Synthesize --> Evaluate --+--> Answer
  ^                                     |       |
  |                                score < 0.7  |
  +---- Rewrite <---------- retry loop ---------+
                          (max 2 retries)
```

The LangGraph engine uses an `AgentState` TypedDict with 12 fields that flow through each node. Conditional edges route from the evaluator back to the rewrite node if the score is below the threshold.

**Best for**: Deterministic pipelines, precise state inspection, debugging individual steps, production workloads requiring predictable behavior.

### CrewAI

A role-based multi-agent crew with 4 specialized agents:

| Agent | Role | Tools |
|-------|------|-------|
| **Research Planner** | Decomposes complex questions into 1-4 focused sub-questions | None |
| **Knowledge Retriever** | Searches the knowledge base using hybrid retrieval | HybridSearchTool, GraphExpansionTool |
| **Answer Synthesizer** | Generates cited answers from retrieved documents only | None |
| **Quality Evaluator** | Scores answers and provides improvement feedback | EvaluateAnswerTool |

CrewAI agents execute in a sequential process, with tasks chained via `context` dependencies. The crew also supports retry with question rewriting when the evaluation score falls below threshold.

**CrewAI Tools:**

| Tool | Description |
|------|-------------|
| `HybridSearchTool` | Wraps the hybrid retriever (vector + graph + RRF fusion) for agent use |
| `GraphExpansionTool` | Expands entity relationships through Neo4j graph traversal (2 hops) |
| `EvaluateAnswerTool` | Scores answer quality on relevancy, groundedness, and completeness |

**Best for**: Natural agent collaboration, flexible delegation, role-based workflows, experimentation with multi-agent patterns.

### What Both Engines Share

- **Hybrid retrieval**: Vector (Qdrant, top-k=20) + Graph (Neo4j, 2 hops) + RRF fusion (k=60)
- **LLM routing**: Groq (primary) -> Gemini (fallback) -> Ollama (local fallback)
- **Evaluation criteria**: Relevancy (40%) + Groundedness (40%) + Completeness (20%)
- **Quality threshold**: Combined score >= 0.7 to pass; up to 2 retries with question rewriting
- **Safety**: NeMo Guardrails with Colang flows for jailbreak/PII filtering

## Via REST API

```bash
# LangGraph engine (default)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is LangGraph?", "top_k": 10, "engine": "langgraph"}'

# CrewAI engine
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare vector search and graph traversal", "engine": "crewai"}'
```

### Request Schema

```json
{
  "question": "Your question here",
  "top_k": 10,
  "engine": "langgraph"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `question` | string | required | Natural language question |
| `top_k` | integer | 10 | Number of final retrieval results to consider after RRF fusion |
| `engine` | string | `"langgraph"` | Orchestration engine: `"langgraph"` or `"crewai"` |

### Response Schema

```json
{
  "answer": "LangGraph is a framework...",
  "citations": [
    {
      "document_id": "doc-abc",
      "chunk_id": "chunk-123",
      "text_snippet": "LangGraph is a library for...",
      "source": "vector"
    }
  ],
  "eval_score": 0.85,
  "sources_used": 3,
  "latency_ms": 2450.5,
  "cost_usd": 0.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Generated answer with markdown formatting |
| `citations` | array | Source references with document/chunk IDs, text snippets, and source type (vector/graph) |
| `eval_score` | float | Combined evaluation score (0.0 - 1.0) |
| `sources_used` | integer | Number of source citations |
| `latency_ms` | float | Total query latency in milliseconds |
| `cost_usd` | float | Estimated LLM cost for the query |

## Via Dashboard

1. Open http://localhost:8501
2. Select **Query** from the sidebar navigation
3. Enter your question in the text input
4. Choose the engine: **langgraph** or **crewai**
5. Adjust **Top K** slider (1-50, default 10)
6. Click **Ask**

The dashboard displays:
- The generated answer with full markdown rendering
- Three metrics: evaluation score, latency (ms), and source count
- An expandable **Citations** section with numbered source references and text snippets

## Via MCP (IDE)

With MCP configured in your IDE (see [Running](./running.md#mcp-server)), use the `query` tool:

```
Use the graphmind query tool to answer: What is Reciprocal Rank Fusion?
```

Specify the engine explicitly:
```
Use graphmind query with engine=crewai: Compare CrewAI and LangGraph
```

## How the Pipeline Works

### Step 1: Safety Check

User input is passed through NeMo Guardrails. Colang flows check for:
- **Jailbreak attempts**: "Ignore all instructions", "Reveal your system prompt", etc.
- **PII sharing**: SSN, credit card numbers, passwords, CPF numbers, etc.

If blocked, the pipeline returns a refusal message without reaching the LLM.

### Step 2: Planning

The question is decomposed into 1-4 focused sub-questions:
- Simple factual questions pass through as-is (1 sub-question)
- Comparisons generate one sub-question per subject plus a comparison question
- Multi-hop reasoning generates sequential step-by-step sub-questions

### Step 3: Hybrid Retrieval

For each sub-question:

1. **Embed** the query using Ollama nomic-embed-text (768 dimensions)
2. **Vector search** in Qdrant with cosine similarity (top-k=20 results)
3. **Graph expansion** from retrieved entity IDs through Neo4j (2 hops depth)
4. **RRF fusion** combines both ranked lists using Reciprocal Rank Fusion:
   ```
   score(d) = sum(1 / (k + rank))    where k = 60
   ```
   Documents appearing in both lists get scores from each, and duplicates are merged by ID.

### Step 4: Synthesis

An LLM (routed via Groq -> Gemini -> Ollama cascade) generates a cited answer using only the retrieved documents. The synthesis prompt enforces:
- Answers grounded exclusively in retrieved documents
- Inline citations using `[Source: doc_id]` format
- Structured formats (tables, bullets) for comparative questions
- Explicit acknowledgment of missing information

### Step 5: Evaluation

The answer is scored by an LLM-as-judge on three weighted dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Relevancy** | 40% | Does the answer address the question? |
| **Groundedness** | 40% | Is every claim supported by source documents? |
| **Completeness** | 20% | Does it cover all aspects of the question? |

Combined score: `(relevancy * 0.4) + (groundedness * 0.4) + (completeness * 0.2)`

### Step 6: Retry (if needed)

If the combined score is below **0.7** and retry count is less than **2**:
1. The evaluation feedback is used to rewrite the question
2. The pipeline re-executes from the planning step with the improved question
3. The best-scoring result across all attempts is returned

## Configuration

Key retrieval and evaluation parameters (settable via `config/settings.yaml` or environment variables):

```yaml
retrieval:
  vector_top_k: 20       # Vector search result count
  graph_hops: 2           # Knowledge graph expansion depth
  rrf_k: 60              # RRF fusion constant
  final_top_n: 10        # Final results after fusion

agents:
  max_retries: 2          # Max retry attempts on low eval score
  eval_threshold: 0.7     # Minimum score to accept an answer
```

## Related Documentation

- [Architecture](./architecture.md) -- Detailed system design and dual engine comparison
- [Ingestion](./ingestion.md) -- How to populate the knowledge base
- [Running](./running.md) -- Starting the API, dashboard, and MCP server
- [Testing](./testing.md) -- Testing the query pipeline

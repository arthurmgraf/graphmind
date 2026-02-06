# Querying the Knowledge Base

GraphMind supports two orchestration engines for answering questions: **LangGraph** and **CrewAI**.

## Engines

### LangGraph (default)

State machine with explicit control flow:
```
Plan -> Retrieve -> Synthesize -> Evaluate -> [Retry if score < 0.7]
```

Best for: deterministic pipelines, precise state control, debugging individual steps.

### CrewAI

Role-based multi-agent crew:
- **Research Planner** - decomposes the question
- **Knowledge Retriever** - searches with hybrid tools
- **Answer Synthesizer** - generates cited answers
- **Quality Evaluator** - scores and provides feedback

Best for: natural agent collaboration, flexible delegation, role-based workflows.

Both engines share the same hybrid retrieval (Qdrant + Neo4j + RRF fusion), LLM routing (Groq -> Gemini -> Ollama), and evaluation criteria.

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
| `top_k` | integer | 10 | Number of retrieval results to consider |
| `engine` | string | "langgraph" | Orchestration engine: `"langgraph"` or `"crewai"` |

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

## Via Dashboard

1. Open http://localhost:8501
2. Select **Query** from the sidebar
3. Enter your question
4. Choose the engine (LangGraph or CrewAI)
5. Adjust Top K if needed
6. Click **Ask**

The dashboard displays:
- The generated answer with markdown formatting
- Evaluation score, latency, and source count as metrics
- Expandable citations section with source references

## Via MCP (IDE)

In your IDE with MCP configured, use the `query` tool:

```
Use the graphmind query tool to answer: What is Reciprocal Rank Fusion?
```

You can specify the engine:
```
Use graphmind query with engine=crewai: Compare CrewAI and LangGraph
```

## How the Pipeline Works

### Step 1: Planning
The question is decomposed into 1-4 sub-questions for focused retrieval.

### Step 2: Hybrid Retrieval
For each sub-question:
1. **Embed** the query using Ollama (nomic-embed-text, 768 dimensions)
2. **Vector search** in Qdrant (top-k=20, cosine similarity)
3. **Graph expansion** from retrieved entity IDs through Neo4j (2 hops)
4. **RRF fusion**: `score(d) = sum(1/(60 + rank))` across both ranked lists

### Step 3: Synthesis
An LLM generates a cited answer using only the retrieved documents.

### Step 4: Evaluation
The answer is scored on:
- **Relevancy** (40%): Does it address the question?
- **Groundedness** (40%): Is every claim supported by documents?
- **Completeness** (20%): Does it cover all aspects?

### Step 5: Retry (if needed)
If combined score < 0.7 and retries < 2:
- Rewrite the question using evaluation feedback
- Re-run the pipeline with the improved question

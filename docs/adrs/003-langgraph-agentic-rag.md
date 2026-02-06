# ADR-003: LangGraph Agentic RAG with Self-Evaluation Loop

## Status
Accepted

## Context
Simple RAG pipelines (retrieve-then-generate) produce answers without quality assurance. If retrieval fails or the LLM hallucinates, the user gets a poor answer with no recourse. An agentic approach with self-correction can improve answer quality.

## Decision
Build the query pipeline as a LangGraph state machine with these nodes:
1. **Planner** - Decomposes complex questions into sub-questions (max 4).
2. **Retriever** - Runs hybrid retrieval for each sub-question.
3. **Synthesizer** - Generates a cited answer from retrieved context.
4. **Evaluator** - Scores the answer on relevancy, groundedness, completeness (0-1).
5. **Rewrite** - If score < threshold (0.7), rewrites the query using feedback.

Conditional edge from Evaluator: if score >= 0.7 or retries >= 2, return answer; otherwise loop back to Planner.

## Consequences
- **Quality**: Self-evaluation catches low-quality answers and retries with refined queries.
- **Latency**: Each retry adds ~2-4 seconds. Max 2 retries caps worst-case overhead.
- **Cost**: Extra LLM calls for evaluation and retry. Mitigated by free-tier providers.
- **Observability**: Each node's input/output is traceable via Langfuse.

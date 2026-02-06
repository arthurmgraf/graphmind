# ADR-005: Dual Orchestration Engine (LangGraph + CrewAI)

## Status
Accepted

## Context
The project initially used LangGraph exclusively for agent orchestration. LangGraph provides fine-grained state machine control with cyclic graphs, ideal for retry/correction loops. However, CrewAI offers a complementary role-based multi-agent approach with simpler APIs and natural delegation patterns.

## Decision
Support both orchestration engines selectable at query time via the `engine` parameter:

1. **LangGraph** (default) - State machine with explicit nodes: Plan -> Retrieve -> Synthesize -> Evaluate -> Retry loop. Best for deterministic pipelines with precise control.

2. **CrewAI** - Role-based crew with four agents: Research Planner, Knowledge Retriever, Answer Synthesizer, Quality Evaluator. Sequential process with tool-based hybrid retrieval. Best for natural multi-agent collaboration.

Both engines share the same:
- Hybrid retrieval layer (Qdrant + Neo4j + RRF fusion)
- LLM provider routing (Groq -> Gemini -> Ollama)
- Evaluation criteria (relevancy, groundedness, completeness)
- API schemas (QueryRequest/QueryResponse)
- Retry mechanism (max 2 retries, threshold 0.7)

## Consequences
- **Flexibility**: Users choose the engine that best fits their use case.
- **Comparison**: Enables A/B testing between orchestration approaches.
- **Complexity**: Two codepaths to maintain, but shared infrastructure minimizes duplication.
- **CrewAI tools**: Custom `BaseTool` wrappers bridge async retrieval to CrewAI's sync interface.

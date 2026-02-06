# ADR-001: Multi-Provider LLM Routing with Cascading Fallback

## Status
Accepted

## Context
GraphMind requires LLM access for multiple tasks: query planning, synthesis, evaluation, entity/relation extraction, and guardrails. No single provider guarantees 100% uptime, and different providers offer different cost/performance tradeoffs.

## Decision
Implement an `LLMRouter` class that cascades through three providers in order:
1. **Groq** (primary) - Llama 3.3 70B via Groq API. Fastest inference, free tier available.
2. **Gemini** (secondary) - Gemini 2.0 Flash via Google AI. High quality, generous free tier.
3. **Ollama** (fallback) - Local phi3:mini. Zero cost, fully offline, lower quality.

All providers are wrapped via LangChain abstractions (`BaseChatModel`) for uniform interface.

## Consequences
- **Resilience**: If Groq is down, the system automatically falls back to Gemini, then Ollama.
- **Cost**: Free-tier providers first, paid only if configured.
- **Latency**: Fallback adds latency on provider failures but not on happy path.
- **Trade-off**: Ollama quality is lower than cloud providers but ensures the system never fully fails.

from __future__ import annotations

from crewai import Agent, Task


def create_planning_task(agent: Agent, question: str) -> Task:
    return Task(
        description=(
            f"Analyze this question and decompose it into focused sub-questions:\n\n"
            f"Question: {question}\n\n"
            f"Rules:\n"
            f"- If the question is simple and factual, return it as-is (single sub-question).\n"
            f"- If comparing things, create one sub-question per thing plus a comparison.\n"
            f"- If requiring multi-hop reasoning, break into sequential steps.\n"
            f"- Maximum 4 sub-questions.\n"
            f"- Return ONLY the sub-questions, one per line."
        ),
        expected_output="A list of 1-4 focused sub-questions, one per line, no numbering.",
        agent=agent,
    )


def create_retrieval_task(
    agent: Agent,
    question: str,
    planning_task: Task,
) -> Task:
    return Task(
        description=(
            f"Using the sub-questions from the research plan, search the knowledge base "
            f"for relevant information.\n\n"
            f"Original question: {question}\n\n"
            f"For each sub-question:\n"
            f"1. Use the hybrid_knowledge_search tool with the sub-question as query.\n"
            f"2. If results contain entity_ids, use graph_expansion to find related entities.\n"
            f"3. Collect and deduplicate all retrieved documents.\n\n"
            f"Return ALL retrieved document texts with their IDs and sources."
        ),
        expected_output=(
            "A structured collection of retrieved documents with their IDs, text content, "
            "scores, and sources. Include all unique documents found across all sub-questions."
        ),
        agent=agent,
        context=[planning_task],
    )


def create_synthesis_task(
    agent: Agent,
    question: str,
    retrieval_task: Task,
) -> Task:
    return Task(
        description=(
            f"Synthesize a comprehensive answer to the question using ONLY the retrieved "
            f"documents.\n\n"
            f"Question: {question}\n\n"
            f"Rules:\n"
            f"- Base your answer ONLY on the retrieved documents. No prior knowledge.\n"
            f"- Cite sources inline using [Source: doc_id] format.\n"
            f"- If comparing, use a table or side-by-side format.\n"
            f"- Be concise but thorough.\n"
            f"- If documents lack information, explicitly state what is missing."
        ),
        expected_output=(
            "A comprehensive, well-cited answer that addresses all aspects of the question. "
            "Every claim must reference a specific source document."
        ),
        agent=agent,
        context=[retrieval_task],
    )


def create_evaluation_task(
    agent: Agent,
    question: str,
    synthesis_task: Task,
    retrieval_task: Task,
) -> Task:
    return Task(
        description=(
            f"Evaluate the synthesized answer for quality.\n\n"
            f"Original question: {question}\n\n"
            f"Score the answer on three dimensions (0.0 to 1.0):\n"
            f"1. Relevancy: Does it address the question?\n"
            f"2. Groundedness: Is every claim supported by the source documents?\n"
            f"3. Completeness: Does it cover all aspects of the question?\n\n"
            f"Use the evaluate_answer_quality tool with the question, answer, and document "
            f"texts as input.\n\n"
            f"If the combined score is below 0.7, provide specific feedback on how to improve."
        ),
        expected_output=(
            "A JSON evaluation with relevancy, groundedness, completeness scores, "
            "combined score, and actionable feedback. Format:\n"
            '{"relevancy": 0.0, "groundedness": 0.0, "completeness": 0.0, '
            '"combined": 0.0, "feedback": "..."}'
        ),
        agent=agent,
        context=[synthesis_task, retrieval_task],
    )

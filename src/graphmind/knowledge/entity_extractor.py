from __future__ import annotations

import structlog
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from graphmind.config import Settings, get_settings
from graphmind.llm_router import LLMRouter, get_llm_router
from graphmind.schemas import Entity, EntityType

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert knowledge-graph entity extractor. "
    "Given a text chunk, identify and extract all meaningful entities. "
    "Each entity must be one of the following types: "
    "concept, technology, person, organization, framework, pattern, other. "
    "For every entity provide a short, precise name (normalized to title case) "
    "and a one-sentence description grounded in the source text. "
    "Return ONLY valid JSON matching the required schema. "
    "Do not invent entities that are not present in the text."
)

USER_TEMPLATE = (
    "Extract all entities from the following text.\n\n"
    "---\n{text}\n---\n\n"
    "Respond with a JSON object containing a single key \"entities\" "
    "whose value is an array of objects, each with keys: "
    "\"name\" (string), \"type\" (one of: concept, technology, person, "
    "organization, framework, pattern, other), and \"description\" (string)."
)


class ExtractedEntity(BaseModel):
    name: str
    type: str
    description: str = ""


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)


def _parse_entity_type(raw: str) -> EntityType:
    normalized = raw.strip().lower()
    try:
        return EntityType(normalized)
    except ValueError:
        return EntityType.OTHER


class EntityExtractor:
    def __init__(
        self,
        router: LLMRouter | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._router = router or get_llm_router()

    async def extract(self, text: str, chunk_id: str) -> list[Entity]:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_TEMPLATE.format(text=text)),
        ]

        llm = self._router.get_primary()
        structured_llm = llm.with_structured_output(ExtractionResult)

        try:
            result: ExtractionResult = await structured_llm.ainvoke(messages)
        except Exception:
            logger.exception("Structured extraction failed, attempting fallback parse")
            response = await self._router.ainvoke(messages)
            result = self._fallback_parse(response.content)

        return self._to_entities(result, chunk_id)

    def _to_entities(self, result: ExtractionResult, chunk_id: str) -> list[Entity]:
        entities: list[Entity] = []
        seen_names: set[str] = set()

        for raw in result.entities:
            normalized_name = raw.name.strip().title()
            if not normalized_name or normalized_name.lower() in seen_names:
                continue
            seen_names.add(normalized_name.lower())

            entities.append(
                Entity(
                    name=normalized_name,
                    type=_parse_entity_type(raw.type),
                    description=raw.description.strip(),
                    source_chunk_id=chunk_id,
                )
            )

        logger.info(
            "Extracted %d entities from chunk %s",
            len(entities),
            chunk_id,
        )
        return entities

    def _fallback_parse(self, content: Any) -> ExtractionResult:
        import json

        text = str(content)

        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("No JSON object found in LLM response")
            return ExtractionResult()

        try:
            data = json.loads(text[start:end])
            return ExtractionResult.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Fallback JSON parse failed: %s", exc)
            return ExtractionResult()

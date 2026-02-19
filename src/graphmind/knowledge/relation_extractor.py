from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from graphmind.config import Settings, get_settings
from graphmind.llm_router import LLMRouter, get_llm_router
from graphmind.schemas import Entity, Relation

logger = structlog.get_logger(__name__)

VALID_RELATION_TYPES = frozenset(
    {"uses", "depends_on", "extends", "implements", "part_of", "related_to"}
)

SYSTEM_PROMPT = (
    "You are an expert knowledge-graph relation extractor. "
    "Given a text and a list of previously extracted entities, "
    "identify meaningful directed relationships between them. "
    "Each relation must use one of these types: "
    "uses, depends_on, extends, implements, part_of, related_to. "
    "Only create relations that are clearly supported by the text. "
    "Use the entity names exactly as provided. "
    "Return ONLY valid JSON matching the required schema."
)

USER_TEMPLATE = (
    "Text:\n---\n{text}\n---\n\n"
    "Entities:\n{entity_list}\n\n"
    "Identify all directed relationships between the entities above "
    "that are supported by the text. "
    'Respond with a JSON object containing a single key "relations" '
    "whose value is an array of objects, each with keys: "
    '"source" (entity name), "target" (entity name), '
    '"type" (one of: uses, depends_on, extends, implements, part_of, related_to), '
    'and "description" (brief explanation).'
)


class ExtractedRelation(BaseModel):
    source: str
    target: str
    type: str
    description: str = ""


class ExtractionResult(BaseModel):
    relations: list[ExtractedRelation] = Field(default_factory=list)


def _format_entity_list(entities: list[Entity]) -> str:
    lines: list[str] = []
    for entity in entities:
        lines.append(f"- {entity.name} ({entity.type.value})")
    return "\n".join(lines)


def _normalize_relation_type(raw: str) -> str:
    normalized = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in VALID_RELATION_TYPES:
        return normalized
    return "related_to"


class RelationExtractor:
    def __init__(
        self,
        router: LLMRouter | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._router = router or get_llm_router()

    async def extract(self, text: str, entities: list[Entity]) -> list[Relation]:
        if len(entities) < 2:
            return []

        entity_name_to_id: dict[str, str] = {entity.name.lower(): entity.id for entity in entities}

        entity_list_str = _format_entity_list(entities)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_TEMPLATE.format(text=text, entity_list=entity_list_str)),
        ]

        llm = self._router.get_primary()
        structured_llm = llm.with_structured_output(ExtractionResult)

        try:
            result: ExtractionResult = await structured_llm.ainvoke(messages)  # type: ignore[assignment]
        except Exception:
            logger.exception("Structured relation extraction failed, attempting fallback")
            response = await self._router.ainvoke(messages)
            result = self._fallback_parse(response.content)

        return self._to_relations(result, entity_name_to_id)

    def _to_relations(
        self,
        result: ExtractionResult,
        entity_name_to_id: dict[str, str],
    ) -> list[Relation]:
        relations: list[Relation] = []
        seen_triples: set[tuple[str, str, str]] = set()

        for raw in result.relations:
            source_name = raw.source.strip().lower()
            target_name = raw.target.strip().lower()

            source_id = entity_name_to_id.get(source_name)
            target_id = entity_name_to_id.get(target_name)

            if not source_id or not target_id:
                logger.debug(
                    "Skipping relation with unknown entity: %s -> %s",
                    raw.source,
                    raw.target,
                )
                continue

            if source_id == target_id:
                continue

            relation_type = _normalize_relation_type(raw.type)
            triple = (source_id, target_id, relation_type)

            if triple in seen_triples:
                continue
            seen_triples.add(triple)

            relations.append(
                Relation(
                    source_id=source_id,
                    target_id=target_id,
                    type=relation_type,
                    description=raw.description.strip(),
                )
            )

        logger.info("Extracted %d relations", len(relations))
        return relations

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

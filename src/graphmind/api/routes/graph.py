"""Graph visualization endpoints for D3.js-compatible data."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Query, Request

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1")


@router.get("/graph/explore")
async def explore_graph(
    request: Request,
    entity: str = Query(..., min_length=1, description="Entity name to explore"),
    hops: int = Query(default=2, ge=1, le=5, description="Number of hops from the entity"),
) -> dict:
    """Return D3.js-compatible graph JSON centered on an entity.

    Returns ``{nodes: [...], links: [...]}`` suitable for force-directed
    graph visualisation.
    """
    resources = request.app.state.resources
    driver = resources.neo4j_driver

    if driver is None:
        return {"nodes": [], "links": [], "error": "Neo4j not configured"}

    query = """
    MATCH path = (start:Entity {name: $entity})-[*1..$hops]-(connected:Entity)
    WITH start, connected, relationships(path) AS rels
    UNWIND rels AS rel
    WITH collect(DISTINCT start) + collect(DISTINCT connected) AS all_nodes,
         collect(DISTINCT rel) AS all_rels
    UNWIND all_nodes AS node
    WITH collect(DISTINCT {
        id: node.id,
        name: node.name,
        type: node.type,
        description: coalesce(node.description, '')
    }) AS nodes, all_rels
    UNWIND all_rels AS rel
    WITH nodes, collect(DISTINCT {
        source: startNode(rel).id,
        target: endNode(rel).id,
        type: rel.type,
        description: coalesce(rel.description, '')
    }) AS links
    RETURN nodes, links
    """

    try:
        async with driver.session() as session:
            result = await session.run(query, entity=entity, hops=hops)
            record = await result.single()

            if record is None:
                logger.info("graph_explore_no_results", entity=entity, hops=hops)
                return {"nodes": [], "links": []}

            nodes = record["nodes"] or []
            links = record["links"] or []

            logger.info(
                "graph_explore_complete",
                entity=entity,
                hops=hops,
                nodes=len(nodes),
                links=len(links),
            )
            return {"nodes": nodes, "links": links}

    except Exception as exc:
        logger.error("graph_explore_failed", entity=entity, error=str(exc))
        return {"nodes": [], "links": [], "error": str(exc)}


@router.get("/graph/entity-types")
async def get_entity_types(request: Request) -> dict:
    """Return counts of each entity type in the knowledge graph."""
    resources = request.app.state.resources
    driver = resources.neo4j_driver

    if driver is None:
        return {"types": {}}

    try:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (e:Entity) RETURN e.type AS type, count(e) AS count ORDER BY count DESC"
            )
            types = {}
            async for record in result:
                types[record["type"]] = record["count"]
            return {"types": types}
    except Exception as exc:
        logger.error("entity_types_failed", error=str(exc))
        return {"types": {}, "error": str(exc)}

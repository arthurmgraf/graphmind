// GraphMind initial schema migration
// Creates indexes and constraints for Entity and Relation nodes

// Unique constraint on Entity id
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

// Index on Entity name for text search
CREATE INDEX entity_name_index IF NOT EXISTS
FOR (e:Entity) ON (e.name);

// Index on Entity type for filtering
CREATE INDEX entity_type_index IF NOT EXISTS
FOR (e:Entity) ON (e.type);

// Index on Entity source_chunk_id for provenance tracking
CREATE INDEX entity_source_chunk_index IF NOT EXISTS
FOR (e:Entity) ON (e.source_chunk_id);

// Index on RELATES_TO relationship type
CREATE INDEX relation_type_index IF NOT EXISTS
FOR ()-[r:RELATES_TO]-() ON (r.type);

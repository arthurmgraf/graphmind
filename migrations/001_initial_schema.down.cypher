// Rollback: drop indexes and constraints
DROP CONSTRAINT entity_id_unique IF EXISTS;
DROP INDEX entity_name_index IF EXISTS;
DROP INDEX entity_type_index IF EXISTS;
DROP INDEX entity_source_chunk_index IF EXISTS;
DROP INDEX relation_type_index IF EXISTS;

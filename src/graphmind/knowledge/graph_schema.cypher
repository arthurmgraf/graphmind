CREATE CONSTRAINT entity_name_type_unique IF NOT EXISTS
FOR (e:Entity)
REQUIRE (e.name, e.type) IS UNIQUE;

CREATE INDEX entity_type_index IF NOT EXISTS
FOR (e:Entity)
ON (e.type);

CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
FOR (e:Entity)
ON EACH [e.name];

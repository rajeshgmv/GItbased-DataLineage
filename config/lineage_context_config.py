"""Static CBM queries and lineage-context export configuration."""


CSV_FIELDS = ("repo_url", "CloneStatus", "IndexStatus", "ContextStatus")
CONTEXT_STATUS_PENDING = ""
CONTEXT_STATUS_COMPLETE = "Contexted"
GRAPH_QUERY_LIMIT = 100000
SMALL_GRAPH_NODE_LIMIT = 100
ARCHITECTURE_ASPECTS = ("all",)

SYMBOL_QUERY = f"""
MATCH (n)
RETURN n.label AS label,
       n.name AS name,
       n.qualified_name AS qualified_name,
       n.file_path AS file_path,
       n.start_line AS start_line,
       n.end_line AS end_line,
       n.signature AS signature,
       n.param_names AS param_names,
       n.param_types AS param_types,
       n.return_type AS return_type,
       n.parent_class AS parent_class,
       n.base_classes AS base_classes,
       n.decorators AS decorators,
       n.decorator_tags AS decorator_tags,
       n.method AS route_method,
       n.route_path AS route_path,
       n.key_path AS key_path,
       n.source AS discovery_source,
       n.transport AS transport,
       n.env_key AS env_key,
       n.is_entry_point AS is_entry_point,
       n.is_exported AS is_exported,
       n.is_test AS is_test,
       n.extension AS extension
LIMIT {GRAPH_QUERY_LIMIT}
""".strip()

RELATIONSHIP_QUERY = f"""
MATCH (source)-[relationship]->(target)
RETURN type(relationship) AS relationship,
       source.label AS source_label,
       source.name AS source_name,
       source.qualified_name AS source_qualified_name,
       source.file_path AS source_file_path,
       source.start_line AS source_start_line,
       source.end_line AS source_end_line,
       target.label AS target_label,
       target.name AS target_name,
       target.qualified_name AS target_qualified_name,
       target.file_path AS target_file_path,
       target.start_line AS target_start_line,
       target.end_line AS target_end_line,
       relationship.args AS arguments,
       relationship.callee AS callee,
       relationship.candidates AS candidates,
       relationship.confidence AS confidence,
       relationship.strategy AS strategy,
       relationship.url_path AS url_path,
       relationship.via AS via,
       relationship.handler AS handler,
       relationship.source AS discovery_source,
       relationship.transport AS transport,
       relationship.decorator AS decorator,
       relationship.local_name AS local_name
LIMIT {GRAPH_QUERY_LIMIT}
""".strip()

LINEAGE_RELATIONSHIPS = {
    "ASYNC_CALLS",
    "CALLS",
    "CONFIGURES",
    "CONSUMES",
    "CROSS_ASYNC_CALLS",
    "CROSS_CHANNEL",
    "CROSS_HTTP_CALLS",
    "DATA_FLOWS",
    "DECORATES",
    "DEFINES_METHOD",
    "EMITS",
    "HANDLES",
    "HTTP_CALLS",
    "IMPLEMENTS",
    "IMPORTS",
    "INHERITS",
    "OVERRIDE",
    "READS",
    "USAGE",
    "WRITES",
}

INTERFACE_LABELS = {
    "Channel",
    "Database",
    "EnvVar",
    "Queue",
    "Resource",
    "Route",
    "Table",
    "Topic",
}

INTERFACE_RELATIONSHIPS = {
    "ASYNC_CALLS",
    "CONFIGURES",
    "CONSUMES",
    "CROSS_ASYNC_CALLS",
    "CROSS_CHANNEL",
    "CROSS_HTTP_CALLS",
    "EMITS",
    "HANDLES",
    "HTTP_CALLS",
    "READS",
    "WRITES",
}

DIRECT_BOUNDARY_RELATIONSHIPS = {
    "ASYNC_CALLS",
    "CONSUMES",
    "CROSS_ASYNC_CALLS",
    "CROSS_CHANNEL",
    "CROSS_HTTP_CALLS",
    "DATA_FLOWS",
    "EMITS",
    "HANDLES",
    "HTTP_CALLS",
}

CONDITIONAL_BOUNDARY_RELATIONSHIPS = {"CONFIGURES", "READS", "WRITES"}
BOUNDARY_RESOURCE_LABELS = INTERFACE_LABELS | {"File"}

GRAPH_EXPANSION_RELATIONSHIPS = {
    "ASYNC_CALLS",
    "CALLS",
    "DATA_FLOWS",
    "IMPLEMENTS",
    "INHERITS",
    "OVERRIDE",
}

SOURCE_LABELS = {
    "Class",
    "Field",
    "Function",
    "Interface",
    "Method",
    "Module",
    "Variable",
}

CONFIGURATION_AND_SCHEMA_EXTENSIONS = {
    ".avsc",
    ".conf",
    ".graphql",
    ".json",
    ".properties",
    ".proto",
    ".sql",
    ".toml",
    ".xml",
    ".yaml",
    ".yml",
}

DATA_ARTIFACT_EXTENSIONS = {
    ".avro",
    ".csv",
    ".db",
    ".jsonl",
    ".ndjson",
    ".orc",
    ".parquet",
    ".sqlite",
    ".sqlite3",
    ".tsv",
    ".xls",
    ".xlsx",
}

LINEAGE_ARTIFACT_EXTENSIONS = (
    CONFIGURATION_AND_SCHEMA_EXTENSIONS | DATA_ARTIFACT_EXTENSIONS
)

GRAPH_SELECTION_RULES = (
    "select interface nodes and nodes carrying entry-point, route, semantic "
    "decorator-tag, transport, or environment metadata",
    "exclude test, generated, dependency, and CI symbols from Agent 1 context",
    "select both endpoints of direct boundary relationships; require a resource "
    "endpoint for CONFIGURES, READS, and WRITES",
    "expand up to two graph hops across code and data relationships",
    "select configuration and schema modules by indexed file extension",
    f"for graphs with at most {SMALL_GRAPH_NODE_LIMIT} nodes, include all "
    "non-documentation source modules",
    "retrieve one containing module per selected file when available",
    "record data-file modules as artifacts without embedding their contents",
)

CONTEXT_LIMITATIONS = (
    "Graph relationships are discovery evidence, not proof of field movement.",
    "Confirmed lineage requires source evidence such as assignments, SQL, schemas, "
    "mappings, serialization, or configuration.",
    "Source excerpts are selected from CBM graph metadata and retrieved by qualified "
    "name.",
    "Optional text search is a fallback for graph coverage gaps and is disabled "
    "unless --enable-text-fallback is supplied.",
    "The current Git commit is recorded, but CBM 0.8.1 does not expose the indexed "
    "commit SHA directly.",
)

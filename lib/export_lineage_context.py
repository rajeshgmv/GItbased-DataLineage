#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from config.lineage_context_config import (
    ARCHITECTURE_ASPECTS,
    BOUNDARY_RESOURCE_LABELS,
    CONDITIONAL_BOUNDARY_RELATIONSHIPS,
    CONFIGURATION_AND_SCHEMA_EXTENSIONS,
    CONTEXT_LIMITATIONS,
    CONTEXT_STATUS_COMPLETE,
    CSV_FIELDS,
    DATA_ARTIFACT_EXTENSIONS,
    DIRECT_BOUNDARY_RELATIONSHIPS,
    GRAPH_EXPANSION_RELATIONSHIPS,
    GRAPH_QUERY_LIMIT,
    GRAPH_SELECTION_RULES,
    INTERFACE_LABELS,
    INTERFACE_RELATIONSHIPS,
    LINEAGE_ARTIFACT_EXTENSIONS,
    LINEAGE_RELATIONSHIPS,
    RELATIONSHIP_QUERY,
    SMALL_GRAPH_NODE_LIMIT,
    SOURCE_LABELS,
    SYMBOL_QUERY,
)


SCRIPT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SCRIPT_DIR / ".env"
load_dotenv(ENV_FILE)


def configured_path(variable_name: str, default: Path) -> Path:
    """Return an absolute path from an environment variable or its default."""
    configured_value = os.getenv(variable_name)
    path = Path(configured_value).expanduser() if configured_value else default
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path.resolve()


PROJECT_DIR = configured_path("PROJECT_DIR", SCRIPT_DIR)
CBM_CACHE_DIR = configured_path("CBM_CACHE_DIR", PROJECT_DIR / ".cbm-cache")
REPO_LIST_FILE = configured_path("REPO_LIST_FILE", PROJECT_DIR / "git_repo_list.csv")
CLONE_DIR = configured_path("CLONE_DIR", PROJECT_DIR / "repo_local_clone")
CODEBASE_MEMORY_MCP_BIN = configured_path(
    "CODEBASE_MEMORY_MCP_BIN",
    PROJECT_DIR / ".venv" / "bin" / "codebase-memory-mcp",
)
LINEAGE_CONTEXT_DIR = configured_path(
    "LINEAGE_CONTEXT_DIR",
    PROJECT_DIR / "lineage_context",
)
FALLBACK_SEARCH_QUERY_FILE = (
    PROJECT_DIR / "config" / "lineage_fallback_search_queries.json"
)


def run_process(command, cwd=None, check=True):
    """Run a command with captured text output and raise a detailed error on failure."""
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{details}")
    return result


def run_cbm_tool(tool_name: str, arguments=None):
    """Invoke one CBM 0.8.1 CLI tool and parse its JSON response."""
    command = [str(CODEBASE_MEMORY_MCP_BIN), "cli", tool_name]
    if arguments:
        command.append(json.dumps(arguments, separators=(",", ":")))

    environment = os.environ.copy()
    environment["CBM_CACHE_DIR"] = str(CBM_CACHE_DIR)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"CBM tool failed: {tool_name}\n{details}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"CBM tool returned invalid JSON: {tool_name}\n{result.stdout.strip()}"
        ) from exc


def load_repository_rows(csv_path: Path):
    """Load indexed repositories from the status CSV and validate its header."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Repository CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(CSV_FIELDS):
            expected = ",".join(CSV_FIELDS)
            raise ValueError(f"Expected CSV header '{expected}' in {csv_path}")
        return [row for row in reader if (row.get("repo_url") or "").strip()]


def write_repository_rows(csv_path: Path, rows):
    """Atomically write repository statuses after a successful context export."""
    temporary_path = csv_path.with_suffix(f"{csv_path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(csv_path)


def repo_name_from_url(repo_url: str) -> str:
    """Derive the local clone directory name from a Git repository URL."""
    name = repo_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def load_fallback_search_queries(query_path: Path):
    """Load optional text-search definitions used only when fallback is enabled."""
    if not query_path.is_file():
        raise FileNotFoundError(f"Lineage search query file not found: {query_path}")
    with query_path.open("r", encoding="utf-8") as query_file:
        queries = json.load(query_file)
    if not isinstance(queries, list) or not queries:
        raise ValueError(f"Expected a non-empty JSON array in {query_path}")
    return queries


def table_to_records(table):
    """Convert CBM query_graph column/row output into named JSON records."""
    columns = table.get("columns", [])
    return [dict(zip(columns, row)) for row in table.get("rows", [])]


def has_metadata_value(value):
    """Return whether a CBM property contains a meaningful non-default value."""
    if value is None or value is False:
        return False
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "none", "null", "[]", "{}"}
    return bool(value)


def is_non_runtime_path(file_path):
    """Identify a test, generated, dependency, build, or CI file path."""
    file_path = (file_path or "").replace("\\", "/")
    path = Path(file_path)
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts.intersection({
        ".github",
        ".mvn",
        "__tests__",
        "build",
        "dist",
        "node_modules",
        "target",
        "test",
        "tests",
    }):
        return True

    file_name = path.name.lower()
    stem = path.stem.lower()
    return (
        file_name.startswith("test_")
        or stem == "test"
        or stem.endswith("_test")
        or stem.endswith("tests")
    )


def is_non_runtime_symbol(symbol):
    """Identify test and non-runtime CBM symbols excluded from Agent 1."""
    return (
        has_metadata_value(symbol.get("is_test"))
        or is_non_runtime_path(symbol.get("file_path"))
    )


def is_data_artifact_path(file_path):
    """Return whether a path identifies a data file that should not be embedded."""
    return Path(file_path or "").suffix.lower() in DATA_ARTIFACT_EXTENSIONS


def is_boundary_relationship(relationship):
    """Classify graph edges that cross or configure a data-system boundary."""
    relationship_type = relationship.get("relationship")
    if relationship_type in DIRECT_BOUNDARY_RELATIONSHIPS:
        return True
    if relationship_type not in CONDITIONAL_BOUNDARY_RELATIONSHIPS:
        return False
    return (
        relationship.get("source_label") in BOUNDARY_RESOURCE_LABELS
        or relationship.get("target_label") in BOUNDARY_RESOURCE_LABELS
    )


def is_context_relationship(relationship):
    """Keep graph edges used to discover or directly express lineage context."""
    return (
        is_boundary_relationship(relationship)
        or relationship.get("relationship") in GRAPH_EXPANSION_RELATIONSHIPS
    )


def normalize_relationship_modules(relationship):
    """Represent CBM Module endpoints as source files in the exported context."""
    normalized = dict(relationship)
    if normalized.get("source_label") == "Module":
        normalized["source_label"] = "SourceFile"
    if normalized.get("target_label") == "Module":
        normalized["target_label"] = "SourceFile"
    return normalized


def is_lineage_configuration_module(symbol):
    """Keep schema and runtime configuration modules while excluding UI messages/logs."""
    file_path = symbol.get("file_path") or ""
    path = Path(file_path)
    extension = (symbol.get("extension") or path.suffix).lower()
    if extension not in CONFIGURATION_AND_SCHEMA_EXTENSIONS:
        return False
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts.intersection({"i18n", "locale", "locales", "messages"}):
        return False
    file_name = path.name.lower()
    return not file_name.startswith(("log4j", "logback"))


def validate_graph_export_coverage(graph_schema, symbols, relationships):
    """Verify that graph queries returned every node and edge reported by CBM."""
    expected_nodes = sum(
        int(item.get("count", 0)) for item in graph_schema.get("node_labels", [])
    )
    expected_relationships = sum(
        int(item.get("count", 0)) for item in graph_schema.get("edge_types", [])
    )
    actual_nodes = len(symbols)
    actual_relationships = len(relationships)

    if expected_nodes != actual_nodes or expected_relationships != actual_relationships:
        raise RuntimeError(
            "CBM graph export is incomplete: "
            f"expected {expected_nodes} nodes/{expected_relationships} relationships, "
            f"received {actual_nodes} nodes/{actual_relationships} relationships. "
            f"Increase GRAPH_QUERY_LIMIT (currently {GRAPH_QUERY_LIMIT})."
        )

    return {
        "complete": True,
        "expected_nodes": expected_nodes,
        "exported_nodes": actual_nodes,
        "expected_relationships": expected_relationships,
        "exported_relationships": actual_relationships,
        "query_limit": GRAPH_QUERY_LIMIT,
    }


def compact_json_value(value):
    """Recursively remove null and empty JSON values while preserving false and zero."""
    if isinstance(value, dict):
        compacted = {}
        for key, child in value.items():
            compacted_child = compact_json_value(child)
            if is_empty_json_value(compacted_child):
                continue
            compacted[key] = compacted_child
        return compacted
    if isinstance(value, list):
        return [
            compacted_child
            for child in value
            if not is_empty_json_value(
                compacted_child := compact_json_value(child)
            )
        ]
    return value


def is_empty_json_value(value):
    """Return whether a JSON value carries no information for the lineage agent."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def build_compact_architecture(architecture):
    """Keep useful architecture facts while removing test-prone raw CBM sections."""
    languages = [
        item.get("language") if isinstance(item, dict) else item
        for item in architecture.get("languages", [])
    ]
    frameworks = [
        (
            item.get("framework") or item.get("name")
            if isinstance(item, dict)
            else item
        )
        for item in architecture.get("frameworks", [])
    ]
    entry_points = [
        entry_point
        for entry_point in architecture.get("entry_points", [])
        if not is_non_runtime_path(
            entry_point.get("file") or entry_point.get("file_path")
        )
    ]
    return compact_json_value({
        "project": architecture.get("project"),
        "languages": languages,
        "frameworks": frameworks,
        "entry_points": entry_points,
    })


def build_lineage_artifacts(symbols):
    """Convert selected data, schema, and configuration modules into file artifacts."""
    artifacts = []
    for symbol in symbols:
        if symbol.get("label") != "Module" or is_non_runtime_symbol(symbol):
            continue
        file_path = symbol.get("file_path") or ""
        extension = Path(file_path).suffix.lower()
        if extension not in LINEAGE_ARTIFACT_EXTENSIONS:
            continue
        if is_data_artifact_path(file_path):
            artifact_type = "data_file"
        elif extension in {".avsc", ".graphql", ".proto", ".sql"}:
            artifact_type = "schema_file"
        else:
            artifact_type = "configuration_file"
        artifacts.append({
            "artifact_type": artifact_type,
            "name": symbol.get("name"),
            "file_path": file_path,
            "format": extension.lstrip("."),
            "qualified_name": symbol.get("qualified_name"),
            "start_line": symbol.get("start_line"),
            "end_line": symbol.get("end_line"),
        })
    return compact_json_value(artifacts)


def count_records_by(records, property_name, output_name):
    """Count records by one property and return stable named count objects."""
    counts = defaultdict(int)
    for record in records:
        value = record.get(property_name)
        if value:
            counts[value] += 1
    return [
        {output_name: value, "count": count}
        for value, count in sorted(counts.items())
    ]


def build_graph_summary(project_name, coverage, symbols, relationships, artifacts):
    """Build a small selected-graph summary instead of exporting the raw schema."""
    return compact_json_value({
        "project": project_name,
        "raw_graph_coverage": coverage,
        "selected_node_labels": count_records_by(symbols, "label", "label"),
        "selected_relationship_types": count_records_by(
            relationships,
            "relationship",
            "type",
        ),
        "selected_artifact_types": count_records_by(
            artifacts,
            "artifact_type",
            "type",
        ),
    })


def build_agent_context(
    manifest,
    graph_summary,
    architecture,
    symbols,
    relationships,
    artifacts,
    interfaces,
    source_evidence,
):
    """Assemble the compact, test-free JSON document intended for Agent 1."""
    return compact_json_value({
        "manifest": manifest,
        "graph_summary": graph_summary,
        "architecture": architecture,
        "symbols": symbols,
        "relationships": relationships,
        "artifacts": artifacts,
        "interfaces": interfaces,
        "source_evidence": source_evidence,
    })


def select_graph_source_candidates(symbols, relationships):
    """Choose source symbols from CBM labels, properties, and graph connectivity."""
    symbols_by_qualified_name = {
        symbol["qualified_name"]: symbol
        for symbol in symbols
        if symbol.get("qualified_name")
    }
    modules_by_file = defaultdict(list)
    for symbol in symbols:
        if symbol.get("label") == "Module" and symbol.get("file_path"):
            modules_by_file[symbol["file_path"]].append(symbol)

    selected = {}

    def select_qualified_name(qualified_name, reason):
        """Add one known graph symbol to the candidate set with an audit reason."""
        symbol = symbols_by_qualified_name.get(qualified_name)
        if not symbol or is_non_runtime_symbol(symbol):
            return False
        entry = selected.setdefault(
            qualified_name,
            {"symbol": symbol, "selection_reasons": set()},
        )
        entry["selection_reasons"].add(reason)
        return True

    for symbol in symbols:
        if is_non_runtime_symbol(symbol):
            continue
        qualified_name = symbol.get("qualified_name")
        if symbol.get("label") in INTERFACE_LABELS:
            select_qualified_name(qualified_name, "interface_node")
        if has_metadata_value(symbol.get("is_entry_point")):
            select_qualified_name(qualified_name, "entry_point")
        if any(
            has_metadata_value(symbol.get(property_name))
            for property_name in (
                "decorator_tags",
                "route_method",
                "route_path",
                "transport",
                "env_key",
            )
        ):
            select_qualified_name(qualified_name, "lineage_metadata")

        if (
            symbol.get("label") == "Module"
            and is_lineage_configuration_module(symbol)
        ):
            select_qualified_name(qualified_name, "configuration_or_schema_module")

    for relationship in relationships:
        relationship_type = relationship.get("relationship")
        if not is_boundary_relationship(relationship):
            continue
        select_qualified_name(
            relationship.get("source_qualified_name"),
            f"boundary_relationship:{relationship_type}:source",
        )
        select_qualified_name(
            relationship.get("target_qualified_name"),
            f"boundary_relationship:{relationship_type}:target",
        )

    frontier = set(selected)
    for depth in range(1, 3):
        next_frontier = set()
        for relationship in relationships:
            relationship_type = relationship.get("relationship")
            if relationship_type not in GRAPH_EXPANSION_RELATIONSHIPS:
                continue
            source = relationship.get("source_qualified_name")
            target = relationship.get("target_qualified_name")
            if source in frontier and target not in selected:
                if select_qualified_name(
                    target,
                    f"graph_neighbor:{relationship_type}:depth_{depth}",
                ):
                    next_frontier.add(target)
            if target in frontier and source not in selected:
                if select_qualified_name(
                    source,
                    f"graph_neighbor:{relationship_type}:depth_{depth}",
                ):
                    next_frontier.add(source)
        frontier = next_frontier
        if not frontier:
            break

    if len(symbols) <= SMALL_GRAPH_NODE_LIMIT:
        for symbol in symbols:
            if is_non_runtime_symbol(symbol):
                continue
            file_path = symbol.get("file_path") or ""
            if symbol.get("label") != "Module" or not file_path:
                continue
            if Path(file_path).suffix.lower() in {".md", ".rst", ".txt"}:
                continue
            select_qualified_name(
                symbol.get("qualified_name"),
                "small_graph_source_module",
            )

    for entry in list(selected.values()):
        file_path = entry["symbol"].get("file_path")
        for module in modules_by_file.get(file_path, []):
            select_qualified_name(
                module.get("qualified_name"),
                f"containing_module:{entry['symbol'].get('label')}",
            )

    candidates = []
    for entry in selected.values():
        symbol = entry["symbol"]
        candidates.append({
            "qualified_name": symbol.get("qualified_name"),
            "label": symbol.get("label"),
            "name": symbol.get("name"),
            "file_path": symbol.get("file_path"),
            "start_line": symbol.get("start_line"),
            "end_line": symbol.get("end_line"),
            "selection_reasons": sorted(entry["selection_reasons"]),
        })
    candidates.sort(key=lambda item: (
        item.get("file_path") or "",
        int(item.get("start_line") or 0),
        item.get("qualified_name") or "",
    ))

    candidates_by_file = defaultdict(list)
    for candidate in candidates:
        if candidate.get("file_path") and candidate.get("label") in SOURCE_LABELS:
            candidates_by_file[candidate["file_path"]].append(candidate)

    snippet_targets = []
    for file_candidates in candidates_by_file.values():
        modules = [
            item for item in file_candidates if item.get("label") == "Module"
        ]
        source_modules = [
            item
            for item in modules
            if not is_data_artifact_path(item.get("file_path"))
        ]
        if source_modules:
            module = max(
                source_modules,
                key=lambda item: int(item.get("end_line") or 0)
                - int(item.get("start_line") or 0),
            )
            inherited_reasons = {
                reason
                for item in file_candidates
                for reason in item["selection_reasons"]
            }
            module["selection_reasons"] = sorted(inherited_reasons)
            snippet_targets.append(module)
        elif modules:
            continue
        else:
            snippet_targets.extend(file_candidates)
    snippet_targets.sort(key=lambda item: (
        item.get("file_path") or "",
        int(item.get("start_line") or 0),
        item.get("qualified_name") or "",
    ))

    return {
        "rules": list(GRAPH_SELECTION_RULES),
        "candidate_count": len(candidates),
        "snippet_target_count": len(snippet_targets),
        "candidates": candidates,
        "snippet_targets": snippet_targets,
    }


def read_indexed_source(repo_dir: Path, symbol):
    """Read the exact CBM-indexed file range when snippet retrieval is unavailable."""
    file_path = symbol.get("file_path")
    if not file_path:
        return None

    candidate_path = Path(file_path)
    if not candidate_path.is_absolute():
        candidate_path = repo_dir / candidate_path
    candidate_path = candidate_path.resolve()
    try:
        candidate_path.relative_to(repo_dir.resolve())
    except ValueError:
        return None
    if not candidate_path.is_file():
        return None

    lines = candidate_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start_line = max(int(symbol.get("start_line") or 1), 1)
    end_line = int(symbol.get("end_line") or len(lines))
    end_line = min(max(end_line, start_line), len(lines))
    return {
        "qualified_name": symbol.get("qualified_name"),
        "label": symbol.get("label"),
        "name": symbol.get("name"),
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "source": "\n".join(lines[start_line - 1:end_line]),
    }


def git_value(repo_dir: Path, *arguments, check=True):
    """Return trimmed output from a Git command executed in one cloned repository."""
    result = run_process(["git", *arguments], cwd=repo_dir, check=check)
    return result.stdout.strip()


def collect_git_metadata(repo_dir: Path, configured_url: str):
    """Capture immutable repository provenance for evidence and freshness checks."""
    remote_result = run_process(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_dir,
        check=False,
    )
    branch_result = run_process(
        ["git", "branch", "--show-current"],
        cwd=repo_dir,
        check=False,
    )
    return {
        "name": repo_dir.name,
        "configured_url": configured_url,
        "origin_url": remote_result.stdout.strip() or None,
        "branch": branch_result.stdout.strip() or None,
        "commit_sha": git_value(repo_dir, "rev-parse", "HEAD"),
        "commit_timestamp": git_value(repo_dir, "show", "-s", "--format=%cI", "HEAD"),
        "root_path": str(repo_dir),
        "working_tree_clean": not bool(git_value(repo_dir, "status", "--porcelain")),
    }


def select_repository(repo_name: str, rows):
    """Find one CSV repository row by its URL-derived local name."""
    for row in rows:
        configured_url = row["repo_url"].strip()
        if repo_name_from_url(configured_url) == repo_name:
            return row
    raise ValueError(f"Repository '{repo_name}' was not found in {REPO_LIST_FILE}")


def is_repository_context_pending(row):
    """Select rows with no context or a newly refreshed clone."""
    return (
        not (row.get("ContextStatus") or "").strip()
        or (row.get("CloneStatus") or "").strip() == "cloned again"
    )


def select_cbm_project(repo_dir: Path, projects):
    """Match a cloned repository to its CBM project using the canonical root path."""
    canonical_root = str(repo_dir.resolve())
    for project in projects:
        root_path = project.get("root_path")
        if root_path and str(Path(root_path).resolve()) == canonical_root:
            return project
    raise ValueError(f"No CBM project found for repository root: {canonical_root}")


def redact_source(source: str):
    """Remove obvious literal credentials while retaining lineage-relevant variable names."""
    if not source:
        return source, False
    pattern = re.compile(
        r"(?im)(\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\b\s*=\s*)"
        r"(['\"])(.*?)\2"
    )
    redacted, replacements = pattern.subn(r'\1"<REDACTED>"', source)
    return redacted, replacements > 0


def collect_text_fallback_evidence(project_name: str, search_queries):
    """Run optional CBM text searches for facts absent from graph-selected source."""
    snippets = {}
    raw_matches = {}
    searches = []
    any_redactions = False
    excluded_non_runtime_matches = 0
    excluded_data_artifact_matches = 0

    for definition in search_queries:
        arguments = {
            "project": project_name,
            "pattern": definition["pattern"],
            "regex": definition.get("regex", True),
            "mode": definition.get("mode", "full"),
            "limit": definition.get("limit", 200),
        }
        response = run_cbm_tool("search_code", arguments)
        result_count = len(response.get("results", []))
        total_results = response.get("total_results", result_count)
        searches.append({
            "name": definition["name"],
            "pattern": definition["pattern"],
            "result_count": result_count,
            "total_results": total_results,
            "total_grep_matches": response.get("total_grep_matches", 0),
            "truncated": total_results > result_count,
        })

        for result in response.get("results", []):
            if is_non_runtime_symbol({
                "file_path": result.get("file"),
                "is_test": result.get("is_test"),
            }):
                excluded_non_runtime_matches += 1
                continue
            if is_data_artifact_path(result.get("file")):
                excluded_data_artifact_matches += 1
                continue
            key = result.get("qualified_name") or (
                f"{result.get('file')}:{result.get('start_line')}:{result.get('end_line')}"
            )
            source, was_redacted = redact_source(result.get("source", ""))
            any_redactions = any_redactions or was_redacted
            if key not in snippets:
                snippets[key] = {
                    "node": result.get("node"),
                    "qualified_name": result.get("qualified_name"),
                    "label": (
                        "SourceFile"
                        if result.get("label") == "Module"
                        else result.get("label")
                    ),
                    "file_path": result.get("file"),
                    "start_line": result.get("start_line"),
                    "end_line": result.get("end_line"),
                    "match_lines": result.get("match_lines", []),
                    "matched_categories": [],
                    "source": source,
                }
            snippets[key]["matched_categories"].append(definition["name"])
            snippets[key]["match_lines"] = sorted(set(
                snippets[key]["match_lines"] + result.get("match_lines", [])
            ))

        for match in response.get("raw_matches", []):
            if is_non_runtime_symbol({"file_path": match.get("file")}):
                excluded_non_runtime_matches += 1
                continue
            if is_data_artifact_path(match.get("file")):
                excluded_data_artifact_matches += 1
                continue
            key = f"{match.get('file')}:{match.get('line')}:{match.get('text')}"
            if key not in raw_matches:
                text, was_redacted = redact_source(match.get("text", ""))
                any_redactions = any_redactions or was_redacted
                raw_matches[key] = {
                    **match,
                    "text": text,
                    "matched_categories": [],
                }
            raw_matches[key]["matched_categories"].append(definition["name"])

    return {
        "searches": searches,
        "snippets": list(snippets.values()),
        "raw_matches": list(raw_matches.values()),
        "excluded_non_runtime_matches": excluded_non_runtime_matches,
        "excluded_data_artifact_matches": excluded_data_artifact_matches,
        "redactions_applied": any_redactions,
    }


def collect_graph_source_evidence(
    project_name: str,
    repo_dir: Path,
    symbols,
    relationships,
    enable_text_fallback=False,
):
    """Retrieve source from graph-selected CBM symbols, with optional text fallback."""
    selection = select_graph_source_candidates(symbols, relationships)
    snippets = []
    retrieval_failures = []
    any_redactions = False

    for target in selection["snippet_targets"]:
        qualified_name = target.get("qualified_name")
        try:
            response = run_cbm_tool(
                "get_code_snippet",
                {"project": project_name, "qualified_name": qualified_name},
            )
            retrieval_method = "cbm_get_code_snippet"
        except RuntimeError as exc:
            response = read_indexed_source(repo_dir, target)
            retrieval_failures.append({
                "qualified_name": qualified_name,
                "file_path": target.get("file_path"),
                "error": str(exc),
                "recovered_from_indexed_location": response is not None,
            })
            retrieval_method = "indexed_location_fallback"

        if not response:
            continue
        source, was_redacted = redact_source(response.get("source", ""))
        any_redactions = any_redactions or was_redacted
        response_label = response.get("label") or target.get("label")
        snippets.append({
            "qualified_name": response.get("qualified_name") or qualified_name,
            "label": "SourceFile" if response_label == "Module" else response_label,
            "name": response.get("name") or target.get("name"),
            "file_path": response.get("file_path") or target.get("file_path"),
            "start_line": response.get("start_line") or target.get("start_line"),
            "end_line": response.get("end_line") or target.get("end_line"),
            "selection_reasons": target["selection_reasons"],
            "retrieval_method": retrieval_method,
            "source": source,
        })

    if enable_text_fallback:
        fallback_evidence = collect_text_fallback_evidence(
            project_name,
            load_fallback_search_queries(FALLBACK_SEARCH_QUERY_FILE),
        )
        text_fallback = {
            "enabled": True,
            "reason": (
                "Explicitly enabled to search for lineage facts that CBM did not "
                "represent as graph metadata or connected source symbols."
            ),
            **fallback_evidence,
        }
        any_redactions = (
            any_redactions or fallback_evidence.get("redactions_applied", False)
        )
    else:
        text_fallback = {
            "enabled": False,
        }

    semantic_candidates = [
        candidate
        for candidate in selection["candidates"]
        if candidate.get("label") != "Module"
    ]
    public_selection = {
        "rules": selection["rules"],
        "candidate_count": len(semantic_candidates),
        "source_file_count": len(selection["snippet_targets"]),
        "candidates": semantic_candidates,
    }
    return {
        "_selected_qualified_names": [
            candidate["qualified_name"]
            for candidate in selection["candidates"]
            if candidate.get("qualified_name")
        ],
        "discovery_mode": "graph_first",
        "selection": public_selection,
        "snippets": snippets,
        "retrieval_failures": retrieval_failures,
        "text_fallback": text_fallback,
        "redactions_applied": any_redactions,
    }


def write_json(path: Path, value):
    """Write compacted, readable UTF-8 JSON with a final newline."""
    path.write_text(
        json.dumps(compact_json_value(value), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def export_repository_context(repo_name: str, enable_text_fallback=False):
    """Export one indexed repository into an Agent 1 lineage evidence package."""
    rows = load_repository_rows(REPO_LIST_FILE)
    row = select_repository(repo_name, rows)
    if row.get("IndexStatus", "").strip() != "Indexed":
        raise ValueError(
            f"Repository '{repo_name}' must have IndexStatus=Indexed before export."
        )

    repo_dir = (CLONE_DIR / repo_name).resolve()
    if not (repo_dir / ".git").is_dir():
        raise FileNotFoundError(f"Cloned Git repository not found: {repo_dir}")
    if not CODEBASE_MEMORY_MCP_BIN.is_file():
        raise FileNotFoundError(f"CBM executable not found: {CODEBASE_MEMORY_MCP_BIN}")

    os.environ["CBM_CACHE_DIR"] = str(CBM_CACHE_DIR)
    project_list = run_cbm_tool("list_projects").get("projects", [])
    cbm_project = select_cbm_project(repo_dir, project_list)
    project_name = cbm_project["name"]

    index_status = run_cbm_tool("index_status", {"project": project_name})
    if index_status.get("status") != "ready":
        raise RuntimeError(f"CBM project is not ready: {index_status}")

    graph_schema = run_cbm_tool("get_graph_schema", {"project": project_name})
    architecture = run_cbm_tool(
        "get_architecture",
        {"project": project_name, "aspects": list(ARCHITECTURE_ASPECTS)},
    )
    symbol_table = run_cbm_tool(
        "query_graph",
        {
            "project": project_name,
            "query": SYMBOL_QUERY,
            "max_rows": GRAPH_QUERY_LIMIT,
        },
    )
    relationship_table = run_cbm_tool(
        "query_graph",
        {
            "project": project_name,
            "query": RELATIONSHIP_QUERY,
            "max_rows": GRAPH_QUERY_LIMIT,
        },
    )

    symbols = table_to_records(symbol_table)
    all_relationships = table_to_records(relationship_table)
    graph_export_coverage = validate_graph_export_coverage(
        graph_schema,
        symbols,
        all_relationships,
    )
    relationships = [
        relationship
        for relationship in all_relationships
        if relationship.get("relationship") in LINEAGE_RELATIONSHIPS
    ]
    source_evidence = collect_graph_source_evidence(
        project_name,
        repo_dir,
        symbols,
        relationships,
        enable_text_fallback=enable_text_fallback,
    )
    selected_qualified_names = set(
        source_evidence.pop("_selected_qualified_names")
    )
    selected_symbols_with_modules = [
        symbol
        for symbol in symbols
        if symbol.get("qualified_name") in selected_qualified_names
    ]
    selected_symbols = [
        symbol
        for symbol in selected_symbols_with_modules
        if symbol.get("label") != "Module"
    ]
    artifacts = build_lineage_artifacts(selected_symbols_with_modules)
    selected_relationships = [
        normalize_relationship_modules(relationship)
        for relationship in relationships
        if (
            relationship.get("source_qualified_name") in selected_qualified_names
            and relationship.get("target_qualified_name") in selected_qualified_names
            and is_context_relationship(relationship)
        )
    ]
    interfaces = {
        "nodes": [
            symbol
            for symbol in selected_symbols
            if symbol.get("label") in INTERFACE_LABELS
        ],
        "relationships": [
            relationship
            for relationship in selected_relationships
            if relationship.get("relationship") in INTERFACE_RELATIONSHIPS
        ],
    }
    compact_architecture = build_compact_architecture(architecture)
    graph_summary = build_graph_summary(
        project_name,
        graph_export_coverage,
        selected_symbols,
        selected_relationships,
        artifacts,
    )

    exported_at = datetime.now(timezone.utc).isoformat()
    repository = collect_git_metadata(repo_dir, row["repo_url"].strip())
    completed_clone_status = (
        "cloned"
        if row.get("CloneStatus", "").strip() == "cloned again"
        else row.get("CloneStatus", "").strip()
    )
    manifest = {
        "lineage_context_schema_version": "1.2",
        "exported_at": exported_at,
        "repository": repository,
        "csv_status": {
            "CloneStatus": completed_clone_status,
            "IndexStatus": row.get("IndexStatus", "").strip(),
            "ContextStatus": CONTEXT_STATUS_COMPLETE,
        },
        "codebase_memory": {
            "version": run_process(
                [str(CODEBASE_MEMORY_MCP_BIN), "--version"]
            ).stdout.strip(),
            "project": project_name,
            "root_path": cbm_project.get("root_path"),
            "index_status": index_status,
            "graph_export_coverage": graph_export_coverage,
        },
        "agent_context_scope": {
            "test_files_excluded": True,
            "module_records_excluded": True,
            "empty_attributes_excluded": True,
            "selected_symbols": len(selected_symbols),
            "selected_relationships": len(selected_relationships),
            "lineage_artifacts": len(artifacts),
            "source_snippets": len(source_evidence["snippets"]),
        },
        "limitations": list(CONTEXT_LIMITATIONS),
        "files": {
            "graph_summary": "graph-schema.json",
            "architecture": "architecture.json",
            "symbols": "symbols.json",
            "relationships": "relationships.json",
            "artifacts": "artifacts.json",
            "interfaces": "interfaces.json",
            "source_evidence": "source-evidence.json",
            "combined_context": "context.json",
        },
    }

    combined_context = build_agent_context(
        manifest,
        graph_summary,
        compact_architecture,
        selected_symbols,
        selected_relationships,
        artifacts,
        interfaces,
        source_evidence,
    )

    output_dir = LINEAGE_CONTEXT_DIR / repo_name
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "manifest.json", manifest)
    write_json(output_dir / "graph-schema.json", graph_summary)
    write_json(output_dir / "architecture.json", compact_architecture)
    write_json(output_dir / "symbols.json", selected_symbols)
    write_json(output_dir / "relationships.json", selected_relationships)
    write_json(output_dir / "artifacts.json", artifacts)
    write_json(output_dir / "interfaces.json", interfaces)
    write_json(output_dir / "source-evidence.json", source_evidence)
    write_json(output_dir / "context.json", combined_context)
    row["CloneStatus"] = completed_clone_status
    row["ContextStatus"] = CONTEXT_STATUS_COMPLETE
    write_repository_rows(REPO_LIST_FILE, rows)
    return output_dir


def export_pending_repository_contexts(enable_text_fallback=False):
    """Export every indexed row with a blank context or a refreshed clone."""
    rows = load_repository_rows(REPO_LIST_FILE)
    pending_rows = [row for row in rows if is_repository_context_pending(row)]
    if not pending_rows:
        print("No repositories require a lineage context export.")
        return []

    output_directories = []
    failures = []
    for row in pending_rows:
        repo_name = repo_name_from_url(row["repo_url"].strip())
        if row.get("IndexStatus", "").strip() != "Indexed":
            print(
                f"Skipping context for {repo_name}: "
                f"IndexStatus is '{row.get('IndexStatus', '').strip()}'."
            )
            continue

        print(f"Creating lineage context for: {repo_name}")
        try:
            output_dir = export_repository_context(
                repo_name,
                enable_text_fallback=enable_text_fallback,
            )
            output_directories.append(output_dir)
            print(f"Finished lineage context for: {repo_name}")
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"{repo_name}: {exc}")
            print(f"ERROR: {repo_name}: {exc}", file=sys.stderr)

    if failures:
        details = "\n".join(f"- {failure}" for failure in failures)
        raise RuntimeError(f"Some context exports failed:\n{details}")

    return output_directories


def parse_args():
    """Parse either one repository or the pending-repository batch mode."""
    parser = argparse.ArgumentParser(
        description="Export indexed repositories for the repository-lineage agent."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--repo",
        help="Repository directory name from git_repo_list.csv, such as crypto-kaka-rag.",
    )
    selection.add_argument(
        "--all-pending",
        action="store_true",
        help=(
            "Export every indexed row whose ContextStatus is blank or whose "
            "CloneStatus is cloned again."
        ),
    )
    parser.add_argument(
        "--enable-text-fallback",
        action="store_true",
        help=(
            "Also run optional text searches for lineage evidence absent from the "
            "CBM graph. Disabled by default."
        ),
    )
    return parser.parse_args()


def main():
    """Run one repository export or all pending exports requested by the CLI."""
    args = parse_args()
    try:
        if args.all_pending:
            output_dirs = export_pending_repository_contexts(
                enable_text_fallback=args.enable_text_fallback,
            )
        else:
            output_dirs = [export_repository_context(
                args.repo,
                enable_text_fallback=args.enable_text_fallback,
            )]
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    for output_dir in output_dirs:
        print(f"Lineage context exported to: {output_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate repository-lineage JSON and render its deterministic Markdown view."""

import argparse
import json
import sys
from pathlib import Path


SCHEMA_VERSION = "repository-lineage/1.0"
REQUIRED_TOP_LEVEL_SECTIONS = {
    "schema_version",
    "repository",
    "input_coverage",
    "components",
    "data_elements",
    "boundary_contracts",
    "lineage_flows",
    "end_to_end_paths",
    "issues",
    "evidence",
}
LIST_SECTIONS = (
    "input_coverage",
    "components",
    "data_elements",
    "boundary_contracts",
    "lineage_flows",
    "end_to_end_paths",
    "issues",
    "evidence",
)
CONFIDENCE_VALUES = {"confirmed", "partial", "inferred"}
COMPONENT_KINDS = {
    "service",
    "external_service",
    "external_api",
    "database",
    "stream",
    "file",
    "batch_job",
    "unknown",
}
CONTRACT_DIRECTIONS = {"inbound", "outbound"}
CONTRACT_MECHANISMS = {
    "http",
    "graphql",
    "grpc",
    "soap",
    "kafka",
    "queue",
    "database",
    "file",
    "object_storage",
    "other",
}
FLOW_TYPES = {
    "service_to_service",
    "external_api_to_service",
    "service_to_external_api",
    "database_to_service",
    "service_to_database",
    "database_to_database",
    "file_to_service",
    "service_to_file",
    "file_to_database",
    "database_to_file",
    "service_to_stream",
    "stream_to_service",
    "file_to_file",
    "internal",
}
TRANSFORMATION_TYPES = {
    "none",
    "rename",
    "cast",
    "format",
    "parse",
    "filter",
    "derive",
    "aggregate",
    "serialize",
    "deserialize",
    "constant",
    "enrich",
    "lookup",
    "unknown",
}
ISSUE_TYPES = {
    "missing_contract",
    "missing_endpoint",
    "missing_schema",
    "unresolved_alias",
    "unresolved_consumer",
    "unresolved_producer",
    "locator_mismatch",
    "incomplete_mapping",
    "other",
}
ISSUE_SEVERITIES = {"high", "medium", "low"}


def load_lineage_json(input_path: Path) -> dict:
    """Load one repository-lineage JSON document from disk."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Lineage JSON file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as input_file:
        data = json.load(input_file)
    if not isinstance(data, dict):
        raise ValueError("The lineage JSON root must be an object")
    return data


def require_keys(record: dict, keys: tuple[str, ...], location: str) -> None:
    """Require a record to contain each named property."""
    missing = [key for key in keys if key not in record]
    if missing:
        raise ValueError(f"{location} is missing required properties: {', '.join(missing)}")


def require_enum(value: str, allowed: set[str], location: str) -> None:
    """Require a string value to belong to an allowed set."""
    if value not in allowed:
        expected = ", ".join(sorted(allowed))
        raise ValueError(f"{location} has invalid value '{value}'; expected one of: {expected}")


def build_unique_index(records: list[dict], id_field: str, section: str) -> dict[str, dict]:
    """Index records by ID and reject missing or duplicate identifiers."""
    index = {}
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{section}[{position}] must be an object")
        identifier = record.get(id_field)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"{section}[{position}].{id_field} must be a non-empty string")
        if identifier in index:
            raise ValueError(f"Duplicate {id_field} '{identifier}' in {section}")
        index[identifier] = record
    return index


def validate_references(values: list[str], index: dict[str, dict], location: str) -> None:
    """Require every referenced identifier to exist in its target index."""
    missing = sorted({value for value in values if value not in index})
    if missing:
        raise ValueError(f"{location} references unknown IDs: {', '.join(missing)}")


def reject_duplicate_keys(records: list[dict], key_builder, description: str) -> None:
    """Reject records that share a semantic deduplication key."""
    seen = set()
    for record in records:
        key = key_builder(record)
        if key in seen:
            raise ValueError(f"Duplicate {description} key: {key}")
        seen.add(key)


def validate_no_empty_scalars(value, location: str = "root") -> None:
    """Reject null values and empty strings anywhere in the canonical document."""
    if value is None or value == "":
        raise ValueError(f"{location} contains a null or empty-string value")
    if isinstance(value, dict):
        for key, child in value.items():
            validate_no_empty_scalars(child, f"{location}.{key}")
    elif isinstance(value, list):
        for position, child in enumerate(value):
            validate_no_empty_scalars(child, f"{location}[{position}]")


def validate_confidence(record: dict, location: str, issue_index: dict[str, dict]) -> None:
    """Validate confidence and require issues for partial or inferred records."""
    confidence = record.get("confidence")
    require_enum(confidence, CONFIDENCE_VALUES, f"{location}.confidence")
    issue_ids = record.get("issue_ids", [])
    if not isinstance(issue_ids, list):
        raise ValueError(f"{location}.issue_ids must be an array")
    validate_references(issue_ids, issue_index, f"{location}.issue_ids")
    if confidence != "confirmed" and not issue_ids:
        raise ValueError(f"{location} must reference an issue when confidence is {confidence}")


def validate_lineage(data: dict) -> dict[str, dict[str, dict]]:
    """Validate the canonical lineage schema, references, and deduplication rules."""
    actual_sections = set(data)
    if actual_sections != REQUIRED_TOP_LEVEL_SECTIONS:
        missing = sorted(REQUIRED_TOP_LEVEL_SECTIONS - actual_sections)
        extra = sorted(actual_sections - REQUIRED_TOP_LEVEL_SECTIONS)
        raise ValueError(f"Invalid top-level sections; missing={missing}, extra={extra}")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version '{data['schema_version']}'; expected '{SCHEMA_VERSION}'"
        )
    if not isinstance(data["repository"], dict):
        raise ValueError("repository must be an object")
    require_keys(data["repository"], ("name",), "repository")
    for section in LIST_SECTIONS:
        if not isinstance(data[section], list):
            raise ValueError(f"{section} must be an array")

    indexes = {
        "components": build_unique_index(data["components"], "component_id", "components"),
        "elements": build_unique_index(data["data_elements"], "element_id", "data_elements"),
        "contracts": build_unique_index(
            data["boundary_contracts"], "contract_id", "boundary_contracts"
        ),
        "flows": build_unique_index(data["lineage_flows"], "flow_id", "lineage_flows"),
        "paths": build_unique_index(data["end_to_end_paths"], "path_id", "end_to_end_paths"),
        "issues": build_unique_index(data["issues"], "issue_id", "issues"),
        "evidence": build_unique_index(data["evidence"], "evidence_id", "evidence"),
    }

    coverage_sections = []
    for position, coverage in enumerate(data["input_coverage"]):
        require_keys(coverage, ("section", "records_considered", "used_for"), f"input_coverage[{position}]")
        coverage_sections.append(coverage["section"])
    if len(coverage_sections) != len(set(coverage_sections)):
        raise ValueError("input_coverage contains duplicate section names")

    for position, component in enumerate(data["components"]):
        location = f"components[{position}]"
        require_keys(
            component,
            ("component_id", "name", "kind", "raw_locator", "normalized_locator", "evidence_ids"),
            location,
        )
        require_enum(component["kind"], COMPONENT_KINDS, f"{location}.kind")
        validate_references(component["evidence_ids"], indexes["evidence"], f"{location}.evidence_ids")

    for position, element in enumerate(data["data_elements"]):
        location = f"data_elements[{position}]"
        require_keys(
            element,
            (
                "element_id",
                "name",
                "element_path",
                "component_id",
                "container",
                "data_type",
                "aliases",
                "evidence_ids",
            ),
            location,
        )
        validate_references([element["component_id"]], indexes["components"], f"{location}.component_id")
        validate_references(element["evidence_ids"], indexes["evidence"], f"{location}.evidence_ids")

    for position, contract in enumerate(data["boundary_contracts"]):
        location = f"boundary_contracts[{position}]"
        require_keys(
            contract,
            (
                "contract_id",
                "direction",
                "mechanism",
                "operation",
                "local_component_id",
                "remote_component_id",
                "raw_locator",
                "normalized_locator",
                "data_element_ids",
                "schema_signature",
                "confidence",
                "evidence_ids",
            ),
            location,
        )
        require_enum(contract["direction"], CONTRACT_DIRECTIONS, f"{location}.direction")
        require_enum(contract["mechanism"], CONTRACT_MECHANISMS, f"{location}.mechanism")
        validate_references(
            [contract["local_component_id"], contract["remote_component_id"]],
            indexes["components"],
            f"{location}.components",
        )
        validate_references(contract["data_element_ids"], indexes["elements"], f"{location}.data_element_ids")
        validate_references(contract["evidence_ids"], indexes["evidence"], f"{location}.evidence_ids")
        validate_confidence(contract, location, indexes["issues"])

    for position, flow in enumerate(data["lineage_flows"]):
        location = f"lineage_flows[{position}]"
        require_keys(
            flow,
            (
                "flow_id",
                "flow_type",
                "source_component_id",
                "target_component_id",
                "operation",
                "mechanism",
                "element_mappings",
                "confidence",
                "evidence_ids",
            ),
            location,
        )
        require_enum(flow["flow_type"], FLOW_TYPES, f"{location}.flow_type")
        validate_references(
            [flow["source_component_id"], flow["target_component_id"]],
            indexes["components"],
            f"{location}.components",
        )
        validate_references(flow["evidence_ids"], indexes["evidence"], f"{location}.evidence_ids")
        if not isinstance(flow["element_mappings"], list):
            raise ValueError(f"{location}.element_mappings must be an array")
        for mapping_position, mapping in enumerate(flow["element_mappings"]):
            mapping_location = f"{location}.element_mappings[{mapping_position}]"
            require_keys(
                mapping,
                (
                    "source_element_ids",
                    "target_element_id",
                    "transformation_type",
                    "expression",
                    "evidence_ids",
                ),
                mapping_location,
            )
            if not mapping["source_element_ids"]:
                raise ValueError(f"{mapping_location}.source_element_ids must not be empty")
            validate_references(
                mapping["source_element_ids"] + [mapping["target_element_id"]],
                indexes["elements"],
                f"{mapping_location}.elements",
            )
            require_enum(
                mapping["transformation_type"],
                TRANSFORMATION_TYPES,
                f"{mapping_location}.transformation_type",
            )
            validate_references(
                mapping["evidence_ids"], indexes["evidence"], f"{mapping_location}.evidence_ids"
            )
        validate_confidence(flow, location, indexes["issues"])

    for position, path in enumerate(data["end_to_end_paths"]):
        location = f"end_to_end_paths[{position}]"
        require_keys(
            path,
            (
                "path_id",
                "name",
                "flow_ids",
                "source_component_id",
                "target_component_id",
                "data_element_ids",
                "confidence",
                "issue_ids",
            ),
            location,
        )
        if not path["flow_ids"]:
            raise ValueError(f"{location}.flow_ids must not be empty")
        validate_references(path["flow_ids"], indexes["flows"], f"{location}.flow_ids")
        validate_references(
            [path["source_component_id"], path["target_component_id"]],
            indexes["components"],
            f"{location}.components",
        )
        validate_references(path["data_element_ids"], indexes["elements"], f"{location}.data_element_ids")
        current_component = path["source_component_id"]
        for flow_id in path["flow_ids"]:
            flow = indexes["flows"][flow_id]
            if flow["source_component_id"] != current_component:
                raise ValueError(f"{location} has a discontinuity before flow {flow_id}")
            current_component = flow["target_component_id"]
        if current_component != path["target_component_id"]:
            raise ValueError(f"{location} does not end at its target_component_id")
        validate_confidence(path, location, indexes["issues"])

    all_related_ids = set().union(*(set(index) for index in indexes.values()))
    for position, issue in enumerate(data["issues"]):
        location = f"issues[{position}]"
        require_keys(
            issue,
            ("issue_id", "type", "severity", "description", "related_ids", "evidence_ids"),
            location,
        )
        require_enum(issue["type"], ISSUE_TYPES, f"{location}.type")
        require_enum(issue["severity"], ISSUE_SEVERITIES, f"{location}.severity")
        missing_related = sorted(set(issue["related_ids"]) - all_related_ids)
        if missing_related:
            raise ValueError(f"{location}.related_ids references unknown IDs: {', '.join(missing_related)}")
        validate_references(issue["evidence_ids"], indexes["evidence"], f"{location}.evidence_ids")

    for position, evidence in enumerate(data["evidence"]):
        location = f"evidence[{position}]"
        require_keys(
            evidence,
            (
                "evidence_id",
                "file_path",
                "start_line",
                "end_line",
                "qualified_name",
                "evidence_type",
            ),
            location,
        )
        if evidence["start_line"] <= 0 or evidence["end_line"] < evidence["start_line"]:
            raise ValueError(f"{location} has an invalid source range")
        if "excerpt" in evidence and len(evidence["excerpt"].splitlines()) > 3:
            raise ValueError(f"{location}.excerpt exceeds three lines")

    reject_duplicate_keys(
        data["components"],
        lambda item: (item["kind"], item["normalized_locator"]),
        "component",
    )
    reject_duplicate_keys(
        data["data_elements"],
        lambda item: (item["component_id"], item["container"], item["element_path"]),
        "data element",
    )
    reject_duplicate_keys(
        data["boundary_contracts"],
        lambda item: (
            item["direction"],
            item["mechanism"],
            item["normalized_locator"],
            item["operation"],
        ),
        "boundary contract",
    )
    reject_duplicate_keys(
        data["lineage_flows"],
        lambda item: (
            item["source_component_id"],
            item["target_component_id"],
            item["operation"],
            tuple(
                sorted(
                    (
                        tuple(sorted(mapping["source_element_ids"])),
                        mapping["target_element_id"],
                        mapping["transformation_type"],
                    )
                    for mapping in item["element_mappings"]
                )
            ),
        ),
        "lineage flow",
    )
    reject_duplicate_keys(
        data["end_to_end_paths"],
        lambda item: tuple(item["flow_ids"]),
        "end-to-end path",
    )
    reject_duplicate_keys(
        data["evidence"],
        lambda item: (
            item["file_path"],
            item["start_line"],
            item["end_line"],
            item["qualified_name"],
        ),
        "evidence",
    )
    validate_no_empty_scalars(data)
    return indexes


def markdown_cell(value) -> str:
    """Escape one scalar or list for safe use inside a Markdown table cell."""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value) if value else "—"
    text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def ordered_unique(values: list[str]) -> list[str]:
    """Return values once each while preserving their first-seen order."""
    return list(dict.fromkeys(values))


def render_table(headers: tuple[str, ...], rows: list[list[str]]) -> list[str]:
    """Render a GitHub-flavored Markdown table as individual lines."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(cell) for cell in row) + " |")
    return lines


def render_flow_row(flow: dict) -> list[str]:
    """Convert one lineage flow into the required Markdown table columns."""
    mappings = []
    transformations = []
    for mapping in flow["element_mappings"]:
        mappings.append(
            f"{'+'.join(mapping['source_element_ids'])}→{mapping['target_element_id']}"
        )
        transformations.append(mapping["transformation_type"])
    return [
        flow["flow_id"],
        flow["source_component_id"],
        flow["target_component_id"],
        f"{flow['operation']} / {flow['mechanism']}",
        "; ".join(mappings) if mappings else "—",
        "; ".join(ordered_unique(transformations)) if transformations else "—",
        flow["confidence"],
        ", ".join(flow["evidence_ids"]),
    ]


def render_contract_row(contract: dict) -> list[str]:
    """Convert one boundary contract into the required Markdown table columns."""
    return [
        contract["contract_id"],
        contract["direction"],
        contract["mechanism"],
        contract["normalized_locator"],
        ", ".join(contract["data_element_ids"]),
        contract["confidence"],
        ", ".join(contract.get("issue_ids", [])) or "—",
    ]


def render_path_row(path: dict, flow_index: dict[str, dict]) -> list[str]:
    """Convert one validated end-to-end path into its Markdown table columns."""
    path_parts = [path["source_component_id"]]
    for flow_id in path["flow_ids"]:
        path_parts.extend((flow_id, flow_index[flow_id]["target_component_id"]))
    return [
        path["path_id"],
        " → ".join(path_parts),
        ", ".join(path["data_element_ids"]),
        path["confidence"],
        ", ".join(path.get("issue_ids", [])) or "—",
    ]


def render_issue_row(issue: dict) -> list[str]:
    """Convert one unresolved issue into the required Markdown table columns."""
    return [
        issue["issue_id"],
        issue["type"],
        issue["severity"],
        issue["description"],
        ", ".join(issue["related_ids"]),
        ", ".join(issue["evidence_ids"]),
    ]


def render_markdown(data: dict, indexes: dict[str, dict[str, dict]]) -> str:
    """Render validated repository lineage into the canonical Markdown view."""
    sections = [
        f"# Repository Lineage: {data['repository']['name']}",
        "",
        "## Data Movements",
        "",
    ]
    sections.extend(
        render_table(
            (
                "Flow ID",
                "From",
                "To",
                "Operation / Mechanism",
                "Data Elements",
                "Transformations",
                "Confidence",
                "Evidence",
            ),
            [render_flow_row(flow) for flow in data["lineage_flows"]],
        )
    )
    sections.extend(("", "## Boundary Contracts for Agent 2", ""))
    sections.extend(
        render_table(
            (
                "Contract ID",
                "Direction",
                "Mechanism",
                "Normalized Locator",
                "Data Elements",
                "Confidence",
                "Issues",
            ),
            [render_contract_row(contract) for contract in data["boundary_contracts"]],
        )
    )
    sections.extend(("", "## End-to-End Paths Within This Repository", ""))
    sections.extend(
        render_table(
            ("Path ID", "Path", "Data Elements", "Confidence", "Issues"),
            [render_path_row(path, indexes["flows"]) for path in data["end_to_end_paths"]],
        )
    )
    sections.extend(("", "## Unresolved Issues", ""))
    sections.extend(
        render_table(
            ("Issue ID", "Type", "Severity", "Description", "Related IDs", "Evidence"),
            [render_issue_row(issue) for issue in data["issues"]],
        )
    )
    return "\n".join(sections) + "\n"


def write_markdown(output_path: Path, markdown: str) -> None:
    """Atomically write rendered Markdown without leaving a partial output file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(markdown, encoding="utf-8")
    temporary_path.replace(output_path)


def render_repository_lineage(input_path: Path, output_path: Path | None = None) -> Path:
    """Load, validate, and render one repository-lineage JSON document."""
    resolved_input = input_path.expanduser().resolve()
    resolved_output = (
        output_path.expanduser().resolve()
        if output_path is not None
        else resolved_input.with_name("repo-lineage.md")
    )
    data = load_lineage_json(resolved_input)
    indexes = validate_lineage(data)
    write_markdown(resolved_output, render_markdown(data, indexes))
    return resolved_output


def parse_arguments() -> argparse.Namespace:
    """Parse command-line paths for one JSON-to-Markdown conversion."""
    parser = argparse.ArgumentParser(
        description="Validate repo-lineage.json and generate deterministic Markdown."
    )
    parser.add_argument("input_json", type=Path, help="Path to repo-lineage.json")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Markdown output path; defaults to repo-lineage.md beside the input",
    )
    return parser.parse_args()


def main() -> int:
    """Run the renderer CLI and report validation or filesystem failures."""
    arguments = parse_arguments()
    try:
        output_path = render_repository_lineage(arguments.input_json, arguments.output)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Generated Markdown: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

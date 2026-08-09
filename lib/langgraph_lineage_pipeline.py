#!/usr/bin/env python3
"""Run lineage agents with LangGraph and LangChain's Gemini integration."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict

from dotenv import load_dotenv

from lib.render_repository_lineage import validate_lineage


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AGENT1_PROMPT = (
    PROJECT_ROOT / "prompts" / "agent1_repository_lineage_langgraph.agent.md"
)
DEFAULT_AGENT2_PROMPT = (
    PROJECT_ROOT / "prompts" / "agent2_cross_repository_lineage_langgraph.agent.md"
)
DEFAULT_CONTEXT_ROOT = PROJECT_ROOT / "lineage_context"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "lineage_output"
AGENT1_MODEL = "gemini-2.5-flash"
AGENT2_MODEL = "gemini-2.5-flash"
AGENT1_THINKING_BUDGET = 1_024
AGENT2_THINKING_BUDGET = 8_192
DEFAULT_MAX_REQUEST_CHARACTERS = 260_000
DEFAULT_MAX_COMPLETION_TOKENS = 32_768

AGENT1_REQUIRED_REPOSITORY_FIELDS = {
    "name": ("manifest", "repository", "name"),
    "origin_url": ("manifest", "repository", "origin_url"),
    "commit_sha": ("manifest", "repository", "commit_sha"),
    "branch": ("manifest", "repository", "branch"),
    "context_exported_at": ("manifest", "exported_at"),
}

HIGH_LEVEL_HEADERS = (
    "Flow ID",
    "Source Application",
    "Target Application",
    "Mechanism",
    "Operation",
    "Shared Boundary",
    "Data Summary",
    "Confidence",
    "Issues",
)

DETAIL_HEADERS = (
    "Detail ID",
    "Flow ID",
    "Source Application",
    "Source Contract / Flow",
    "Source Data Element(s)",
    "Source Type",
    "Source Raw / Normalized Locator",
    "Mechanism",
    "Operation",
    "Transformation Chain",
    "Target Application",
    "Target Contract / Flow",
    "Target Data Element",
    "Target Type",
    "Target Raw / Normalized Locator",
    "Confidence",
    "Evidence",
    "Issues",
)


class PipelineState(TypedDict, total=False):
    """State passed between the deterministic LangGraph stages."""

    repositories: list[str]
    contexts: dict[str, dict[str, Any]]
    agent1_prompt: str
    agent2_prompt: str
    agent1_outputs: dict[str, dict[str, Any]]
    final_report: str
    written_files: list[str]


class LineageModel(Protocol):
    """Minimal model interface used by the graph and offline tests."""

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_output: bool,
    ) -> str:
        """Return one model completion."""


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime configuration for one pipeline execution."""

    context_root: Path
    output_root: Path
    agent1_prompt_path: Path
    agent2_prompt_path: Path
    repositories: tuple[str, ...] = ()
    all_repositories: bool = False
    max_request_characters: int = DEFAULT_MAX_REQUEST_CHARACTERS
    validation_retries: int = 1


class LangChainLineageModel:
    """LangChain chat-model adapter used by the LangGraph nodes."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        thinking_budget: int = AGENT2_THINKING_BUDGET,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        max_retries: int = 4,
    ) -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError(
                "The LangChain Google Generative AI integration is not installed; run "
                "python3 -m pip install -r requirements.txt"
            ) from exc

        self.chat_model = ChatGoogleGenerativeAI(
            api_key=api_key,
            model=model,
            thinking_budget=thinking_budget,
            max_tokens=max_completion_tokens,
            max_retries=max_retries,
            temperature=0,
        )
        self.json_model = self.chat_model.bind(
            response_mime_type="application/json"
        )

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_output: bool,
    ) -> str:
        messages = [
            ("system", system_prompt),
            ("human", user_prompt),
        ]
        runnable = self.json_model if json_output else self.chat_model
        response = runnable.invoke(messages)
        finish_reason = response.response_metadata.get("finish_reason")
        if getattr(finish_reason, "name", finish_reason) in {
            "length",
            "MAX_TOKENS",
        }:
            raise RuntimeError(
                "The model stopped at the completion-token limit; increase "
                "--max-completion-tokens or reduce the selected context"
            )
        content = response.content
        if isinstance(content, list):
            content = "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("The LangChain chat model returned an empty completion")
        return content.strip()


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _value_at_path(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _expected_repository(context: dict[str, Any]) -> dict[str, Any]:
    expected = {}
    for output_field, input_path in AGENT1_REQUIRED_REPOSITORY_FIELDS.items():
        value = _value_at_path(context, input_path)
        if output_field == "origin_url" and not value:
            value = _value_at_path(
                context, ("manifest", "repository", "configured_url")
            )
        if value is None or value == "":
            raise ValueError(
                f"Context is missing repository metadata required for {output_field}"
            )
        expected[output_field] = value
    return expected


def _validate_agent1_document(
    document: dict[str, Any],
    context: dict[str, Any],
) -> None:
    validate_lineage(document)
    expected_repository = _expected_repository(context)
    actual_repository = document.get("repository")
    if not isinstance(actual_repository, dict):
        raise ValueError("repository must be an object")
    for field, expected_value in expected_repository.items():
        if actual_repository.get(field) != expected_value:
            raise ValueError(
                f"repository.{field} must equal the context value {expected_value!r}"
            )

    coverage = document.get("input_coverage", [])
    covered_sections = {
        row.get("section") for row in coverage if isinstance(row, dict)
    }
    expected_sections = set(context)
    if covered_sections != expected_sections:
        missing = sorted(expected_sections - covered_sections)
        extra = sorted(covered_sections - expected_sections)
        raise ValueError(
            f"input_coverage sections do not match context; missing={missing}, extra={extra}"
        )


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json|markdown|md)?\s*\n?(.*?)\n?```", stripped, re.DOTALL)
    return match.group(1).strip() if match else stripped


def _parse_json_completion(text: str) -> dict[str, Any]:
    try:
        document = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("model JSON output must have an object at its root")
    return document


def _ensure_request_size(
    system_prompt: str,
    user_prompt: str,
    max_request_characters: int,
) -> None:
    request_characters = len(system_prompt) + len(user_prompt)
    if request_characters > max_request_characters:
        raise ValueError(
            f"Model request contains {request_characters:,} characters, above the "
            f"configured limit of {max_request_characters:,}"
        )


def _array_skeleton(
    value: Any,
    path: tuple[str, ...],
) -> tuple[Any, list[tuple[tuple[str, ...], int, Any]]]:
    """Replace nested arrays with empty arrays and return their original items."""
    if isinstance(value, list):
        return [], [(path, position, item) for position, item in enumerate(value)]
    if isinstance(value, dict):
        skeleton = {}
        units: list[tuple[tuple[str, ...], int, Any]] = []
        for key, child in value.items():
            child_skeleton, child_units = _array_skeleton(child, path + (key,))
            skeleton[key] = child_skeleton
            units.extend(child_units)
        return skeleton, units
    return value, []


def _normalized_file_key(item: Any, context: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    candidate = next(
        (
            item.get(key)
            for key in ("file_path", "source_file_path", "target_file_path")
            if item.get(key)
        ),
        "",
    )
    if not isinstance(candidate, str):
        return ""
    normalized = candidate.replace("\\", "/")
    root_path = _value_at_path(context, ("manifest", "repository", "root_path"))
    if isinstance(root_path, str):
        normalized_root = root_path.replace("\\", "/").rstrip("/")
        if normalized.startswith(f"{normalized_root}/"):
            normalized = normalized[len(normalized_root) + 1 :]
    return normalized


def _append_array_item(
    document: dict[str, Any],
    path: tuple[str, ...],
    item: Any,
) -> None:
    current: Any = document
    for key in path[:-1]:
        current = current[key]
    current[path[-1]].append(copy.deepcopy(item))


def _pop_array_item(document: dict[str, Any], path: tuple[str, ...]) -> None:
    current: Any = document
    for key in path[:-1]:
        current = current[key]
    current[path[-1]].pop()


def _partition_context(
    context: dict[str, Any],
    max_json_characters: int,
) -> list[dict[str, Any]]:
    """Partition oversized context arrays into source-file-oriented JSON batches."""
    if len(_compact_json(context)) <= max_json_characters:
        return [context]

    base: dict[str, Any] = {}
    units: list[tuple[tuple[str, ...], int, Any]] = []
    for key, value in context.items():
        if key in {"manifest", "graph_summary", "architecture"}:
            base[key] = copy.deepcopy(value)
            continue
        skeleton, child_units = _array_skeleton(value, (key,))
        base[key] = skeleton
        units.extend(child_units)

    if len(_compact_json(base)) > max_json_characters:
        raise ValueError(
            "The non-partitionable context metadata exceeds the model request limit"
        )
    if not units:
        raise ValueError(
            "The context exceeds the model request limit but contains no arrays that can be batched"
        )

    units.sort(
        key=lambda unit: (
            _normalized_file_key(unit[2], context),
            ".".join(unit[0]),
            unit[1],
        )
    )

    batches: list[dict[str, Any]] = []
    current = copy.deepcopy(base)
    current_has_units = False
    for path, _position, item in units:
        _append_array_item(current, path, item)
        if len(_compact_json(current)) <= max_json_characters:
            current_has_units = True
            continue

        _pop_array_item(current, path)
        if current_has_units:
            batches.append(current)
        current = copy.deepcopy(base)
        _append_array_item(current, path, item)
        if len(_compact_json(current)) > max_json_characters:
            raise ValueError(
                f"One context record at {'.'.join(path)} is too large for the model request limit"
            )
        current_has_units = True

    if current_has_units:
        batches.append(current)
    return batches


def _build_agent1_user_prompt(
    *,
    repository: str,
    context: dict[str, Any],
    batch_number: int,
    batch_count: int,
) -> str:
    batching = ""
    if batch_count > 1:
        batching = f"""
This is evidence batch {batch_number} of {batch_count} from one oversized context.
Analyze only the exact records supplied in this batch and produce a canonical
intermediate Agent 1 JSON document. Do not infer that evidence absent from this
batch is absent from the repository. A later Agent 1 consolidation pass will
deduplicate and combine every validated batch result.
""".strip()
    else:
        batching = (
            "This is the complete context. Produce the final canonical Agent 1 JSON document."
        )

    return f"""Repository name: {repository}

The following JSON is the Agent 1 context supplied by LangGraph state.
{batching}

<context_json>
{_compact_json(context)}
</context_json>
"""


def _build_agent1_consolidation_prompt(
    repository: str,
    context: dict[str, Any],
    documents: list[dict[str, Any]],
) -> str:
    return f"""Complete the Agent 1 task for repository {repository} by consolidating
the validated intermediate JSON documents below. They were produced from
different batches of one authoritative context. Return one canonical Agent 1
JSON object and nothing else.

Deduplicate semantic facts, reconcile batch-local IDs and references, retain all
supported evidence, and remove issues caused only by evidence being split across
batches. Do not add a fact absent from the intermediate documents. Copy the
authoritative repository metadata exactly and include input_coverage for every
original top-level context section.

Authoritative repository metadata:
{_compact_json(_expected_repository(context))}
Original context sections:
{_compact_json(list(context))}

<intermediate_documents>
{_compact_json(documents)}
</intermediate_documents>
"""


def _repair_json_prompt(
    *,
    repository: str,
    context: dict[str, Any],
    previous_output: str,
    validation_error: Exception,
) -> str:
    return f"""Correct the previous Agent 1 output for repository {repository}.
Return the complete corrected canonical JSON object and nothing else. Do not add
new lineage facts; correct only schema, references, identity, coverage,
deduplication, and validation defects.

Authoritative repository metadata:
{_compact_json(_expected_repository(context))}
Required input_coverage sections:
{_compact_json(list(context))}
Validation error:
{validation_error}

<previous_output>
{previous_output}
</previous_output>
"""


def _generate_agent1_json(
    *,
    model: LineageModel,
    system_prompt: str,
    user_prompt: str,
    repository: str,
    validation_context: dict[str, Any],
    max_request_characters: int,
    validation_retries: int,
) -> dict[str, Any]:
    current_prompt = user_prompt
    last_error: Exception | None = None
    for attempt in range(validation_retries + 1):
        _ensure_request_size(system_prompt, current_prompt, max_request_characters)
        raw_output = model.complete(
            system_prompt=system_prompt,
            user_prompt=current_prompt,
            json_output=True,
        )
        try:
            document = _parse_json_completion(raw_output)
            _validate_agent1_document(document, validation_context)
            return document
        except (KeyError, TypeError, ValueError) as exc:
            last_error = exc
            if attempt >= validation_retries:
                break
            current_prompt = _repair_json_prompt(
                repository=repository,
                context=validation_context,
                previous_output=raw_output,
                validation_error=exc,
            )

    raise RuntimeError(
        f"Agent 1 output for {repository} failed deterministic validation: {last_error}"
    )


def _split_markdown_row(line: str) -> tuple[str, ...]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise ValueError(f"Invalid Markdown table row: {line}")
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in stripped[1:-1]:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            current.append(character)
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    cells.append("".join(current).strip())
    return tuple(cells)


def _read_markdown_table(
    report: str,
    heading: str,
) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    lines = report.splitlines()
    try:
        heading_index = lines.index(heading)
    except ValueError as exc:
        raise ValueError(f"Missing required heading: {heading}") from exc

    position = heading_index + 1
    while position < len(lines) and not lines[position].strip():
        position += 1
    if position + 1 >= len(lines):
        raise ValueError(f"Missing Markdown table after {heading}")
    headers = _split_markdown_row(lines[position])
    separator = _split_markdown_row(lines[position + 1])
    if len(separator) != len(headers) or any(
        not re.fullmatch(r":?-{3,}:?", cell) for cell in separator
    ):
        raise ValueError(f"Invalid Markdown table separator after {heading}")

    rows = []
    position += 2
    while position < len(lines) and lines[position].strip().startswith("|"):
        row = _split_markdown_row(lines[position])
        if len(row) != len(headers):
            raise ValueError(f"Table row after {heading} has the wrong column count")
        rows.append(row)
        position += 1
    return headers, rows


def validate_cross_repository_report(
    report: str,
    repositories: list[str],
) -> None:
    """Validate the deterministic structure and cross-table references in Agent 2 output."""
    report = _strip_code_fence(report)
    required_headings = (
        "# Cross-Repository Data Lineage",
        "## Application-to-Application Lineage",
        "## Detailed Data Flow",
        "## Application Flow Diagram",
    )
    positions = []
    for heading in required_headings:
        if report.count(heading) != 1:
            raise ValueError(f"Report must contain {heading!r} exactly once")
        positions.append(report.index(heading))
    if positions != sorted(positions):
        raise ValueError("Report sections are not in the required order")
    if report.lstrip().splitlines()[0] != required_headings[0]:
        raise ValueError("The report must begin with the required title")

    analyzed_match = re.search(r"^Repositories analyzed:\s*(.+)$", report, re.MULTILINE)
    inputs_match = re.search(r"^Repository inputs:\s*(\d+)\s*$", report, re.MULTILINE)
    connections_match = re.search(
        r"^Cross-repository connections:\s*(\d+)\s*$", report, re.MULTILINE
    )
    if not analyzed_match or not inputs_match or not connections_match:
        raise ValueError("The title section is missing required coverage values")
    analyzed = [item.strip() for item in analyzed_match.group(1).split(",")]
    if analyzed != repositories:
        raise ValueError(
            f"Repositories analyzed must be exactly: {', '.join(repositories)}"
        )
    if int(inputs_match.group(1)) != len(repositories):
        raise ValueError("Repository inputs count does not match selected inputs")

    high_headers, high_rows = _read_markdown_table(
        report, "## Application-to-Application Lineage"
    )
    detail_headers, detail_rows = _read_markdown_table(report, "## Detailed Data Flow")
    if high_headers != HIGH_LEVEL_HEADERS:
        raise ValueError("Application-to-Application Lineage has incorrect headers")
    if detail_headers != DETAIL_HEADERS:
        raise ValueError("Detailed Data Flow has incorrect headers")
    if int(connections_match.group(1)) != len(high_rows):
        raise ValueError("Cross-repository connections count does not match Table 1")

    expected_high_ids = [f"HL-{position:03d}" for position in range(1, len(high_rows) + 1)]
    high_ids = [row[0] for row in high_rows]
    if high_ids != expected_high_ids:
        raise ValueError("Table 1 Flow IDs must be sequential HL-001 identifiers")
    high_by_id = {row[0]: row for row in high_rows}
    high_keys = set()
    confidence_rank = {"inferred": 0, "partial": 1, "confirmed": 2}
    for row in high_rows:
        if row[1] not in repositories or row[2] not in repositories or row[1] == row[2]:
            raise ValueError(f"{row[0]} does not connect two selected repositories")
        if row[7] not in confidence_rank:
            raise ValueError(f"{row[0]} has invalid confidence {row[7]!r}")
        if row[7] != "confirmed" and row[8] in {"", "—", "-"}:
            raise ValueError(f"{row[0]} must describe an issue for {row[7]} confidence")
        key = (row[1], row[2], row[3], row[5], row[4])
        if key in high_keys:
            raise ValueError(f"Duplicate Table 1 connection key: {key}")
        high_keys.add(key)

    expected_detail_ids = [f"DF-{position:03d}" for position in range(1, len(detail_rows) + 1)]
    if [row[0] for row in detail_rows] != expected_detail_ids:
        raise ValueError("Table 2 Detail IDs must be sequential DF-001 identifiers")
    detail_keys = set()
    detail_confidence: dict[str, list[int]] = {}
    for row in detail_rows:
        high_row = high_by_id.get(row[1])
        if high_row is None:
            raise ValueError(f"{row[0]} references unknown Flow ID {row[1]}")
        if row[2] != high_row[1] or row[10] != high_row[2]:
            raise ValueError(f"{row[0]} application direction disagrees with {row[1]}")
        if row[15] not in confidence_rank:
            raise ValueError(f"{row[0]} has invalid confidence {row[15]!r}")
        if row[15] != "confirmed" and row[17] in {"", "—", "-"}:
            raise ValueError(f"{row[0]} must describe an issue for {row[15]} confidence")
        key = (row[1], row[4], row[12], row[9])
        if key in detail_keys:
            raise ValueError(f"Duplicate Table 2 mapping key: {key}")
        detail_keys.add(key)
        detail_confidence.setdefault(row[1], []).append(confidence_rank[row[15]])

    for flow_id, ranks in detail_confidence.items():
        high_rank = confidence_rank[high_by_id[flow_id][7]]
        if high_rank > min(ranks):
            raise ValueError(f"{flow_id} confidence exceeds its weakest detailed row")

    diagram_section = report[positions[3] :]
    diagram_match = re.search(r"```mermaid\s*\n(.*?)```", diagram_section, re.DOTALL)
    if not diagram_match:
        raise ValueError("Application Flow Diagram must contain a Mermaid block")
    diagram_lines = [line.strip() for line in diagram_match.group(1).splitlines() if line.strip()]
    if not diagram_lines or diagram_lines[0] != "flowchart LR":
        raise ValueError("Mermaid diagram must begin with flowchart LR")
    edge_lines = [line for line in diagram_lines[1:] if "-->" in line]
    diagram_flow_ids = []
    for line in edge_lines:
        identifiers = re.findall(r"HL-\d{3}", line)
        if len(identifiers) != 1:
            raise ValueError("Each Mermaid edge must contain exactly one Table 1 Flow ID")
        diagram_flow_ids.append(identifiers[0])
    if sorted(diagram_flow_ids) != sorted(high_ids) or len(edge_lines) != len(high_rows):
        raise ValueError("Mermaid edges do not match the final Table 1 connections")


def _build_agent2_user_prompt(
    repositories: list[str],
    agent1_outputs: dict[str, dict[str, Any]],
) -> str:
    inputs = [
        {
            "repository": repository,
            "lineage": agent1_outputs[repository],
        }
        for repository in repositories
    ]
    return f"""The following Agent 1 outputs are supplied by LangGraph state.
Use each repository lineage document exactly once.

Selected repositories, in required report order:
{_compact_json(repositories)}

<repository_lineage_inputs>
{_compact_json(inputs)}
</repository_lineage_inputs>

Return only the required final Markdown report.
"""


def _repair_markdown_prompt(
    repositories: list[str],
    previous_output: str,
    validation_error: Exception,
) -> str:
    return f"""Correct the previous Agent 2 report without adding new lineage facts.
Return the complete corrected Markdown report and nothing else.

Repositories analyzed, in required order:
{_compact_json(repositories)}
Validation error:
{validation_error}

<previous_output>
{previous_output}
</previous_output>
"""


def _generate_agent2_report(
    *,
    model: LineageModel,
    system_prompt: str,
    user_prompt: str,
    repositories: list[str],
    max_request_characters: int,
    validation_retries: int,
) -> str:
    current_prompt = user_prompt
    last_error: Exception | None = None
    for attempt in range(validation_retries + 1):
        _ensure_request_size(system_prompt, current_prompt, max_request_characters)
        raw_output = model.complete(
            system_prompt=system_prompt,
            user_prompt=current_prompt,
            json_output=False,
        )
        report = _strip_code_fence(raw_output)
        try:
            validate_cross_repository_report(report, repositories)
            return report.rstrip() + "\n"
        except ValueError as exc:
            last_error = exc
            if attempt >= validation_retries:
                break
            current_prompt = _repair_markdown_prompt(
                repositories, raw_output, exc
            )
    raise RuntimeError(f"Agent 2 output failed deterministic validation: {last_error}")


class LineagePipeline:
    """Node implementations and graph construction for the two-agent pipeline."""

    def __init__(
        self,
        config: PipelineConfig,
        agent1_model: LineageModel,
        agent2_model: LineageModel,
    ) -> None:
        self.config = config
        self.agent1_model = agent1_model
        self.agent2_model = agent2_model

    def load_inputs(self, _state: PipelineState) -> PipelineState:
        for prompt_path in (
            self.config.agent1_prompt_path,
            self.config.agent2_prompt_path,
        ):
            if not prompt_path.is_file():
                raise FileNotFoundError(f"Agent prompt not found: {prompt_path}")

        context_root = self.config.context_root.resolve()
        if not context_root.is_dir():
            raise FileNotFoundError(f"Context root not found: {context_root}")
        if self.config.all_repositories:
            repositories = sorted(
                path.parent.name for path in context_root.glob("*/context.json")
            )
        else:
            repositories = list(self.config.repositories)
        if len(repositories) < 2:
            raise ValueError("Select at least two repositories for Agent 2")
        if len(repositories) != len(set(repositories)):
            raise ValueError("Repository selections must be unique")

        contexts: dict[str, dict[str, Any]] = {}
        for repository in repositories:
            if repository != Path(repository).name or repository in {".", ".."}:
                raise ValueError(f"Invalid repository name: {repository!r}")
            context_path = context_root / repository / "context.json"
            if not context_path.is_file():
                raise FileNotFoundError(f"Context file not found: {context_path}")
            try:
                context = json.loads(context_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid context JSON in {context_path}: {exc}") from exc
            if not isinstance(context, dict):
                raise ValueError(f"Context root must be an object: {context_path}")
            expected_name = _value_at_path(context, ("manifest", "repository", "name"))
            if expected_name != repository:
                raise ValueError(
                    f"Context repository name {expected_name!r} does not match directory {repository!r}"
                )
            contexts[repository] = context

        return {
            "repositories": repositories,
            "contexts": contexts,
            "agent1_prompt": self.config.agent1_prompt_path.read_text(encoding="utf-8"),
            "agent2_prompt": self.config.agent2_prompt_path.read_text(encoding="utf-8"),
        }

    def _consolidate_agent1_documents(
        self,
        *,
        repository: str,
        context: dict[str, Any],
        documents: list[dict[str, Any]],
        system_prompt: str,
    ) -> dict[str, Any]:
        current = documents
        while len(current) > 1:
            next_level: list[dict[str, Any]] = []
            for position in range(0, len(current), 2):
                group = current[position : position + 2]
                if len(group) == 1:
                    next_level.append(group[0])
                    continue
                user_prompt = _build_agent1_consolidation_prompt(
                    repository, context, group
                )
                next_level.append(
                    _generate_agent1_json(
                        model=self.agent1_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        repository=repository,
                        validation_context=context,
                        max_request_characters=self.config.max_request_characters,
                        validation_retries=self.config.validation_retries,
                    )
                )
            current = next_level
        return current[0]

    def run_agent1(self, state: PipelineState) -> PipelineState:
        system_prompt = state["agent1_prompt"]
        prompt_overhead = len(system_prompt) + 8_000
        batch_json_limit = self.config.max_request_characters - prompt_overhead
        if batch_json_limit <= 0:
            raise ValueError("Agent 1 prompt is larger than the configured request limit")

        outputs: dict[str, dict[str, Any]] = {}
        for repository in state["repositories"]:
            context = state["contexts"][repository]
            batches = _partition_context(context, batch_json_limit)
            print(f"Agent 1: {repository} ({len(batches)} context batch(es))")
            partial_documents = []
            for position, batch in enumerate(batches, start=1):
                user_prompt = _build_agent1_user_prompt(
                    repository=repository,
                    context=batch,
                    batch_number=position,
                    batch_count=len(batches),
                )
                partial_documents.append(
                    _generate_agent1_json(
                        model=self.agent1_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        repository=repository,
                        validation_context=batch,
                        max_request_characters=self.config.max_request_characters,
                        validation_retries=self.config.validation_retries,
                    )
                )
            outputs[repository] = self._consolidate_agent1_documents(
                repository=repository,
                context=context,
                documents=partial_documents,
                system_prompt=system_prompt,
            )
        return {"agent1_outputs": outputs}

    def validate_agent1(self, state: PipelineState) -> PipelineState:
        for repository in state["repositories"]:
            _validate_agent1_document(
                state["agent1_outputs"][repository], state["contexts"][repository]
            )
        return {}

    def run_agent2(self, state: PipelineState) -> PipelineState:
        print(f"Agent 2: comparing {len(state['repositories'])} repository outputs")
        user_prompt = _build_agent2_user_prompt(
            state["repositories"],
            state["agent1_outputs"],
        )
        report = _generate_agent2_report(
            model=self.agent2_model,
            system_prompt=state["agent2_prompt"],
            user_prompt=user_prompt,
            repositories=state["repositories"],
            max_request_characters=self.config.max_request_characters,
            validation_retries=self.config.validation_retries,
        )
        return {"final_report": report}

    def validate_agent2(self, state: PipelineState) -> PipelineState:
        validate_cross_repository_report(
            state["final_report"], state["repositories"]
        )
        return {}

    def write_outputs(self, state: PipelineState) -> PipelineState:
        output_root = self.config.output_root
        output_root.mkdir(parents=True, exist_ok=True)
        written_files: list[str] = []
        with tempfile.TemporaryDirectory(
            dir=output_root, prefix=".lineage-agent-stage-"
        ) as temporary_directory:
            staging_root = Path(temporary_directory)
            staged_files: list[tuple[Path, Path]] = []
            for repository in state["repositories"]:
                relative_path = Path(repository) / "repo-lineage.json"
                staged_path = staging_root / relative_path
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.write_text(
                    json.dumps(
                        state["agent1_outputs"][repository],
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                staged_files.append((staged_path, output_root / relative_path))

            report_path = staging_root / "cross-boundary-lineage.md"
            report_path.write_text(state["final_report"], encoding="utf-8")
            staged_files.append(
                (report_path, output_root / "cross-boundary-lineage.md")
            )

            for staged_path, destination in staged_files:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_path, destination)
                written_files.append(str(destination))
        return {"written_files": written_files}

    def build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph is not installed; run python3 -m pip install -r requirements.txt"
            ) from exc

        graph = StateGraph(PipelineState)
        graph.add_node("load_inputs", self.load_inputs)
        graph.add_node("agent1_per_repository", self.run_agent1)
        graph.add_node("validate_agent1", self.validate_agent1)
        graph.add_node("agent2_cross_repository", self.run_agent2)
        graph.add_node("validate_agent2", self.validate_agent2)
        graph.add_node("write_outputs", self.write_outputs)
        graph.add_edge(START, "load_inputs")
        graph.add_edge("load_inputs", "agent1_per_repository")
        graph.add_edge("agent1_per_repository", "validate_agent1")
        graph.add_edge("validate_agent1", "agent2_cross_repository")
        graph.add_edge("agent2_cross_repository", "validate_agent2")
        graph.add_edge("validate_agent2", "write_outputs")
        graph.add_edge("write_outputs", END)
        return graph.compile()

    def run(self) -> PipelineState:
        return self.build_graph().invoke({})


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Agent 1 and Agent 2 as a validated LangGraph pipeline using Gemini."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--repo",
        action="append",
        dest="repositories",
        metavar="NAME",
        help="Exact repository context to include; repeat for each repository.",
    )
    selection.add_argument(
        "--all-repositories",
        action="store_true",
        help="Explicitly include every immediate */context.json under the context root.",
    )
    parser.add_argument("--context-root", type=Path, default=DEFAULT_CONTEXT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--agent1-prompt", type=Path, default=DEFAULT_AGENT1_PROMPT)
    parser.add_argument("--agent2-prompt", type=Path, default=DEFAULT_AGENT2_PROMPT)
    parser.add_argument(
        "--agent1-model", default=os.getenv("AGENT1_MODEL", AGENT1_MODEL)
    )
    parser.add_argument(
        "--agent1-thinking-budget",
        type=int,
        default=os.getenv("AGENT1_THINKING_BUDGET", AGENT1_THINKING_BUDGET),
        help="Gemini 2.5 thinking-token budget for Agent 1 (1024 is low reasoning).",
    )
    parser.add_argument(
        "--agent2-model", default=os.getenv("AGENT2_MODEL", AGENT2_MODEL)
    )
    parser.add_argument(
        "--agent2-thinking-budget",
        type=int,
        default=os.getenv("AGENT2_THINKING_BUDGET", AGENT2_THINKING_BUDGET),
        help="Gemini 2.5 thinking-token budget for Agent 2 (8192 is medium reasoning).",
    )
    parser.add_argument(
        "--max-request-characters",
        type=int,
        default=DEFAULT_MAX_REQUEST_CHARACTERS,
        help="Conservative request-size guard used for semantic context batching.",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=DEFAULT_MAX_COMPLETION_TOKENS,
    )
    parser.add_argument("--validation-retries", type=int, default=1)
    parser.add_argument("--api-retries", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    args = parse_arguments(argv)
    try:
        if args.max_request_characters <= 0 or args.max_completion_tokens <= 0:
            raise ValueError("Model size limits must be positive")
        if args.agent1_thinking_budget < 0 or args.agent2_thinking_budget < 0:
            raise ValueError("Thinking-token budgets must not be negative")
        if args.validation_retries < 0 or args.api_retries < 0:
            raise ValueError("Retry counts must not be negative")

        config = PipelineConfig(
            context_root=args.context_root.resolve(),
            output_root=args.output_root.resolve(),
            agent1_prompt_path=args.agent1_prompt.resolve(),
            agent2_prompt_path=args.agent2_prompt.resolve(),
            repositories=tuple(args.repositories or ()),
            all_repositories=args.all_repositories,
            max_request_characters=args.max_request_characters,
            validation_retries=args.validation_retries,
        )
        agent1_model = LangChainLineageModel(
            api_key=os.getenv("GOOGLE_API_KEY", ""),
            model=args.agent1_model,
            thinking_budget=args.agent1_thinking_budget,
            max_completion_tokens=args.max_completion_tokens,
            max_retries=args.api_retries,
        )
        agent2_model = LangChainLineageModel(
            api_key=os.getenv("GOOGLE_API_KEY", ""),
            model=args.agent2_model,
            thinking_budget=args.agent2_thinking_budget,
            max_completion_tokens=args.max_completion_tokens,
            max_retries=args.api_retries,
        )
        final_state = LineagePipeline(config, agent1_model, agent2_model).run()
        print("Pipeline completed. Validated outputs:")
        for output_file in final_state["written_files"]:
            print(f"- {output_file}")
        return 0
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

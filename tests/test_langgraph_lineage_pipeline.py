import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.langgraph_lineage_pipeline import (
    LangChainLineageModel,
    LineagePipeline,
    PipelineConfig,
    _build_agent1_user_prompt,
    _build_agent2_user_prompt,
    _compact_json,
    _partition_context,
    parse_arguments,
    validate_cross_repository_report,
)


CONTEXT_SECTIONS = (
    "manifest",
    "graph_summary",
    "architecture",
    "symbols",
    "relationships",
    "artifacts",
    "interfaces",
    "source_evidence",
)


def make_context(repository: str) -> dict:
    return {
        "manifest": {
            "lineage_context_schema_version": "1.2",
            "exported_at": "2026-08-08T00:00:00+00:00",
            "repository": {
                "name": repository,
                "configured_url": f"https://example.test/{repository}.git",
                "origin_url": f"https://example.test/{repository}.git",
                "branch": "main",
                "commit_sha": f"{repository}-commit",
                "root_path": f"/tmp/{repository}",
            },
        },
        "graph_summary": {"project": repository},
        "architecture": {"languages": ["Python"]},
        "symbols": [],
        "relationships": [],
        "artifacts": [],
        "interfaces": {"nodes": [], "relationships": []},
        "source_evidence": {
            "discovery_mode": "graph_first",
            "selection": {"candidates": [], "snippet_targets": []},
            "snippets": [],
            "text_fallback": {"enabled": False},
            "redactions_applied": False,
        },
    }


def make_agent1_output(repository: str, invalid_identity: bool = False) -> dict:
    return {
        "schema_version": "repository-lineage/1.0",
        "repository": {
            "name": "wrong-name" if invalid_identity else repository,
            "origin_url": f"https://example.test/{repository}.git",
            "commit_sha": f"{repository}-commit",
            "branch": "main",
            "context_exported_at": "2026-08-08T00:00:00+00:00",
        },
        "input_coverage": [
            {
                "section": section,
                "records_considered": 0,
                "used_for": ["not_lineage_relevant"],
            }
            for section in CONTEXT_SECTIONS
        ],
        "components": [],
        "data_elements": [],
        "boundary_contracts": [],
        "lineage_flows": [],
        "end_to_end_paths": [],
        "issues": [],
        "evidence": [],
    }


def make_empty_report(repositories: list[str]) -> str:
    return f"""# Cross-Repository Data Lineage

Repositories analyzed: {', '.join(repositories)}
Repository inputs: {len(repositories)}
Cross-repository connections: 0

## Application-to-Application Lineage

| Flow ID | Source Application | Target Application | Mechanism | Operation | Shared Boundary | Data Summary | Confidence | Issues |
|---|---|---|---|---|---|---|---|---|

## Detailed Data Flow

| Detail ID | Flow ID | Source Application | Source Contract / Flow | Source Data Element(s) | Source Type | Source Raw / Normalized Locator | Mechanism | Operation | Transformation Chain | Target Application | Target Contract / Flow | Target Data Element | Target Type | Target Raw / Normalized Locator | Confidence | Evidence | Issues |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Application Flow Diagram

```mermaid
flowchart LR
```
"""


class FakeLineageModel:
    def __init__(self, repositories: list[str], invalid_identity: bool = False):
        self.repositories = repositories
        self.invalid_identity = invalid_identity
        self.calls = []
        self.agent2_prompt = ""

    def complete(self, *, system_prompt: str, user_prompt: str, json_output: bool) -> str:
        self.calls.append((system_prompt, user_prompt, json_output))
        if not json_output:
            self.agent2_prompt = user_prompt
            return make_empty_report(self.repositories)

        match = re.search(r"Repository name: ([^\n]+)", user_prompt)
        if not match:
            match = re.search(r"repository ([^\s]+) by consolidating", user_prompt)
        if not match:
            raise AssertionError("Fake model could not identify the repository")
        repository = match.group(1)
        return json.dumps(make_agent1_output(repository, self.invalid_identity))


class LangGraphLineagePipelineTests(unittest.TestCase):
    def test_langgraph_messages_do_not_pass_file_bindings_to_agents(self):
        context = make_context("alpha")
        agent1_message = _build_agent1_user_prompt(
            repository="alpha",
            context=context,
            batch_number=1,
            batch_count=1,
        )
        agent2_message = _build_agent2_user_prompt(
            ["alpha", "beta"],
            {
                "alpha": make_agent1_output("alpha"),
                "beta": make_agent1_output("beta"),
            },
        )

        self.assertNotIn("INPUT_CONTEXT_PATH", agent1_message)
        self.assertNotIn("OUTPUT_DIRECTORY", agent1_message)
        self.assertNotIn("INPUT_ROOT_DIRECTORY", agent2_message)
        self.assertNotIn("repo-lineage.json", agent2_message)

    def test_cli_defaults_agent_thinking_budgets_independently(self):
        with patch.dict(
            "os.environ",
            {
                "AGENT1_MODEL": "gemini-2.5-flash",
                "AGENT1_THINKING_BUDGET": "1024",
                "AGENT2_MODEL": "gemini-2.5-flash",
                "AGENT2_THINKING_BUDGET": "8192",
            },
        ):
            arguments = parse_arguments(["--all-repositories"])

        self.assertEqual(arguments.agent1_model, "gemini-2.5-flash")
        self.assertEqual(arguments.agent1_thinking_budget, 1_024)
        self.assertEqual(arguments.agent2_model, "gemini-2.5-flash")
        self.assertEqual(arguments.agent2_thinking_budget, 8_192)

    def test_agents_can_use_independent_models_and_thinking_budgets(self):
        agent1_model = LangChainLineageModel(
            api_key="test-key",
            model="gemini-2.5-flash",
            thinking_budget=1_024,
            max_completion_tokens=100,
        )
        agent2_model = LangChainLineageModel(
            api_key="test-key",
            model="gemini-2.5-flash",
            thinking_budget=8_192,
            max_completion_tokens=100,
        )

        self.assertEqual(agent1_model.chat_model.model, "gemini-2.5-flash")
        self.assertEqual(agent1_model.chat_model.thinking_budget, 1_024)
        self.assertEqual(agent2_model.chat_model.model, "gemini-2.5-flash")
        self.assertEqual(agent2_model.chat_model.thinking_budget, 8_192)

    def test_pipeline_uses_only_current_selected_agent1_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            context_root = root / "lineage_context"
            output_root = root / "lineage_output"
            prompt_root = root / "prompts"
            prompt_root.mkdir()
            (prompt_root / "agent1.md").write_text("Agent 1", encoding="utf-8")
            (prompt_root / "agent2.md").write_text("Agent 2", encoding="utf-8")

            repositories = ["alpha", "beta"]
            for repository in repositories:
                repository_root = context_root / repository
                repository_root.mkdir(parents=True)
                (repository_root / "context.json").write_text(
                    json.dumps(make_context(repository)), encoding="utf-8"
                )

            stale_root = output_root / "stale-repository"
            stale_root.mkdir(parents=True)
            (stale_root / "repo-lineage.json").write_text(
                json.dumps(make_agent1_output("stale-repository")), encoding="utf-8"
            )

            agent1_model = FakeLineageModel(repositories)
            agent2_model = FakeLineageModel(repositories)
            config = PipelineConfig(
                context_root=context_root,
                output_root=output_root,
                agent1_prompt_path=prompt_root / "agent1.md",
                agent2_prompt_path=prompt_root / "agent2.md",
                repositories=tuple(repositories),
                max_request_characters=100_000,
                validation_retries=0,
            )
            state = LineagePipeline(config, agent1_model, agent2_model).run()

            self.assertEqual(len(state["written_files"]), 3)
            self.assertTrue((output_root / "alpha" / "repo-lineage.json").is_file())
            self.assertTrue((output_root / "beta" / "repo-lineage.json").is_file())
            self.assertTrue((output_root / "cross-boundary-lineage.md").is_file())
            self.assertNotIn("stale-repository", agent2_model.agent2_prompt)
            self.assertTrue(all(call[2] for call in agent1_model.calls))
            self.assertTrue(all(not call[2] for call in agent2_model.calls))
            self.assertEqual(
                json.loads((output_root / "alpha" / "repo-lineage.json").read_text())["repository"]["name"],
                "alpha",
            )

    def test_invalid_agent1_identity_stops_before_writes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            context_root = root / "contexts"
            prompt_root = root / "prompts"
            prompt_root.mkdir()
            (prompt_root / "agent1.md").write_text("Agent 1", encoding="utf-8")
            (prompt_root / "agent2.md").write_text("Agent 2", encoding="utf-8")
            repositories = ["alpha", "beta"]
            for repository in repositories:
                repository_root = context_root / repository
                repository_root.mkdir(parents=True)
                (repository_root / "context.json").write_text(
                    json.dumps(make_context(repository)), encoding="utf-8"
                )
            output_root = root / "outputs"
            config = PipelineConfig(
                context_root=context_root,
                output_root=output_root,
                agent1_prompt_path=prompt_root / "agent1.md",
                agent2_prompt_path=prompt_root / "agent2.md",
                repositories=tuple(repositories),
                max_request_characters=100_000,
                validation_retries=0,
            )

            with self.assertRaises(RuntimeError):
                LineagePipeline(
                    config,
                    FakeLineageModel(repositories, invalid_identity=True),
                    FakeLineageModel(repositories),
                ).run()
            self.assertFalse(output_root.exists())

    def test_large_context_partition_preserves_every_array_record(self):
        context = make_context("alpha")
        context["symbols"] = [
            {
                "qualified_name": f"symbol-{position}",
                "file_path": f"src/file-{position % 3}.py",
                "payload": "x" * 180,
            }
            for position in range(15)
        ]
        context["source_evidence"]["snippets"] = [
            {
                "qualified_name": f"snippet-{position}",
                "file_path": f"/tmp/alpha/src/file-{position % 3}.py",
                "source": "y" * 180,
            }
            for position in range(9)
        ]

        batches = _partition_context(context, 1_350)

        self.assertGreater(len(batches), 1)
        self.assertTrue(all(len(_compact_json(batch)) <= 1_350 for batch in batches))
        symbols = [item for batch in batches for item in batch["symbols"]]
        snippets = [
            item
            for batch in batches
            for item in batch["source_evidence"]["snippets"]
        ]
        self.assertCountEqual(symbols, context["symbols"])
        self.assertCountEqual(snippets, context["source_evidence"]["snippets"])

    def test_report_validator_accepts_empty_cross_repository_result(self):
        repositories = ["alpha", "beta"]
        validate_cross_repository_report(make_empty_report(repositories), repositories)


if __name__ == "__main__":
    unittest.main()

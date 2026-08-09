#!/usr/bin/env python3
"""A small, beginner-friendly LangGraph example for Agent 1 and Agent 2."""

import json
import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI as ChatModel
from langgraph.graph import END, START, StateGraph


# ---------------------------------------------------------------------------
# Step 1: Define the default settings.
#
# Change these values directly while learning. No command-line arguments are
# needed. A few small repositories are used because this simple example does not
# include the large-context batching from the production pipeline.
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

REPOSITORIES = [
    "Chroma_db_reader",
    "crypto-kaka-rag",
    "json_reader_test",
]

CONTEXT_ROOT = PROJECT_ROOT / "lineage_context"
OUTPUT_ROOT = PROJECT_ROOT / "simple_lineage_output"

AGENT1_PROMPT_PATH = (
    PROJECT_ROOT / "prompts" / "agent1_repository_lineage_langgraph.agent.md"
)
AGENT2_PROMPT_PATH = (
    PROJECT_ROOT / "prompts" / "agent2_cross_repository_lineage_langgraph.agent.md"
)

# ---------------------------------------------------------------------------
# Step 2: Load GOOGLE_API_KEY and model settings from the local .env file.
# ---------------------------------------------------------------------------

load_dotenv(PROJECT_ROOT / ".env")

AGENT1_MODEL = os.getenv("AGENT1_MODEL", "gemini-2.5-flash").lower()
AGENT2_MODEL = os.getenv("AGENT2_MODEL", "gemini-2.5-flash").lower()

# Gemini 2.5 uses thinking-token budgets instead of reasoning_effort names.
AGENT1_THINKING_BUDGET = 1_024  # Low reasoning
AGENT2_THINKING_BUDGET = 8_192  # Medium reasoning


# ---------------------------------------------------------------------------
# Step 3: Create one LangChain model for each agent.
# ---------------------------------------------------------------------------

agent1_model = ChatModel(
    model=AGENT1_MODEL,
    thinking_budget=AGENT1_THINKING_BUDGET,
    temperature=0,
    max_tokens=32_768,
)

# Agent 1 must return JSON, so Gemini JSON mode is added to its model.
agent1_json_model = agent1_model.bind(
    response_mime_type="application/json"
)

agent2_model = ChatModel(
    model=AGENT2_MODEL,
    thinking_budget=AGENT2_THINKING_BUDGET,
    temperature=0,
    max_tokens=32_768,
)


# ---------------------------------------------------------------------------
# Step 4: Define the information passed between LangGraph nodes.
# ---------------------------------------------------------------------------

class LineageState(TypedDict, total=False):
    repository_outputs: dict[str, dict]
    final_report: str


# ---------------------------------------------------------------------------
# Step 5: Agent 1 reads each context and returns repository-lineage JSON.
# ---------------------------------------------------------------------------

def run_agent1(_state: LineageState) -> LineageState:
    agent1_prompt = AGENT1_PROMPT_PATH.read_text(encoding="utf-8")
    repository_outputs = {}

    for repository in REPOSITORIES:
        context_path = CONTEXT_ROOT / repository / "context.json"
        context = json.loads(context_path.read_text(encoding="utf-8"))

        task_message = f"""
Analyze the following context for repository {repository}.
Return only the canonical repo-lineage JSON required by the Agent 1 prompt.

Context:
{json.dumps(context)}
"""

        response = agent1_json_model.invoke(
            [
                ("system", agent1_prompt),
                ("human", task_message),
            ]
        )

        repository_outputs[repository] = json.loads(response.content)
        print(f"Agent 1 completed: {repository}")

    return {"repository_outputs": repository_outputs}


# ---------------------------------------------------------------------------
# Step 6: Agent 2 compares all Agent 1 outputs and returns Markdown.
# ---------------------------------------------------------------------------

def run_agent2(state: LineageState) -> LineageState:
    agent2_prompt = AGENT2_PROMPT_PATH.read_text(encoding="utf-8")

    task_message = f"""
Compare these Agent 1 repository-lineage outputs.
Return only the final cross-repository Markdown report required by Agent 2.

Repository outputs:
{json.dumps(state['repository_outputs'])}
"""

    response = agent2_model.invoke(
        [
            ("system", agent2_prompt),
            ("human", task_message),
        ]
    )

    print("Agent 2 completed")
    return {"final_report": response.content}


# ---------------------------------------------------------------------------
# Step 7: Save Agent 1 and Agent 2 outputs.
# ---------------------------------------------------------------------------

def save_outputs(state: LineageState) -> LineageState:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    for repository, output in state["repository_outputs"].items():
        repository_directory = OUTPUT_ROOT / repository
        repository_directory.mkdir(parents=True, exist_ok=True)

        output_path = repository_directory / "repo-lineage.json"
        output_path.write_text(
            json.dumps(output, indent=2) + "\n",
            encoding="utf-8",
        )

    report_path = OUTPUT_ROOT / "cross-boundary-lineage.md"
    report_path.write_text(state["final_report"], encoding="utf-8")

    print(f"Outputs saved under: {OUTPUT_ROOT}")
    return {}


# ---------------------------------------------------------------------------
# Step 8: Connect the Python functions using LangGraph.
#
# START -> Agent 1 -> Agent 2 -> Save outputs -> END
# ---------------------------------------------------------------------------

graph_builder = StateGraph(LineageState)

graph_builder.add_node("agent1", run_agent1)
graph_builder.add_node("agent2", run_agent2)
graph_builder.add_node("save", save_outputs)

graph_builder.add_edge(START, "agent1")
graph_builder.add_edge("agent1", "agent2")
graph_builder.add_edge("agent2", "save")
graph_builder.add_edge("save", END)

lineage_graph = graph_builder.compile()


if __name__ == "__main__":
    lineage_graph.invoke({})

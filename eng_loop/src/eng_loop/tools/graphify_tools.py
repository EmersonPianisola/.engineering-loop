from __future__ import annotations

import logging
import subprocess
from typing import Any

from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


def _run_graphify_cmd(args: list[str], cwd: str) -> str:
    """Execute a graphify CLI command and return stdout."""
    try:
        result = subprocess.run(
            ["graphify"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return f"graphify error: {result.stderr.strip()}"
        return result.stdout.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "graphify command timed out"
    except FileNotFoundError:
        return "graphify CLI not found. Install: uv tool install graphifyy"


def create_graphify_explain_tool(project_root: str) -> Tool:
    """Tool: graphify explain <entity> — understand a concept's structure and connections."""
    return Tool(
        name="graphify_explain",
        description=(
            "Explain a code entity and its connections. "
            "Use this BEFORE reading files to understand structure, location, and impact scope. "
            "Example: graphify_explain('AuthMiddleware'), graphify_explain('Firebase setup')"
        ),
        func=lambda entity: _run_graphify_cmd(["explain", entity], cwd=project_root),
    )


def create_graphify_path_tool(project_root: str) -> Tool:
    """Tool: graphify path <source> <destination> — trace connections between two entities."""
    return Tool(
        name="graphify_path",
        description=(
            "Find the shortest path between two code entities. "
            "Use for tracing data flow, dependency chains, and connection mapping. "
            "Example: graphify_path('login', 'database'), graphify_path('API route', 'Firebase')"
        ),
        func=lambda pair: _run_graphify_cmd(["path"] + pair.split(","), cwd=project_root),
    )


def create_graphify_query_tool(project_root: str) -> Tool:
    """Tool: graphify query <question> — get scoped subgraph for architecture questions."""
    return Tool(
        name="graphify_query",
        description=(
            "Query the knowledge graph for architecture context. "
            "Returns a scoped subgraph relevant to the question. "
            "Use for high-level understanding before diving into files. "
            "Example: graphify_query('how is Firebase configured'), graphify_query('E2E test infrastructure')"
        ),
        func=lambda question: _run_graphify_cmd(["query", question], cwd=project_root),
    )


def get_graphify_tools(
    state: dict[str, Any],
    paths: dict[str, str],
) -> list[Tool]:
    """Return graphify tools if the knowledge graph was built."""
    graphify_state = state.get("graphify", {})
    if not graphify_state.get("built", False):
        return []

    project_root = paths.get("project_root", ".")
    return [
        create_graphify_explain_tool(project_root),
        create_graphify_path_tool(project_root),
        create_graphify_query_tool(project_root),
    ]

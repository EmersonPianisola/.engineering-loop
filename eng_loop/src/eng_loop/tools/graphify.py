from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from eng_loop.state import get_work_item_text

logger = logging.getLogger(__name__)


def is_graphify_enabled(config: dict[str, Any]) -> bool:
    """Check if graphify is enabled in config."""
    return config.get("graphify", {}).get("enabled", False)


def should_skip_graphify(config: dict[str, Any], complexity: str, project_root: str) -> tuple[bool, str]:
    """Determine if graphify should be skipped. Returns (skip, reason)."""
    graphify_config = config.get("graphify", {})

    if graphify_config.get("skip_if_small", True) and complexity == "small":
        return True, "complexity small"

    project = Path(project_root)
    code_files = (
        list(project.glob("**/*.js"))
        + list(project.glob("**/*.ts"))
        + list(project.glob("**/*.jsx"))
        + list(project.glob("**/*.tsx"))
        + list(project.glob("**/*.py"))
    )
    if not code_files:
        return True, "no codebase"

    return False, ""


def check_graphify_cli() -> tuple[bool, str]:
    """Check if graphify CLI is installed. Returns (available, version)."""
    try:
        result = subprocess.run(
            ["graphify", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def build_graph(project_root: str, incremental: bool = False) -> tuple[bool, dict[str, Any]]:
    """Build or update the graphify knowledge graph. Returns (success, stats)."""
    project = Path(project_root)
    graph_file = project / "graphify-out" / "graph.json"

    # graphify update <path> works for both initial build and incremental update
    command = ["graphify", "update", "."]

    try:
        result = subprocess.run(
            command,
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error("graphify build failed: %s", result.stderr)
            return False, {"error": result.stderr}

        # Parse stats from output or graph file
        stats = _parse_graph_stats(graph_file)
        return True, stats

    except subprocess.TimeoutExpired:
        logger.error("graphify build timed out")
        return False, {"error": "timeout"}
    except Exception as e:
        logger.error("graphify build error: %s", e)
        return False, {"error": str(e)}


def _parse_graph_stats(graph_file: Path) -> dict[str, Any]:
    """Parse graph statistics from graph.json."""
    if not graph_file.exists():
        return {"nodes": 0, "edges": 0, "communities": 0}

    try:
        with open(graph_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        nodes = len(data.get("nodes", []))
        edges = len(data.get("edges", []))
        communities = len({n.get("community", "") for n in data.get("nodes", [])})

        return {
            "nodes": nodes,
            "edges": edges,
            "communities": communities,
        }
    except Exception as e:
        logger.warning("Failed to parse graph stats: %s", e)
        return {"nodes": 0, "edges": 0, "communities": 0}


def get_graphify_prompt_injection(graph_path: str, tools_available: bool = True) -> str:
    """Generate prompt instructions for stages to use graphify queries.

    Args:
        graph_path: Path to the project root containing graphify-out/
        tools_available: Whether graphify tools (graphify_query, etc.) are available.
            If False, only provides guidance for pre-computed context.
    """
    if tools_available:
        return f"""## KNOWLEDGE GRAPH AVAILABLE

A knowledge graph of the codebase is available at `{graph_path}/graphify-out/`.

**MANDATORY: Query the graph BEFORE reading files you don't already know.**

Before calling `read`, `glob`, or `grep` on any entity you don't already know:
1. Use `graphify_query` to get architectural context for your task
2. Use `graphify_explain` to understand specific entities' structure and connections
3. Only then read the specific files you need

**Tools:**
- **graphify_query** — Get architecture context for a question. Use this FIRST.
- **graphify_explain** — Understand a specific entity's structure and connections.
- **graphify_path** — Trace connections between two entities.

**Confidence rules:**
- EXTRACTED edges: Trust — explicit in source
- INFERRED edges: Verify if critical — derived by resolution
- AMBIGUOUS edges: Must Read source — do not trust

**DO NOT** start with 10+ file reads. Use graphify to find what to read.
If you have made 3+ consecutive reads without writing anything, STOP and use graphify."""
    else:
        return """## KNOWLEDGE GRAPH AVAILABLE

A knowledge graph of the codebase is available. Pre-computed context is provided above.

**Use the GRAPH CONTEXT section above** to understand the codebase structure before reading files.
Focus your reads on files directly relevant to your current task.
**DO NOT** start with 10+ file reads — use the pre-computed context to guide your exploration."""


def get_graphify_injection(
    state: dict[str, Any],
    paths: dict[str, str],
    tools_available: bool = True,
) -> str:
    """Get graphify prompt injection if graph was built. Returns empty string if not available.

    Args:
        state: Pipeline state
        paths: Filesystem paths
        tools_available: Whether graphify tools (graphify_query, etc.) are available to the agent.
            Set to False for backends that don't support graphify tools (e.g., opencode).
    """
    graphify_state = state.get("graphify", {})
    if not graphify_state.get("built", False):
        return ""

    project_root = paths.get("project_root", ".")
    return get_graphify_prompt_injection(project_root, tools_available)


def _run_graphify_cmd(args: list[str], cwd: str) -> str:
    """Execute a graphify CLI command and return stdout."""
    try:
        result = subprocess.run(
            ["graphify"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return f"graphify error: {result.stderr.strip()}"
        return result.stdout.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "graphify command timed out"
    except FileNotFoundError:
        return "graphify CLI not found"


def _extract_entities_from_text(text: str, max_entities: int = 5) -> list[str]:
    """Extract potential code entities from text (file paths, module names, function-like identifiers)."""
    import re

    entities = []

    # File paths
    paths = re.findall(r"[\w]+[\w\.\-]+(?:/[\w]+[\w\.\-]+)*\.(?:ts|tsx|js|jsx|py|css|json|md|yaml|yml)", text)
    entities.extend(paths[:max_entities])

    # CamelCase class/function names
    classes = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text)
    entities.extend(classes[:max_entities])

    # snake_case function/module names
    snake = re.findall(r"\b[a-z][a-z0-9_]{3,}\b", text)
    entities.extend(snake[:max_entities])

    # Module/directory paths (no extension)
    modules = re.findall(r"\b[\w]+(?:/[\w]+)+\b", text)
    entities.extend(modules[:max_entities])

    # Deduplicate, preserve order
    seen = set()
    unique = []
    for e in entities:
        if e not in seen and len(e) > 2:
            seen.add(e)
            unique.append(e)
        if len(unique) >= max_entities:
            break
    return unique


def precompute_graph_context(
    state: dict[str, Any],
    paths: dict[str, str],
    config: dict[str, Any],
    max_entities: int = 5,
) -> str:
    """Pre-compute graph context from work item and blueprint entities.

    Runs graphify_query on the work item and graphify_explain on key entities
    extracted from the work item and blueprint. Returns formatted markdown
    to inject into the agent prompt.

    Returns empty string if graph is not built or no context could be retrieved.
    """
    graphify_state = state.get("graphify", {})
    if not graphify_state.get("built", False):
        return ""

    project_root = paths.get("project_root", ".")
    work_item = get_work_item_text(state)
    blueprint = state.get("stage_artifacts", {}).get("impl.design", "")

    # Combine text sources for entity extraction
    combined_text = f"{work_item}\n{blueprint}"
    if not combined_text.strip():
        return ""

    # Verify graphify CLI is available before attempting queries
    _cli_available, _ = check_graphify_cli()
    if not _cli_available:
        return ""

    parts = []

    # Query on work item — broad architectural context
    if work_item.strip():
        query_result = _run_graphify_cmd(["query", work_item[:500]], project_root)
        if query_result and not _is_graphify_error(query_result):
            parts.append(f"### Task Context\n{query_result}")

    # Explain key entities
    entities = _extract_entities_from_text(combined_text, max_entities)
    if entities:
        explain_results = []
        for entity in entities:
            result = _run_graphify_cmd(["explain", entity], project_root)
            if result and not _is_graphify_error(result):
                explain_results.append(f"#### {entity}\n{result}")
                if len(explain_results) >= max(3, max_entities // 2):
                    break

        if explain_results:
            parts.append("### Key Entities\n" + "\n\n".join(explain_results))

    if parts:
        return "## GRAPH CONTEXT (pre-computed)\n" + "\n\n".join(parts)

    return ""


def _is_graphify_error(result: str) -> bool:
    """Check if a graphify command result is an error or empty."""
    empty_or_error = {
        "(no output)",
        "",
        "graphify CLI not found",
        "graphify command timed out",
    }
    if result in empty_or_error:
        return True
    return bool(result.startswith("graphify error:"))


def run_graphify_init(config: dict[str, Any], complexity: str, project_root: str) -> dict[str, Any]:
    """Execute the full graphify initialization flow. Returns state updates."""
    result = {
        "graphify_built": False,
        "graphify_skipped": False,
        "graphify_error": None,
        "graphify_stats": None,
    }

    if not is_graphify_enabled(config):
        return result

    # Check skip conditions
    should_skip, skip_reason = should_skip_graphify(config, complexity, project_root)
    if should_skip:
        logger.info("Graphify skipped: %s", skip_reason)
        result["graphify_skipped"] = True
        result["graphify_skip_reason"] = skip_reason
        return result

    # Check CLI
    available, version = check_graphify_cli()
    if not available:
        logger.warning("graphify CLI not installed. Install: uv tool install graphifyy or pipx install graphifyy")
        result["graphify_error"] = "CLI not installed"
        return result

    logger.info("Graphify CLI found: %s", version)

    # Build or update graph
    graph_file = Path(project_root) / "graphify-out" / "graph.json"
    incremental = graph_file.exists()
    build_config = config.get("graphify", {})
    build_on_init = build_config.get("build_on_init", True)

    if not build_on_init:
        logger.info("Graphify build_on_init is false, skipping build")
        result["graphify_skipped"] = True
        result["graphify_skip_reason"] = "build_on_init disabled"
        return result

    success, stats = build_graph(project_root, incremental)

    if success:
        result["graphify_built"] = True
        result["graphify_stats"] = stats
        result["graphify_incremental"] = incremental
        logger.info(
            "Graphify %s: %d nodes, %d edges, %d communities",
            "updated" if incremental else "built",
            stats.get("nodes", 0),
            stats.get("edges", 0),
            stats.get("communities", 0),
        )
    else:
        result["graphify_error"] = stats.get("error", "unknown")
        logger.error("Graphify build failed: %s", stats.get("error"))

    return result

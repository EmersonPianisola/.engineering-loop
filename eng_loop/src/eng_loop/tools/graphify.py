from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

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
    code_files = list(project.glob("**/*.js")) + list(project.glob("**/*.ts")) + list(project.glob("**/*.jsx")) + list(project.glob("**/*.tsx")) + list(project.glob("**/*.py"))
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
        communities = len(set(n.get("community", "") for n in data.get("nodes", [])))

        return {
            "nodes": nodes,
            "edges": edges,
            "communities": communities,
        }
    except Exception as e:
        logger.warning("Failed to parse graph stats: %s", e)
        return {"nodes": 0, "edges": 0, "communities": 0}


def get_graphify_prompt_injection(graph_path: str) -> str:
    """Generate prompt instructions for stages to use graphify queries."""
    return f"""## KNOWLEDGE GRAPH AVAILABLE

A knowledge graph of the codebase is available at `{graph_path}/graphify-out/`.

**MANDATORY EXECUTION ORDER — Use graphify tools FIRST, read files SECOND:**

1. **graphify_query** — Start here. Get high-level architecture context before touching files.
2. **graphify_explain** — Understand specific entities before reading their source.
3. **graphify_path** — Trace connections between entities without reading intermediate files.
4. **read/glob/grep** — ONLY after graphify gives you structural context. Use for contract/type details.

**Confidence rules:**
- EXTRACTED edges: Trust — explicit in source
- INFERRED edges: Verify if critical — derived by resolution
- AMBIGUOUS edges: Must Read source — do not trust

**Important:** Graph is the map, Read is the terrain. Use graphify for structural overview, Read for contract/type details. DO NOT skip graphify and go straight to reading files."""


def get_graphify_injection(state: dict[str, Any], paths: dict[str, str]) -> str:
    """Get graphify prompt injection if graph was built. Returns empty string if not available."""
    graphify_state = state.get("graphify", {})
    if not graphify_state.get("built", False):
        return ""

    project_root = paths.get("project_root", ".")
    return get_graphify_prompt_injection(project_root)


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

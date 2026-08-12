from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import Tool

from eng_loop.tools.bash_tool import create_bash_tool
from eng_loop.tools.edit_tool import create_edit_tool
from eng_loop.tools.glob_tool import create_glob_tool
from eng_loop.tools.grep_tool import create_grep_tool
from eng_loop.tools.graphify_tools import get_graphify_tools
from eng_loop.tools.read_tool import create_read_tool
from eng_loop.tools.write_tool import create_write_tool


# Which tools each stage needs
STAGE_TOOLS: dict[str, list[str]] = {
    # Init stages — explore project structure
    "init": ["read", "glob"],
    "init.ideate": ["read"],
    "init.bdd": ["read"],
    "init.refine": ["read"],

    # Design stages — read existing code/docs for context
    "design.user-research": ["read", "glob"],
    "design.personas": ["read", "glob"],
    "design.info-arch": ["read", "glob", "grep"],
    "design.interaction": ["read", "glob", "grep"],
    "design.design-system": ["read", "glob", "grep"],
    "design.visual-design": ["read", "glob"],

    # Architecture — read codebase for context
    "arch.requirements": ["read", "glob", "grep"],
    "arch.solution": ["read", "glob", "grep"],
    "arch.review": ["read", "glob", "grep"],

    # Implementation — full toolkit
    "impl.design": ["read", "glob", "grep"],
    "impl.code": ["read", "write", "edit", "bash", "glob", "grep"],
    "doc.update": ["read", "write", "edit", "glob", "grep"],

    # Verification — read code, run tests
    "verify": ["read", "bash", "glob", "grep"],
    "e2e.execute": ["read", "write", "edit", "bash", "glob", "grep"],

    # QA — read code, run analysis
    "qa.security": ["read", "bash", "glob", "grep"],
    "qa.api-contract": ["read", "glob", "grep"],
    "qa.performance": ["read", "bash", "glob", "grep"],

    # Deploy — run build/lint commands
    "deploy.prepare": ["bash", "read", "glob"],
    "smoke.test": ["read", "write", "bash", "glob", "grep"],

    # Documentation — read and write
    "doc.decisions": ["read", "write", "glob", "grep"],
    "doc.project": ["read", "write", "glob", "grep"],

    # Post — finalize
    "post": ["read", "write", "bash", "glob"],
}

# Essence is special — it only reads, doesn't modify
ESSENCE_TOOLS: list[str] = ["read", "glob"]


def get_tools_for_stage(
    stage_id: str,
    paths: dict[str, str],
    config: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> list[Tool]:
    """Get the list of LangChain Tool instances for a stage."""
    tool_names = STAGE_TOOLS.get(stage_id, ["read"])
    config = config or {}
    state = state or {}
    bash_timeout = config.get("agent", {}).get("tool_timeout", 120)

    project_root = paths.get("project_root", ".")
    tools = []

    for name in tool_names:
        if name == "read":
            tools.append(create_read_tool())
        elif name == "write":
            tools.append(create_write_tool())
        elif name == "edit":
            tools.append(create_edit_tool())
        elif name == "bash":
            tools.append(create_bash_tool(
                workdir=project_root,
                timeout=bash_timeout,
            ))
        elif name == "glob":
            tools.append(create_glob_tool())
        elif name == "grep":
            tools.append(create_grep_tool())

    # Add graphify tools if knowledge graph was built
    graphify_tools = get_graphify_tools(state, paths)
    if graphify_tools:
        tools.extend(graphify_tools)

    return tools


def get_essence_tools(paths: dict[str, str]) -> list[Tool]:
    """Get tools for essence validation (read-only)."""
    return [create_read_tool(), create_glob_tool()]


__all__ = ["get_tools_for_stage", "get_essence_tools", "STAGE_TOOLS"]

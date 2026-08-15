from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.tools import Tool

if TYPE_CHECKING:
    from eng_loop.schemas import DynamicBlueprint, DynamicBlueprintProposal


SAFE_TOOL_POOL: set[str] = {"read", "glob", "grep", "write", "edit", "bash"}

RISK_KEYWORDS: list[str] = [
    "drop database",
    "credentials",
    "production deploy",
    "rm -rf",
    "truncate table",
    "chmod 777",
]


def resolve_allowed_tools(
    requested_capabilities: tuple[str, ...],
    workspace_root: str,
    state: dict[str, Any],
) -> list[Tool]:
    """Validate requested capabilities against safe pool and resolve to Tool instances.

    Filters out any capability not in the safe pool, then constructs
    LangChain Tool instances for the approved subset.
    """
    approved: list[str] = []
    for cap in requested_capabilities:
        if cap in SAFE_TOOL_POOL:
            approved.append(cap)

    if not approved:
        approved = ["read", "glob"]

    return get_tools_by_names(approved, state)


def get_tools_by_names(
    tool_names: list[str],
    state: dict[str, Any],
) -> list[Tool]:
    """Build Tool instances from a list of approved tool names."""
    from eng_loop.tools.bash_tool import create_bash_tool
    from eng_loop.tools.edit_tool import create_edit_tool
    from eng_loop.tools.glob_tool import create_glob_tool
    from eng_loop.tools.grep_tool import create_grep_tool
    from eng_loop.tools.read_tool import create_read_tool
    from eng_loop.tools.write_tool import create_write_tool

    paths = state.get("paths", {})
    config = state.get("config", {})
    project_root = paths.get("project_root", ".")
    bash_timeout = config.get("agent", {}).get("tool_timeout", 120)

    creator_map = {
        "read": create_read_tool,
        "write": create_write_tool,
        "edit": create_edit_tool,
        "bash": lambda: create_bash_tool(workdir=project_root, timeout=bash_timeout),
        "glob": create_glob_tool,
        "grep": create_grep_tool,
    }

    tools = []
    for name in tool_names:
        creator = creator_map.get(name)
        if creator:
            tools.append(creator())

    return tools


def authorize_blueprint(
    proposal: DynamicBlueprintProposal,
    state: dict[str, Any],
) -> DynamicBlueprint:
    """Transform LLM proposal into authorized executable blueprint.

    The framework is the authority on risk. It analyzes the work item
    and overrides the proposed complexity class if risk keywords are
    detected.
    """
    from eng_loop.schemas import DynamicBlueprint

    work_item = state.get("work_item", "").lower()

    if any(kw in work_item for kw in RISK_KEYWORDS):
        auth_complexity = "restricted"
    else:
        auth_complexity = proposal.proposed_complexity

    return DynamicBlueprint(
        plan_id=proposal.plan_id,
        trigger=proposal.trigger,
        authorized_complexity=auth_complexity,
        steps=proposal.steps,
        rationale=proposal.rationale,
    )

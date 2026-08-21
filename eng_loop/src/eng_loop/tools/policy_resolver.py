from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.tools import Tool

from eng_loop.state import get_work_item_text

if TYPE_CHECKING:
    from eng_loop.schemas import (
        AuthorizedGraphTopology,
        DynamicBlueprint,
        DynamicBlueprintProposal,
        GraphTopologyProposal,
    )


SAFE_TOOL_POOL: set[str] = {"read", "glob", "grep", "write", "edit", "bash", "ask_user"}

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
    from eng_loop.tools.ask_user_tool import create_ask_user_tool
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
        "ask_user": create_ask_user_tool,
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

    CRITICAL: Sanitizes validation rules that reference non-existent files.
    The architect frequently hallucinates file paths and symbols. Running
    validation against hallucinated paths wastes retries and blocks the
    pipeline. The policy layer is the enforcement point — not the prompt.
    """
    from eng_loop.schemas import DynamicBlueprint

    work_item = get_work_item_text(state).lower()

    if any(kw in work_item for kw in RISK_KEYWORDS):
        auth_complexity = "restricted"
    else:
        auth_complexity = proposal.proposed_complexity

    project_root = state.get("paths", {}).get("project_root", ".")
    steps = _sanitize_validation_rules(proposal.steps, project_root)

    return DynamicBlueprint(
        plan_id=proposal.plan_id,
        trigger=proposal.trigger,
        authorized_complexity=auth_complexity,
        steps=steps,
        rationale=proposal.rationale,
    )


def _sanitize_validation_rules(
    steps: tuple,
    project_root: str,
) -> tuple:
    """Strip validation rules that reference non-existent files or symbols.

    The architect hallucinates paths and symbols at >60% rate.
    Rather than waste 3 retries per bad rule, filter them at policy time.
    """
    from eng_loop.schemas import DynamicStep, ValidationRule

    root = Path(project_root).resolve()
    sanitized = []

    for step in steps:
        rules = list(step.validation_rules)
        kept = []
        for rule in rules:
            if rule.type == "files_exist":
                paths = getattr(rule.payload, "paths", [])
                existing = [p for p in paths if (root / p).exists()]
                if not existing:
                    continue
                if len(existing) < len(paths):
                    rule = ValidationRule(
                        type="files_exist",
                        payload={"paths": existing},
                    )
                kept.append(rule)
            elif rule.type == "contains_symbol":
                target = getattr(rule.payload, "target_file", "")
                if target and not (root / target).exists():
                    continue
                kept.append(rule)
            else:
                kept.append(rule)

        sanitized_step = DynamicStep(
            step_id=step.step_id,
            role_description=step.role_description,
            requested_capabilities=step.requested_capabilities,
            max_attempts=step.max_attempts,
            validation_rules=tuple(kept),
        )
        sanitized.append(sanitized_step)

    return tuple(sanitized)


# ───────────────────────────────────────────────────────────────────
# TOPOLOGY FIREWALL — 5-layer validation
# LLM proposes → Policy authorizes → Builder compiles → Runtime executes
# ───────────────────────────────────────────────────────────────────


class TopologyValidationError(Exception):
    """Raised when a topology proposal fails policy validation."""

    def __init__(self, layer: str, message: str):
        self.layer = layer
        self.message = message
        super().__init__(f"[{layer}] {message}")


def _get_registry_stage_ids() -> set[str]:
    """Return all known stage IDs from the registry."""
    from eng_loop.node_registry import build_registry

    registry = build_registry()
    return {spec.id for spec in registry.all_specs()}


def _validate_structural(proposal: GraphTopologyProposal) -> None:
    """Layer 1: Structural integrity — basic sanity checks."""
    if not proposal.required_stages:
        raise TopologyValidationError("structural", "required_stages is empty")

    if len(proposal.required_stages) != len(set(proposal.required_stages)):
        raise TopologyValidationError("structural", "required_stages contains duplicates")

    if not proposal.edges:
        raise TopologyValidationError("structural", "edges is empty")

    # Check for duplicate edges
    seen_edges = set()
    for edge in proposal.edges:
        key = (edge.from_stage, edge.to_stage, edge.edge_type)
        if key in seen_edges:
            raise TopologyValidationError("structural", f"Duplicate edge: {key}")
        seen_edges.add(key)

    # Check for unauthorized self-loops
    for edge in proposal.edges:
        if edge.from_stage == edge.to_stage and edge.edge_type != "loopback":
            raise TopologyValidationError(
                "structural",
                f"Self-loop on '{edge.from_stage}' requires edge_type='loopback'",
            )


def _validate_registry(proposal: GraphTopologyProposal) -> None:
    """Layer 2: Registry validation — all stages must exist in the catalog."""
    known_stages = _get_registry_stage_ids()
    # Meta nodes are always allowed
    meta_nodes = {"init.setup", "dynamic.architect", "meta.executor"}
    valid_ids = known_stages | meta_nodes

    for stage_id in proposal.required_stages:
        if stage_id not in valid_ids:
            raise TopologyValidationError(
                "registry",
                f"Stage '{stage_id}' not found in node catalog",
            )

    for edge in proposal.edges:
        if edge.from_stage not in ("__start__",) and edge.from_stage not in valid_ids:
            raise TopologyValidationError(
                "registry",
                f"Edge source '{edge.from_stage}' not in node catalog",
            )
        if edge.to_stage not in ("__end__",) and edge.to_stage not in valid_ids:
            raise TopologyValidationError(
                "registry",
                f"Edge target '{edge.to_stage}' not in node catalog",
            )


def _validate_boundary(proposal: GraphTopologyProposal) -> None:
    """Layer 3: Boundary validation — entry/exit nodes must exist."""
    stage_set = set(proposal.required_stages)

    # Entry: init must be present
    if "init" not in stage_set:
        raise TopologyValidationError("boundary", "Entry node 'init' is required")

    # Exit: post must be present
    if "post" not in stage_set:
        raise TopologyValidationError("boundary", "Exit node 'post' is required")


def _validate_connectivity(proposal: GraphTopologyProposal) -> None:
    """Layer 4: Cycle detection and reachability analysis.

    Ensures:
    - No cycles in the graph
    - All nodes are reachable from entry
    - Exit is reachable from entry
    - No isolated nodes
    """
    stage_set = set(proposal.required_stages)
    # Build adjacency list (node_name format for graph operations)
    adj: dict[str, list[str]] = {s: [] for s in stage_set}

    for edge in proposal.edges:
        from_id = edge.from_stage
        to_id = edge.to_stage
        if from_id == "__start__":
            from_id = "init"
        if to_id == "__end__":
            # __end__ is not in stage_set, skip this edge for connectivity check
            # (it just means the source node can reach the exit)
            continue
        if from_id in stage_set and to_id in stage_set:
            adj.setdefault(from_id, []).append(to_id)

    # Cycle detection via DFS
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {s: WHITE for s in stage_set}

    def has_cycle(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adj.get(node, []):
            if color.get(neighbor) == GRAY:
                return True
            if color.get(neighbor) == WHITE and has_cycle(neighbor):
                return True
        color[node] = BLACK
        return False

    for start_node in stage_set:
        if color.get(start_node) == WHITE:
            if has_cycle(start_node):
                raise TopologyValidationError("connectivity", "Graph contains a cycle")

    # Reachability: BFS from entry
    entry = "init"
    visited = set()
    queue = [entry]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                queue.append(neighbor)

    # All stages must be reachable from entry
    unreachable = stage_set - visited
    if unreachable:
        raise TopologyValidationError(
            "connectivity",
            f"Stages not reachable from entry: {unreachable}",
        )

    # Exit must be reachable
    if "post" not in visited:
        raise TopologyValidationError(
            "connectivity",
            "Exit node 'post' is not reachable from entry",
        )


def _validate_semantic_policy(
    proposal: GraphTopologyProposal,
    state: dict[str, Any],
) -> str:
    """Layer 5: Semantic policy — context-aware restrictions.

    Returns policy notes string (may be empty for clean pass).
    Raises TopologyValidationError for fatal policy violations.
    """
    notes = []
    work_item = get_work_item_text(state).lower()
    complexity = state.get("complexity", "small")
    ui_project = state.get("ui_project", False)
    stage_set = set(proposal.required_stages)

    # Risk keywords: flag but don't reject topology
    if any(kw in work_item for kw in RISK_KEYWORDS):
        notes.append("Risk keywords detected in work item — topology authorized with monitoring")

    # UI-only stages without UI project
    ui_only_stages = {"e2e.execute", "smoke.test"}
    if not ui_project:
        for s in ui_only_stages:
            if s in stage_set:
                notes.append(f"UI-only stage '{s}' included but project is not a UI project")

    # Min-complexity violations (warning, not fatal)
    from eng_loop.state import COMPLEXITY_ORDER, STAGE_MIN_COMPLEXITY

    for stage_id in stage_set:
        min_c = STAGE_MIN_COMPLEXITY.get(stage_id)
        if min_c:
            if COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
                notes.append(f"Stage '{stage_id}' requires min_complexity={min_c}, current={complexity}")

    return "; ".join(notes)


def _validate_cost_budget(
    proposal: GraphTopologyProposal,
    state: dict[str, Any],
) -> str:
    """Layer 6: Cost firewall — over-spawning prevention.

    Validates that the proposed topology does not exceed the parallel token budget.
    A graph of parallel agents costs ~15x tokens per fork.

    Returns policy notes string (may be empty for clean pass).
    Raises TopologyValidationError for fatal budget violations.
    """
    from eng_loop.schemas import ExecutionPolicy

    # Calculate total parallel nodes in the topology
    # Count stages that could run in parallel (same phase group, or no phase grouping)
    max_proposed_parallel = max(
        (len(pg.stages) for pg in proposal.phase_groups),
        default=len(proposal.required_stages),
    )

    # Get budget from execution policies or use defaults
    max_parallel_tokens = state.get("config", {}).get("hardware", {}).get("max_parallel_tokens", 150000)
    agent_context_limit = state.get("config", {}).get("hardware", {}).get("agent_context_limit", 66666)
    max_parallel_agents = state.get("config", {}).get("hardware", {}).get("max_parallel_agents", 3)

    # Check: n_parallel_agents × agent_context_limit ≤ max_parallel_tokens
    projected_tokens = max_proposed_parallel * agent_context_limit
    if projected_tokens > max_parallel_tokens:
        raise TopologyValidationError(
            "cost",
            f"Proposed parallelism ({max_proposed_parallel} nodes × {agent_context_limit} tokens = {projected_tokens}) exceeds budget ({max_parallel_tokens}). Reduce parallel stages or increase max_parallel_tokens.",
        )

    # Check: max_parallel_nodes per stage
    for policy in proposal.execution_policies:
        if policy.max_parallel_nodes > max_parallel_agents:
            raise TopologyValidationError(
                "cost",
                f"Stage '{policy.stage_id}' proposes max_parallel_nodes={policy.max_parallel_nodes} but config limits to {max_parallel_agents}.",
            )

    # Check: max_fan_out per stage
    for policy in proposal.execution_policies:
        if policy.max_fan_out > policy.max_parallel_nodes:
            raise TopologyValidationError(
                "cost",
                f"Stage '{policy.stage_id}' fan_out={policy.max_fan_out} exceeds its own max_parallel_nodes={policy.max_parallel_nodes}.",
            )

    # Warning: high parallelism
    if max_proposed_parallel > max_parallel_agents:
        return (
            f"High parallelism detected ({max_proposed_parallel} proposed, budget is {max_parallel_agents}). "
            "Consider batching parallel work."
        )

    return ""


def authorize_topology(
    proposal: GraphTopologyProposal,
    state: dict[str, Any],
) -> AuthorizedGraphTopology:
    """6-layer topology firewall.

    Validates a GraphTopologyProposal through six sequential layers:
    1. Structural: basic integrity (non-empty, no duplicates, valid self-loops)
    2. Registry: all stages/edges reference known catalog entries
    3. Boundary: entry (init) and exit (post) nodes present
    4. Connectivity: no cycles, all nodes reachable, exit reachable from entry
    5. Semantic: context-aware policy checks (risk, UI, complexity)
    6. Cost: over-spawning prevention (parallel token budget, max_fan_out)

    Returns an AuthorizedGraphTopology on success.
    Raises TopologyValidationError on any failure (caller should catch and fallback).
    """
    from eng_loop.schemas import AuthorizedGraphTopology

    # Layer 1: Structural
    _validate_structural(proposal)

    # Layer 2: Registry
    _validate_registry(proposal)

    # Layer 3: Boundary
    _validate_boundary(proposal)

    # Layer 4: Connectivity
    _validate_connectivity(proposal)

    # Layer 5: Semantic policy
    policy_notes = _validate_semantic_policy(proposal, state)

    # Layer 6: Cost firewall — over-spawning prevention
    cost_notes = _validate_cost_budget(proposal, state)
    if cost_notes:
        policy_notes = f"{policy_notes}; {cost_notes}".strip("; ")

    return AuthorizedGraphTopology(
        plan_id=proposal.plan_id,
        authorized_stages=proposal.required_stages,
        authorized_edges=proposal.edges,
        phase_groups=proposal.phase_groups,
        execution_policies=proposal.execution_policies,
        rationale=proposal.rationale,
        policy_notes=policy_notes,
    )

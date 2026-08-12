from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eng_loop.edge_rules import build_edge_rules
from eng_loop.node_registry import _make_node_name
from eng_loop.state import STAGE_ORDER, get_active_stages, is_stage_active

logger = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    expected_next: str | None = None
    requested_stage: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "ok": self.ok,
            "violations": self.violations,
            "expected_next": self.expected_next,
            "requested_stage": self.requested_stage,
        }, indent=2)

    def __str__(self) -> str:
        status = "OK" if self.ok else "BLOCKED"
        lines = [f"COMPLIANCE: {status}"]
        if self.violations:
            for v in self.violations:
                lines.append(f"  VIOLATION: {v}")
        if self.expected_next:
            lines.append(f"  EXPECTED: {self.expected_next}")
        return "\n".join(lines)


def check_compliance(
    state: dict[str, Any],
    requested_stage: str,
) -> ComplianceResult:
    """Validate that the requested stage transition is compliant with the topology.

    Checks:
    1. requested_stage is active for the current complexity/work_type
    2. No active stages were skipped between last_done and requested
    3. requested_stage matches the expected next stage per edge rules

    Returns ComplianceResult with ok=True if all checks pass.
    """
    violations = []
    complexity = state.get("complexity", "unset")
    ui_project = state.get("ui_project", False)
    work_type = state.get("work_type", "feature")
    stages = state.get("stages", {})

    # CHECK 1: Is requested_stage active?
    if not is_stage_active(requested_stage, complexity, ui_project, work_type):
        violations.append(
            f"INACTIVE_STAGE: '{requested_stage}' is not active "
            f"(complexity={complexity}, work_type={work_type}, ui={ui_project})"
        )
        return ComplianceResult(
            ok=False, violations=violations, requested_stage=requested_stage,
        )

    # CHECK 2: Are there skipped active stages?
    last_done = _find_last_done_stage(stages)
    if last_done:
        skipped = _find_skipped_stages(stages, last_done, requested_stage, complexity, ui_project, work_type)
        if skipped:
            violations.append(
                f"STAGE_SKIP: {len(skipped)} active stage(s) skipped: {skipped}"
            )

    # CHECK 3: Is this the expected next stage per edge rules?
    expected = _get_expected_next_stage(state, last_done, complexity, ui_project, work_type)
    if expected and expected != requested_stage:
        violations.append(
            f"WRONG_ORDER: Expected '{expected}', got '{requested_stage}'"
        )
    elif not expected:
        # No expected next stage — all active stages may be done
        all_done = all(
            stages.get(s, {}).get("done", False)
            for s in STAGE_ORDER
            if is_stage_active(s, complexity, ui_project, work_type)
        )
        if not all_done:
            incomplete = [
                s for s in STAGE_ORDER
                if is_stage_active(s, complexity, ui_project, work_type)
                and not stages.get(s, {}).get("done", False)
            ]
            if incomplete:
                violations.append(
                    f"NO_EXPECTED: No routing rule found. Incomplete stages: {incomplete}"
                )

    return ComplianceResult(
        ok=len(violations) == 0,
        violations=violations,
        expected_next=expected,
        requested_stage=requested_stage,
    )


def check_compliance_from_files(
    state_file: str,
    requested_stage: str,
) -> ComplianceResult:
    """Load state from file and run compliance check."""
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    return check_compliance(state, requested_stage)


def _find_last_done_stage(stages: dict[str, Any]) -> str | None:
    """Find the last completed stage by STAGE_ORDER position."""
    last = None
    for sid in STAGE_ORDER:
        if stages.get(sid, {}).get("done", False):
            last = sid
    return last


def _find_skipped_stages(
    stages: dict[str, Any],
    last_done: str,
    requested: str,
    complexity: str,
    ui_project: bool,
    work_type: str,
) -> list[str]:
    """Find active stages between last_done and requested that are not done."""
    try:
        last_idx = STAGE_ORDER.index(last_done)
    except ValueError:
        return []

    try:
        req_idx = STAGE_ORDER.index(requested)
    except ValueError:
        return []

    if req_idx <= last_idx:
        return []  # Not moving forward

    skipped = []
    for i in range(last_idx + 1, req_idx):
        sid = STAGE_ORDER[i]
        if not is_stage_active(sid, complexity, ui_project, work_type):
            continue  # Inactive stage, not a skip
        if not stages.get(sid, {}).get("done", False):
            skipped.append(sid)

    return skipped


def _get_expected_next_stage(
    state: dict[str, Any],
    last_done: str | None,
    complexity: str,
    ui_project: bool,
    work_type: str,
) -> str | None:
    """Determine the expected next stage using edge rules with bypass resolution."""
    active_ids = set(get_active_stages(complexity, ui_project, work_type))
    active_names = {_make_node_name(s) for s in active_ids}

    if not last_done:
        return "init"

    engine = build_edge_rules(parallel_qa=False)

    # Use bypass resolution to handle inactive intermediate nodes
    resolved_rules = engine.resolve_with_bypass(active_names | {"__start__"}, state)

    last_name = _make_node_name(last_done)

    # Get forward-progress edges (not loopback) from resolved rules
    next_nodes = []
    for rule in resolved_rules:
        if not rule.matches(last_name):
            continue
        if rule.edge_type == "loopback":
            continue
        to_node = rule.to_node
        if to_node == "__end__":
            continue
        if rule.evaluate(state):
            next_nodes.append(_node_name_to_stage_id(to_node))

    if next_nodes:
        return next_nodes[0]
    return None


def _node_name_to_stage_id(node_name: str) -> str:
    """Convert node name back to stage ID."""
    # Build reverse mapping
    reverse = {}
    for sid in STAGE_ORDER:
        reverse[_make_node_name(sid)] = sid
    return reverse.get(node_name, node_name)

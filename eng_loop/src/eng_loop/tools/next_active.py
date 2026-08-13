from __future__ import annotations

from typing import Any

from eng_loop.state import STAGE_ORDER, STAGE_MIN_COMPLEXITY, COMPLEXITY_ORDER


_STAGE_TO_NODE: dict[str, str] = {}
_NODE_TO_STAGE: dict[str, str] = {}
for _sid in STAGE_ORDER:
    _nn = _sid.replace(".", "-").replace("_", "-")
    _STAGE_TO_NODE[_sid] = _nn
    _NODE_TO_STAGE[_nn] = _sid


_NEXT_IN_ORDER: dict[str, str] = {}
for i, _sid in enumerate(STAGE_ORDER):
    if i + 1 < len(STAGE_ORDER):
        _NEXT_IN_ORDER[_sid] = STAGE_ORDER[i + 1]


def _is_active(stage_id: str, state: dict[str, Any]) -> bool:
    """Check whether a stage should execute in the current pipeline."""
    complexity = state.get("complexity", "unset")
    if complexity != "unset":
        min_c = STAGE_MIN_COMPLEXITY.get(stage_id)
        if min_c and COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
            return False

    ui_project = state.get("ui_project", False)
    if stage_id in ("e2e.execute", "smoke.test") and not ui_project:
        return False

    work_type = state.get("work_type", "feature")
    from eng_loop.tools.autosizing import (
        OPERATIONAL_EXCLUDED_STAGES,
        DOCUMENTATION_EXCLUDED_STAGES,
    )
    if work_type == "documentation" and stage_id in DOCUMENTATION_EXCLUDED_STAGES:
        return False
    if work_type == "operational" and stage_id in OPERATIONAL_EXCLUDED_STAGES:
        return False
    if work_type == "bugfix" and stage_id in (
        "design.user-research", "design.personas", "design.info-arch",
        "design.interaction", "design.design-system", "design.visual-design",
    ):
        return False

    return True


def resolve_next(intended_node: str, state: dict[str, Any]) -> str:
    """Resolve the next active node starting from *intended_node*.

    If the intended node is active, returns it unchanged.
    Otherwise walks forward through STAGE_ORDER until an active node is found,
    or returns "__end__".
    """
    stage_id = _NODE_TO_STAGE.get(intended_node, intended_node)
    if _is_active(stage_id, state):
        return intended_node

    current = stage_id
    while current:
        next_stage = _NEXT_IN_ORDER.get(current)
        if not next_stage:
            return "__end__"
        if _is_active(next_stage, state):
            return _STAGE_TO_NODE.get(next_stage, next_stage)
        current = next_stage

    return "__end__"

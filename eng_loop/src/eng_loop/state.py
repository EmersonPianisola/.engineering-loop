from __future__ import annotations

import copy
import json
from operator import add
from pathlib import Path
from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

STAGE_ORDER: list[str] = [
    "init",
    "init.ideate",
    "init.bdd",
    "init.refine",
    "design.user-research",
    "design.personas",
    "design.info-arch",
    "design.interaction",
    "design.design-system",
    "design.visual-design",
    "arch.requirements",
    "arch.solution",
    "arch.review",
    "impl.design",
    "impl.code",
    "doc.update",
    "verify",
    "e2e.execute",
    "qa.security",
    "qa.api-contract",
    "qa.performance",
    "deploy.prepare",
    "smoke.test",
    "doc.decisions",
    "doc.project",
    "post",
]

STAGE_MIN_COMPLEXITY: dict[str, Literal["small", "medium", "large", "complex"]] = {
    "init.bdd": "large",
    "design.user-research": "large",
    "design.personas": "large",
    "design.info-arch": "large",
    "design.interaction": "large",
    "design.design-system": "large",
    "design.visual-design": "large",
    "arch.requirements": "medium",
    "arch.solution": "medium",
    "arch.review": "complex",
    "qa.security": "medium",
    "qa.api-contract": "medium",
    "qa.performance": "complex",
    "doc.decisions": "medium",
    "doc.project": "medium",
}

COMPLEXITY_ORDER = {"small": 0, "medium": 1, "large": 2, "complex": 3}


# ──────────────────────────────────────────────
# FixTask schema (structured verifier feedback)
# ──────────────────────────────────────────────


class FixTask(BaseModel):
    source: str = Field(description="Originating stage, e.g. 'verify', 'qa.security', 'e2e.execute'")
    gap: str = Field(description="Description of the problem found")
    evidence: str = Field(description="file:line evidence from verification artifact")
    severity: Literal["critical", "major", "minor"] = Field(default="critical")
    suggested_fix: str = Field(default="", description="Optional hint from the verifier for the fix")


# ──────────────────────────────────────────────
# Reducers
# ──────────────────────────────────────────────


def _merge_dict(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(old)
    for k, v in new.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k].update(v)
        else:
            result[k] = v
    return result


def _last_write_wins(current: str, update: str) -> str:
    return update if update else current


def _overwrite(current: Any, update: Any) -> Any:
    """Always use the new value, even if it's empty/falsy.
    Used for fields that must be explicitly cleared (e.g., fix_tasks, rollback_target)."""
    return update


def _max_int(current: int, update: int) -> int:
    return max(current, update)


def rollback_to_stage(
    current_stages: dict[str, dict[str, Any]],
    target_stage: str,
    reset_from: str = "impl.code",
) -> dict[str, dict[str, Any]]:
    """Reducer: reset all stages in STAGE_ORDER between reset_from and
    target_stage (inclusive) to their initial state.

    Used when a verifier/QA node fails and needs to rewind the causal
    chain back to the implementation node.

    Example: verify FAIL → reset impl.code, doc.update, verify.
    """
    result = copy.deepcopy(current_stages)

    try:
        start_idx = STAGE_ORDER.index(reset_from)
    except ValueError:
        start_idx = 0

    try:
        end_idx = STAGE_ORDER.index(target_stage)
    except ValueError:
        end_idx = len(STAGE_ORDER) - 1

    for i in range(start_idx, end_idx + 1):
        sid = STAGE_ORDER[i]
        result[sid] = {
            "done": False,
            "attempts": 0,
            "essence_checked": False,
            "output": "",
            "artifact_path": "",
        }

    return result


# ──────────────────────────────────────────────
# Stage helpers
# ──────────────────────────────────────────────


class StageState(dict[str, Any]):
    done: bool = False
    attempts: int = 0
    essence_checked: bool = False
    output: str = ""
    artifact_path: str = ""


def make_stage() -> dict[str, Any]:
    return {
        "done": False,
        "attempts": 0,
        "essence_checked": False,
        "output": "",
        "artifact_path": "",
    }


def init_stages() -> dict[str, dict[str, Any]]:
    return {sid: make_stage() for sid in STAGE_ORDER}


# ──────────────────────────────────────────────
# PipelineState (LangGraph StateGraph schema)
# ──────────────────────────────────────────────


class PipelineState(dict[str, Any]):
    current_stage: Annotated[str, _last_write_wins] = ""
    iteration: Annotated[int, _max_int] = 0
    status: Annotated[str, _last_write_wins] = "running"
    blocking_condition: Annotated[str, _last_write_wins] = ""
    complexity: Literal["unset", "small", "medium", "large", "complex"] = "unset"
    work_type: str = "feature"
    work_item: str = ""
    ideation: str | None = None
    ui_project: bool = False
    tags: list[str] = []
    stages: Annotated[dict[str, Any], _merge_dict] = {}  # type: ignore[assignment]
    decisions: Annotated[list[str], add] = []  # type: ignore[assignment]
    stage_artifacts: Annotated[dict[str, str], _merge_dict] = {}  # type: ignore[assignment]
    lessons: list[str] = []
    errors: Annotated[list[str], add] = []  # type: ignore[assignment]
    messages: Annotated[list, add_messages] = []  # type: ignore[assignment]
    config: dict[str, Any] = {}
    paths: dict[str, str] = {}
    # Dynamic graph topology (populated by GraphBuilder)
    graph_topology: dict[str, Any] = {}
    active_nodes: list[str] = []
    parallel_groups: dict[str, list[str]] = {}
    # Context management (v12 — shared context between stages)
    handoffs: Annotated[dict[str, str], _merge_dict] = {}  # type: ignore[assignment]
    context_tiers: dict[str, Any] = {}
    # Timing metrics
    timing: dict[str, Any] = {}

    # Phase 1: New fields
    fix_tasks: Annotated[list[dict[str, Any]], _overwrite] = []
    fix_iteration: Annotated[int, _max_int] = 0
    rollback_target: Annotated[str, _overwrite] = ""
    explorer_evidence: Annotated[list[str], _last_write_wins] = []
    codebase_facts: Annotated[dict[str, Any], _last_write_wins] = {}
    # Dynamic node orchestration (V1.3)
    dynamic_plan: Annotated[dict[str, Any] | None, _last_write_wins] = None
    dynamic_runtime: Annotated[dict[str, Any], _merge_dict] = {}


def make_initial_state(config: dict[str, Any], paths: dict[str, str]) -> dict[str, Any]:
    return {
        "current_stage": "",
        "iteration": 0,
        "status": "running",
        "blocking_condition": "",
        "complexity": "unset",
        "work_type": "feature",
        "work_item": "",
        "ideation": None,
        "ui_project": False,
        "tags": [],
        "stages": init_stages(),
        "decisions": [],
        "stage_artifacts": {},
        "lessons": [],
        "errors": [],
        "messages": [],
        "config": config,
        "paths": paths,
        "graph_topology": {},
        "active_nodes": [],
        "parallel_groups": {},
        "handoffs": {},
        "context_tiers": {},
        "timing": {},
        "fix_tasks": [],
        "fix_iteration": 0,
        "rollback_target": "",
        "explorer_evidence": [],
        "codebase_facts": {},
        "dynamic_plan": None,
        "dynamic_runtime": {
            "cursor": 0,
            "attempts": {},
            "completed": [],
            "failed": [],
            "status": "pending",
            "step_audit": [],
        },
    }


def get_max_attempts(config: dict[str, Any], stage_id: str) -> int:
    key = f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts"
    constraints = config.get("constraints", {})
    return constraints.get(key, 2)


def is_stage_active(stage_id: str, complexity: str, ui_project: bool, work_type: str = "feature") -> bool:
    if complexity == "unset":
        return True

    min_complexity = STAGE_MIN_COMPLEXITY.get(stage_id)
    if min_complexity:
        if COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_complexity, 0):
            return False

    if stage_id in ("e2e.execute", "smoke.test"):
        return ui_project

    from eng_loop.tools.autosizing import DOCUMENTATION_EXCLUDED_STAGES, OPERATIONAL_EXCLUDED_STAGES

    if work_type == "documentation" and stage_id in DOCUMENTATION_EXCLUDED_STAGES:
        return False
    if work_type == "operational" and stage_id in OPERATIONAL_EXCLUDED_STAGES:
        return False
    if work_type == "bugfix" and stage_id in (
        "design.user-research",
        "design.personas",
        "design.info-arch",
        "design.interaction",
        "design.design-system",
        "design.visual-design",
    ):
        return False

    return True


def get_active_stages(complexity: str, ui_project: bool, work_type: str = "feature") -> list[str]:
    return [s for s in STAGE_ORDER if is_stage_active(s, complexity, ui_project, work_type)]


def next_incomplete_stage(state: dict[str, Any]) -> str | None:
    complexity = state.get("complexity", "unset")
    ui_project = state.get("ui_project", False)
    work_type = state.get("work_type", "feature")
    for sid in STAGE_ORDER:
        if not is_stage_active(sid, complexity, ui_project, work_type):
            continue
        stage = state["stages"].get(sid, {})
        if not stage.get("done", False):
            return sid
    return None


def all_active_stages_done(state: dict[str, Any]) -> bool:
    return next_incomplete_stage(state) is None


def load_state_template(template_path: str | Path) -> dict[str, Any]:
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def restore_snapshot(snapshot_path: str | Path) -> dict[str, Any]:
    """Load a historical state snapshot and restore it as a valid pipeline state.

    Merges missing fields with defaults so the restored state is compatible
    with the current PipelineState schema.
    """
    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    defaults = {
        "current_stage": "",
        "iteration": data.get("iteration", 0),
        "status": "running",
        "blocking_condition": "",
        "complexity": data.get("complexity", "unset"),
        "work_type": data.get("work_type", "feature"),
        "work_item": data.get("work_item", ""),
        "ideation": data.get("ideation"),
        "ui_project": data.get("ui_project", False),
        "tags": data.get("tags", []),
        "stages": data.get("stages", init_stages()),
        "decisions": data.get("decisions", []),
        "stage_artifacts": data.get("stage_artifacts", {}),
        "lessons": data.get("lessons", []),
        "errors": data.get("errors", []),
        "messages": data.get("messages", []),
        "config": data.get("config", {}),
        "paths": data.get("paths", {}),
        "graph_topology": data.get("graph_topology", {}),
        "active_nodes": data.get("active_nodes", []),
        "parallel_groups": data.get("parallel_groups", {}),
        "handoffs": data.get("handoffs", {}),
        "context_tiers": data.get("context_tiers", {}),
        "timing": data.get("timing", {}),
        "fix_tasks": data.get("fix_tasks", []),
        "fix_iteration": data.get("fix_iteration", 0),
        "rollback_target": data.get("rollback_target", ""),
        "explorer_evidence": data.get("explorer_evidence", []),
        "codebase_facts": data.get("codebase_facts", {}),
        "dynamic_plan": data.get("dynamic_plan"),
        "dynamic_runtime": data.get(
            "dynamic_runtime",
            {
                "cursor": 0,
                "attempts": {},
                "completed": [],
                "failed": [],
                "status": "pending",
                "step_audit": [],
            },
        ),
    }
    return defaults

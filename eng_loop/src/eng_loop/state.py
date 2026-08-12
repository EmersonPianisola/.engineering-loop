from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from operator import add

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


def _merge_dict(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(old)
    for k, v in new.items():
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k].update(v)
        else:
            result[k] = v
    return result


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


def _last_write_wins(current: str, update: str) -> str:
    """Reducer for current_stage: last non-empty write wins."""
    return update if update else current


def _max_int(current: int, update: int) -> int:
    """Reducer for iteration: take the maximum value."""
    return max(current, update)


class PipelineState(dict[str, Any]):
    current_stage: Annotated[str, _last_write_wins] = ""
    iteration: Annotated[int, _max_int] = 0
    status: Literal["running", "done", "blocked", "halted"] = "running"
    blocking_condition: str = ""
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

    # Work type exclusions
    from eng_loop.tools.autosizing import OPERATIONAL_EXCLUDED_STAGES
    if work_type == "operational" and stage_id in OPERATIONAL_EXCLUDED_STAGES:
        return False
    if work_type == "bugfix" and stage_id in (
        "design.user-research", "design.personas", "design.info-arch",
        "design.interaction", "design.design-system", "design.visual-design",
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

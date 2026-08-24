from __future__ import annotations

import copy
import json
import logging
from operator import add
from pathlib import Path
from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from eng_loop.context_bus import ContextBus, synonyms_from_config

logger = logging.getLogger(__name__)

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
    "qa.static",
    "qa.unit",
    "qa.integration",
    "e2e.execute",
    "qa.security",
    "qa.api-contract",
    "qa.performance",
    "qa.human.flow",
    "qa.human.ux",
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
    "qa.static": "small",
    "qa.unit": "small",
    "qa.integration": "medium",
    "qa.human.flow": "medium",
    "qa.human.ux": "medium",
    "doc.decisions": "medium",
    "doc.project": "medium",
}

COMPLEXITY_ORDER = {"small": 0, "medium": 1, "large": 2, "complex": 3}


def to_stage_id(name: str | None) -> str | None:
    """Normalize any accepted stage notation to its canonical STAGE_ORDER id.

    Accepts the dotted id as-is ("qa.api-contract"), node names with a single
    separator ("impl-code" -> "impl.code"), and multi-hyphen node names
    ("qa-human-flow" -> "qa.human.flow"). Returns None when no known id matches.
    """
    if not isinstance(name, str) or not name:
        return None
    if name in STAGE_ORDER:
        return name
    all_dotted = name.replace("-", ".")
    if all_dotted in STAGE_ORDER:
        return all_dotted
    first_dotted = name.replace("-", ".", 1)
    if first_dotted in STAGE_ORDER:
        return first_dotted
    return None


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


def get_work_item_text(state: dict[str, Any], default: str = "") -> str:
    """Normalize work_item to str, regardless of whether it's str or dict.

    Central accessor — use this instead of state.get("work_item", ...)
    whenever the result will be used as a string (slicing, .lower(), f-string, etc.).
    """
    wi = state.get("work_item", default)
    if isinstance(wi, dict):
        return wi.get("description", wi.get("text", wi.get("title", str(wi))))
    return str(wi) if wi else default


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

    IMPORTANT: Stages with status='blocked' or 'waiting_for_input' are
    NEVER reset by rollback. BLOCKED means infrastructure failure.
    WAITING_FOR_INPUT means human resolution is in progress.

    Fail-safe: target_stage/reset_from are normalized via to_stage_id; if
    either is not a known stage id the stages are returned UNCHANGED (and a
    warning is logged) — never a full-chain wipe from a bad name.

    Example: verify FAIL → reset impl.code, doc.update, verify.
    """
    result = copy.deepcopy(current_stages)

    start_stage = to_stage_id(reset_from)
    if start_stage is None:
        logger.warning("rollback_to_stage: unknown reset_from %r — returning stages unchanged", reset_from)
        return result

    end_stage = to_stage_id(target_stage)
    if end_stage is None:
        logger.warning("rollback_to_stage: unknown target_stage %r — returning stages unchanged", target_stage)
        return result

    start_idx = STAGE_ORDER.index(start_stage)
    end_idx = STAGE_ORDER.index(end_stage)

    for i in range(start_idx, end_idx + 1):
        sid = STAGE_ORDER[i]
        existing = current_stages.get(sid, {})
        # Never rollback BLOCKED (infrastructure) or WAITING_FOR_INPUT (human pending)
        if existing.get("status") in ("blocked", "waiting_for_input"):
            continue
        result[sid] = {
            "done": False,
            "attempts": 0,
            # Cumulative counter — survives rollbacks so anti-loop guards
            # (contract gate) still see the exhausted source.
            "total_attempts": existing.get("total_attempts", 0) + existing.get("attempts", 0),
            "essence_checked": False,
            "output": "",
            "artifact_path": "",
            "verdict": "",
            "status": "",
            "findings": [],
            "evidence": {},
            "started_at": 0.0,
            "completed_at": 0.0,
        }

    return result


# ──────────────────────────────────────────────
# Stage helpers
# ──────────────────────────────────────────────


def make_stage() -> dict[str, Any]:
    return {
        "done": False,
        "attempts": 0,
        "total_attempts": 0,
        "essence_checked": False,
        "output": "",
        "artifact_path": "",
        "verdict": "",
        "status": "",
        "findings": [],
        "evidence": {},
        "started_at": 0.0,
        "completed_at": 0.0,
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
    # _overwrite: recovery/fix flows explicitly clear it with "" and that must
    # win (with _last_write_wins the stale condition persisted in checkpointed
    # mode).
    blocking_condition: Annotated[str, _overwrite] = ""
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
    # QA results — structured evidence per stage
    qa_results: Annotated[dict[str, Any], _merge_dict] = {}
    # Context Bus — append-only carrier for clarifications, intent refinements, critical findings
    context_bus: Annotated[ContextBus, _last_write_wins] = ContextBus()  # type: ignore[assignment]
    # Essence gate operational state (separate from work_item.clarifications)
    essence: Annotated[dict[str, Any], _last_write_wins] = {}
    # Clarification questions pending user input
    essence_clarifying_questions: Annotated[list[dict[str, Any]], _last_write_wins] = []
    # Audit trail of ask_user interactions during agent execution
    user_interactions: Annotated[list[dict[str, Any]], _overwrite] = []
    # Auto-recovery state
    recovery_attempts: Annotated[int, _max_int] = 0
    # Overwrite (not `add`): the recovery loop re-invokes the graph with the
    # full state, so an append reducer duplicated entries on every recovery
    # attempt ([e1, e1, e2]). Only the CLI loop updates this field.
    recovery_history: Annotated[list[dict[str, Any]], _overwrite] = []
    # Final computed outcome (set by the post node). Channel required —
    # unannotated keys are dropped by the graph and never persisted.
    task_outcome: Annotated[str | None, _last_write_wins] = None


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
        "qa_results": {},
        "context_bus": ContextBus(synonyms=synonyms_from_config(config)),
        "dynamic_runtime": {
            "cursor": 0,
            "attempts": {},
            "completed": [],
            "failed": [],
            "status": "pending",
            "step_audit": [],
        },
        "essence": {
            "checked": False,
            "blocked_stage": None,
            "decision": None,
            "clarification_attempts": 0,
            "auto_adjust_attempts": 0,
            "pending_questions": [],
            "resolved_findings": [],
        },
        "essence_clarifying_questions": [],
        "user_interactions": [],
        "recovery_attempts": 0,
        "recovery_history": [],
        "task_outcome": None,
    }


def get_max_attempts(config: dict[str, Any], stage_id: str) -> int:
    key = f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts"
    constraints = config.get("constraints", {})
    return constraints.get(key, 2)


def is_stage_active(stage_id: str, complexity: str, ui_project: bool, work_type: str = "feature") -> bool:
    if complexity == "unset":
        return True

    min_complexity = STAGE_MIN_COMPLEXITY.get(stage_id)
    if min_complexity and COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_complexity, 0):
        return False

    if stage_id in ("e2e.execute", "smoke.test", "qa.human.ux"):
        return ui_project

    from eng_loop.tools.autosizing import DOCUMENTATION_EXCLUDED_STAGES, OPERATIONAL_EXCLUDED_STAGES

    if work_type == "documentation" and stage_id in DOCUMENTATION_EXCLUDED_STAGES:
        return False
    if work_type == "operational" and stage_id in OPERATIONAL_EXCLUDED_STAGES:
        return False
    return not (
        work_type == "bugfix"
        and stage_id
        in (
            "design.user-research",
            "design.personas",
            "design.info-arch",
            "design.interaction",
            "design.design-system",
            "design.visual-design",
        )
    )


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


def compute_task_outcome(stages: dict[str, dict], post_final_status: str) -> str:
    """Compute the honest task outcome based on stage results and post status.

    Returns one of: "done", "failed", "partial", "done_with_warnings".

    Logic:
    - If post stage failed, task is failed.
    - If any active stage has attempts > 0 but done == False, task is partial.
    - If all active stages done but some had retries (attempts >= 2), done_with_warnings.
    - Otherwise, done.
    """
    # Post is the final gate — if it failed, nothing is "done"
    post_stage = stages.get("post", {})
    if post_stage.get("done") and "failed" in str(post_stage.get("output", "")).lower():
        return "failed"

    if post_final_status == "failed":
        return "failed"

    # Check for active stages that were attempted but not completed
    active_failed = []
    for sid, s in stages.items():
        if s.get("attempts", 0) > 0 and not s.get("done"):
            active_failed.append(sid)

    if active_failed:
        return "partial"

    # Check for retried stages (warnings)
    retried = [sid for sid, s in stages.items() if s.get("done") and s.get("attempts", 0) >= 2]

    return "done_with_warnings" if retried else "done"


def load_state_template(template_path: str | Path) -> dict[str, Any]:
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def context_bus_snapshot(bus: Any) -> dict[str, Any]:
    """Serialize a ContextBus (or raw dict) to a JSON-safe snapshot."""
    if isinstance(bus, ContextBus):
        return bus.snapshot()
    if isinstance(bus, dict):
        return bus
    return {}


def restore_snapshot_data(data: dict[str, Any]) -> dict[str, Any]:
    """Merge raw snapshot data over make_initial_state defaults.

    Single source of truth for the key set: defaults come from
    make_initial_state, so new state keys can never be silently dropped on
    restore (the old hardcoded dict omitted context_bus, qa_results,
    user_interactions, recovery_* and task_outcome).
    """
    defaults = make_initial_state({}, {})
    for key in defaults:
        if key in data:
            defaults[key] = data[key]

    # Legacy key: still read from old snapshots, never written anymore.
    defaults["topology_proposal"] = data.get("topology_proposal")

    # JSON round-trip leaves context_bus as a raw dict — rehydrate it.
    bus = defaults.get("context_bus")
    if isinstance(bus, dict):
        defaults["context_bus"] = ContextBus.from_snapshot(bus)

    return defaults


def restore_snapshot(snapshot_path: str | Path) -> dict[str, Any]:
    """Load a historical state snapshot and restore it as a valid pipeline state.

    Merges missing fields with defaults so the restored state is compatible
    with the current PipelineState schema.
    """
    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return restore_snapshot_data(data)


# Stage descriptions for the architect's node catalog
STAGE_CATALOG: dict[str, dict[str, str]] = {
    "init": {"phase": "init", "description": "Validate work item, classify complexity, prepare loop"},
    "init.ideate": {"phase": "init", "description": "BMAD ideation with Party Mode"},
    "init.bdd": {"phase": "init", "description": "BDD journey mapping with Gherkin scenarios (large+)"},
    "init.refine": {"phase": "init", "description": "Refine work item into engineering spec"},
    "design.user-research": {"phase": "design", "description": "User research and requirements gathering (large+)"},
    "design.personas": {"phase": "design", "description": "Persona creation and analysis (large+)"},
    "design.info-arch": {"phase": "design", "description": "Information architecture (large+)"},
    "design.interaction": {"phase": "design", "description": "Interaction design (large+)"},
    "design.design-system": {"phase": "design", "description": "Design system definition (large+)"},
    "design.visual-design": {"phase": "design", "description": "Visual design and styling (large+)"},
    "arch.requirements": {"phase": "arch", "description": "Architecture requirements analysis (medium+)"},
    "arch.solution": {"phase": "arch", "description": "Architecture solution design (medium+)"},
    "arch.review": {"phase": "arch", "description": "Architecture review (complex)"},
    "impl.design": {"phase": "impl", "description": "Implementation blueprint creation"},
    "impl.code": {"phase": "impl", "description": "TDD code implementation"},
    "doc.update": {"phase": "impl", "description": "Update existing project documentation"},
    "verify": {"phase": "verify", "description": "Independent verification with discrimination sensor"},
    "qa.static": {"phase": "qa", "description": "Static analysis: lint, type-check, cyclomatic complexity"},
    "qa.unit": {"phase": "qa", "description": "Unit test generation and execution"},
    "qa.integration": {"phase": "qa", "description": "Integration: API contracts + component communication (medium+)"},
    "e2e.execute": {"phase": "verify", "description": "E2E Playwright testing (UI only)"},
    "qa.security": {"phase": "qa", "description": "Security audit (medium+)"},
    "qa.api-contract": {"phase": "qa", "description": "API contract validation (DEPRECATED, use qa.integration)"},
    "qa.performance": {"phase": "qa", "description": "Performance testing (complex)"},
    "qa.human.flow": {"phase": "qa", "description": "Persona-based heuristic navigation simulation (medium+)"},
    "qa.human.ux": {"phase": "qa", "description": "WCAG audit + cognitive walkthrough, UI only (medium+)"},
    "deploy.prepare": {"phase": "deploy", "description": "Build, lint, typecheck, env config, migration"},
    "smoke.test": {"phase": "deploy", "description": "Full user journey against production build (UI only)"},
    "doc.decisions": {"phase": "doc", "description": "Consolidate AD-NNN decisions into MADR format (medium+)"},
    "doc.project": {"phase": "doc", "description": "Generate project documentation: arc42 + C4 (medium+)"},
    "post": {"phase": "post", "description": "Finalize, lessons consolidation, commit"},
}

# Stages that are always mandatory for any valid graph
MANDATORY_ENTRY = "init"
MANDATORY_EXIT = "post"


def build_node_catalog_text() -> str:
    """Build a text description of available stages for the architect's context."""
    lines = []
    current_phase = ""
    for stage_id, info in STAGE_CATALOG.items():
        if info["phase"] != current_phase:
            current_phase = info["phase"]
            lines.append(f"\n  [{current_phase.upper()}]")
        min_c = STAGE_MIN_COMPLEXITY.get(stage_id, "small")
        lines.append(f"  {stage_id:30s} min_complexity={min_c:8s}  {info['description']}")
    return "\n".join(lines)

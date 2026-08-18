from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import EssenceOutput
from eng_loop.templates import load_skill
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.agent_tools import get_essence_tools

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class EssenceResult:
    """Result from running the essence gate before a stage."""

    passed: bool = False
    blocked: bool = False
    tension: str = ""
    adjustments: list[str] = None
    updated_state: dict[str, Any] | None = None

    def __post_init__(self):
        if self.adjustments is None:
            self.adjustments = []


def essence_gate(stage_id: str):
    """Decorator that runs the essence gate before a node handler.

    Usage:
        @essence_gate("impl.code")
        def impl_code_node(state: dict[str, Any]) -> Command[str]:
            ...

    The decorator extracts config and paths from state, runs the essence
    gate, and returns a blocked Command if Lens 4 tensions are found.
    """

    def decorator(fn: Callable[[dict[str, Any]], Command[str]]) -> Callable[[dict[str, Any]], Command[str]]:
        @wraps(fn)
        def wrapper(state: dict[str, Any]) -> Command[str]:
            config = state.get("config", {})
            paths = state.get("paths", {})
            stages = dict(state.get("stages", {}))

            essence = run_essence_gate(stage_id, state, paths, config)
            if essence.blocked:
                return Command(
                    update={
                        "status": "blocked",
                        "blocking_condition": f"Essence Lens 4 tension in {stage_id}: {essence.tension}",
                        "stages": stages,
                        "essence_tension": essence.tension,
                    },
                    goto="__end__",
                )
            if essence.updated_state and essence.updated_state.get("stages"):
                state["stages"] = essence.updated_state["stages"]

            return fn(state)

        return wrapper

    return decorator


def run_essence_gate(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, Any],
    config: dict[str, Any],
) -> EssenceResult:
    """Run the Four Lenses essence validation before stage execution.

    Checks config for essence.enabled, skips if already essence_checked.
    Invokes essence sub-agent with read-only tools. On Lens 1-3 findings,
    auto-adjusts and re-runs (bounded by max_essence_retries_per_stage).
    On Lens 4 conflicts, blocks and returns for user resolution.

    Returns:
        EssenceResult with passed/blocked status and any state updates.
    """
    essence_config = config.get("essence", {})
    if not essence_config.get("enabled", True):
        return EssenceResult(passed=True)

    stages = dict(state.get("stages", {}))
    stage_state = stages.get(stage_id, {})
    if stage_state.get("essence_checked", False):
        return EssenceResult(passed=True)

    skill_name = essence_config.get("skill", "essence")
    skill_root = paths.get("framework_skill_root", "")
    skill_content = load_skill(skill_root, skill_name)
    if not skill_content:
        logger.warning("Essence skill '%s' not found, skipping gate for %s", skill_name, stage_id)
        return EssenceResult(passed=True)

    max_retries = config.get("max_essence_retries_per_stage", 5)
    essence_retries = stage_state.get("essence_retries", 0)

    stage_inputs = _gather_essence_inputs(stage_id, state, paths)

    prompt = _build_essence_prompt(skill_content, stage_id, stage_inputs, state)

    model = create_model_from_config(config, "essence")
    tools = get_essence_tools(paths)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 15)

    for attempt in range(max_retries):
        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id=f"essence:{stage_id}",
            output_schema=EssenceOutput,
            max_iterations=max_agent_iterations,
            config=config,
        )

        if agent_result.error:
            logger.warning("Essence gate agent error for %s: %s", stage_id, agent_result.error)
            return EssenceResult(passed=True)

        result = agent_result.data
        is_clean = result.get("clean", False)
        lens_4 = result.get("lens_4_conflicts", [])
        adjustments = result.get("adjustments", [])

        if is_clean and not lens_4:
            return _mark_essence_checked(stage_id, stages, state)

        if lens_4:
            tensions = []
            for conflict in lens_4:
                if isinstance(conflict, dict):
                    tensions.append(conflict.get("tension", str(conflict)))
                else:
                    tensions.append(str(conflict))
            tension_str = "; ".join(tensions)
            capture_decision = essence_config.get("capture_decisions", True)
            context_file = essence_config.get("context_file", "context.md")

            if capture_decision and context_file:
                _capture_lens4_decision(stage_id, tensions, state, paths, context_file)

            return EssenceResult(
                blocked=True,
                tension=tension_str,
                updated_state={
                    "stages": stages,
                    "essence_blocked_stage": stage_id,
                    "essence_tension": tension_str,
                },
            )

        if adjustments:
            stage_inputs = _apply_adjustments(stage_inputs, adjustments)
            prompt = _build_essence_prompt(skill_content, stage_id, stage_inputs, state)
            logger.info(
                "Essence gate for %s: applied %d adjustments, re-running (attempt %d/%d)",
                stage_id,
                len(adjustments),
                attempt + 1,
                max_retries,
            )
            continue

        logger.info(
            "Essence gate for %s: no clean result, re-running (attempt %d/%d)",
            stage_id,
            attempt + 1,
            max_retries,
        )

    logger.warning("Essence gate for %s: exhausted %d retries, proceeding anyway", stage_id, max_retries)
    return _mark_essence_checked(stage_id, stages, state, retries_exceeded=True)


def _gather_essence_inputs(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, Any],
) -> str:
    """Gather stage-specific inputs for essence validation."""
    parts = []
    work_item = state.get("work_item", "")
    if work_item:
        parts.append(f"Work Item: {work_item}")

    stage_artifacts = state.get("stage_artifacts", {})
    if stage_artifacts:
        parts.append("Stage Artifacts:")
        for key, value in stage_artifacts.items():
            if value and isinstance(value, str) and len(value) > 1000:
                parts.append(f"  {key}: (exists, {len(value)} chars)")
            elif value:
                parts.append(f"  {key}: {value[:500]}")

    decisions = state.get("decisions", [])
    if decisions:
        parts.append(f"Decisions ({len(decisions)}):")
        for d in decisions[-10:]:
            parts.append(f"  - {d[:200]}")

    complexity = state.get("complexity", "unset")
    parts.append(f"Complexity: {complexity}")

    ui_project = state.get("ui_project", False)
    parts.append(f"UI Project: {ui_project}")

    return "\n\n".join(parts) if parts else "No inputs available."


def _build_essence_prompt(
    skill_content: str,
    stage_id: str,
    stage_inputs: str,
    state: dict[str, Any],
) -> str:
    """Build the essence validation prompt."""
    return (
        f"{skill_content}\n\n"
        f"## STAGE TO VALIDATE\n"
        f"Stage ID: {stage_id}\n\n"
        f"## STAGE INPUTS\n"
        f"{stage_inputs}\n\n"
        f"## INSTRUCTIONS\n"
        f"Apply the Four Lenses to these stage inputs for stage '{stage_id}'.\n"
        f"Are the inputs sufficient and unambiguous for the upcoming stage?\n"
        f"Return a JSON object with fields:\n"
        f"lens_1_subjective_terms, lens_2_hidden_assumptions, lens_3_literal_traps,\n"
        f"lens_4_conflicts, clean, adjustments, summary."
    )


def _apply_adjustments(stage_inputs: str, adjustments: list[str]) -> str:
    """Apply inline adjustments from Lens 1-3 findings."""
    adjusted = stage_inputs
    for adj in adjustments:
        adjusted += f"\n\n[Adjusted: {adj}]"
    return adjusted


def _mark_essence_checked(
    stage_id: str,
    stages: dict[str, Any],
    state: dict[str, Any],
    retries_exceeded: bool = False,
) -> EssenceResult:
    """Mark a stage as essence-checked and return the result."""
    if stage_id not in stages:
        stages[stage_id] = {}
    stages[stage_id]["essence_checked"] = True
    if retries_exceeded:
        stages[stage_id]["essence_retries_exceeded"] = True

    return EssenceResult(
        passed=True,
        updated_state={"stages": stages},
    )


def _capture_lens4_decision(
    stage_id: str,
    tensions: list[str],
    state: dict[str, Any],
    paths: dict[str, Any],
    context_file: str,
) -> None:
    """Capture Lens 4 tension decisions in context.md."""
    from pathlib import Path

    loop_root = paths.get("loop_root", ".")
    context_path = Path(loop_root) / context_file

    existing = ""
    if context_path.exists():
        existing = context_path.read_text(encoding="utf-8")

    decision_entries = []
    for tension in tensions:
        entry = (
            f"### Lens 4 Tension — {stage_id}\n"
            f"- **Tension**: {tension}\n"
            f"- **Date**: {__import__('datetime').date.today().isoformat()}\n"
            f"- **Stage**: {stage_id}\n"
            f"- **Resolution**: _awaiting user resolution_"
        )
        decision_entries.append(entry)

    new_section = "\n\n## Decisions\n\n" + "\n\n".join(decision_entries)

    if existing:
        content = existing.rstrip() + "\n\n" + "## Decisions\n\n" + "\n\n".join(decision_entries)
    else:
        slug = state.get("work_item", "feature")[:40].replace(" ", "-").lower()
        content = f"# Context — {slug}\n\n" + "## Decisions\n\n" + "\n\n".join(decision_entries)

    context_path.write_text(content, encoding="utf-8")
    logger.info("Captured Lens 4 decision in %s for stage %s", context_path, stage_id)

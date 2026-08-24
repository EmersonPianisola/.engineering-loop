from __future__ import annotations

import copy
import logging
from typing import Any

from eng_loop.schemas import Lesson, RecoveryPlan
from eng_loop.state import make_stage, rollback_to_stage, to_stage_id

logger = logging.getLogger(__name__)


def apply_recovery_plan(state: dict[str, Any], plan: RecoveryPlan) -> dict[str, Any]:
    """Apply a recovery plan to the pipeline state.

    1. Selective rollback of specified stages
    2. Inject lessons into state
    3. Inject fix prompt guidance
    4. Reset blocking condition and status for retry
    """
    new_state = copy.deepcopy(state)

    new_state = _selective_rollback(new_state, plan.stages_to_rollback)
    new_state = _inject_lessons(new_state, plan.lessons)
    new_state = _inject_fix_guidance(new_state, plan)

    new_state["blocking_condition"] = ""
    new_state["status"] = "running"

    return new_state


def _selective_rollback(state: dict[str, Any], stages_to_rollback: list[str]) -> dict[str, Any]:
    """Reset only the specified stages (not the full impl.code chain).

    Targets are normalized via to_stage_id (node names like "qa-security" are
    accepted). Unrecognized targets are logged and discarded. If NO target is
    valid, falls back to the standard impl.code -> current_stage chain
    rollback instead of a silent no-op.

    Respects the invariant: never reset BLOCKED or WAITING_FOR_INPUT stages.
    """
    if not stages_to_rollback:
        return state

    stages = state.get("stages", {})

    valid_ids: list[str] = []
    for name in stages_to_rollback:
        stage_id = to_stage_id(name)
        if stage_id is None:
            logger.warning("_selective_rollback: unrecognized stage %r — discarded", name)
            continue
        if stage_id not in valid_ids:
            valid_ids.append(stage_id)

    if not valid_ids:
        current = to_stage_id(state.get("current_stage", ""))
        if current is None:
            logger.warning(
                "_selective_rollback: no valid targets in %r and current stage %r not normalizable — no rollback",
                stages_to_rollback,
                state.get("current_stage"),
            )
            return state
        logger.warning(
            "_selective_rollback: no valid targets in %r — falling back to chain rollback (impl.code -> %s)",
            stages_to_rollback,
            current,
        )
        state["stages"] = rollback_to_stage(current_stages=stages, target_stage=current, reset_from="impl.code")
        return state

    for stage_id in valid_ids:
        if stage_id not in stages:
            continue

        existing = stages[stage_id]
        if existing.get("status") in ("blocked", "waiting_for_input"):
            continue

        fresh = make_stage()
        # Cumulative counter survives the reset — anti-loop guards
        # (contract gate) must still see an exhausted stage.
        fresh["total_attempts"] = existing.get("total_attempts", 0) + existing.get("attempts", 0)
        stages[stage_id] = fresh

    state["stages"] = stages

    fix_tasks = state.get("fix_tasks", [])
    if fix_tasks:
        known_sources = set(valid_ids) | set(stages_to_rollback)
        state["fix_tasks"] = [ft for ft in fix_tasks if ft.get("source") not in known_sources]

    return state


def _inject_lessons(state: dict[str, Any], lessons: list[Lesson]) -> dict[str, Any]:
    """Inject lessons into the pipeline state.

    Lessons are added to both the `lessons` list and `handoffs` for
    downstream stages to consume.
    """
    if not lessons:
        return state

    existing_lessons = state.get("lessons", [])
    if not isinstance(existing_lessons, list):
        existing_lessons = []

    new_lessons = []
    for lesson in lessons:
        lesson_text = f"[{lesson.category}] {lesson.pattern} -> {lesson.fix_strategy}"
        if lesson.context:
            lesson_text += f" (context: {lesson.context[:200]})"
        new_lessons.append(lesson_text)

    state["lessons"] = existing_lessons + new_lessons

    handoffs = state.get("handoffs", {})
    if not isinstance(handoffs, dict):
        handoffs = {}
        state["handoffs"] = handoffs

    recovery_context = []
    for lesson in lessons:
        recovery_context.append(f"- {lesson.fix_strategy}")

    if recovery_context:
        existing = handoffs.get("recovery_lessons", "")
        handoffs["recovery_lessons"] = (existing + "\n" if existing else "") + "\n".join(recovery_context)

    return state


def _inject_fix_guidance(state: dict[str, Any], plan: RecoveryPlan) -> dict[str, Any]:
    """Inject fix guidance into the current stage for retry.

    Adds recovery context to fix_tasks and handoffs so the next
    agent execution knows what went wrong and how to fix it.
    """
    current_stage = state.get("current_stage", "")
    if not current_stage:
        return state

    fix_tasks = state.get("fix_tasks", [])
    if not isinstance(fix_tasks, list):
        fix_tasks = []
        state["fix_tasks"] = fix_tasks

    if plan.fix_actions:
        fix_tasks.append(
            {
                "source": "recovery-agent",
                "gap": plan.root_cause[:500],
                "evidence": f"Error: {plan.error_category}",
                "severity": "critical",
                "suggested_fix": "; ".join(plan.fix_actions[:3]),
            }
        )
        state["fix_tasks"] = fix_tasks

    handoffs = state.get("handoffs", {})
    if not isinstance(handoffs, dict):
        handoffs = {}
        state["handoffs"] = handoffs

    if plan.fix_prompt_injection:
        handoffs["recovery_fix_prompt"] = plan.fix_prompt_injection

    return state

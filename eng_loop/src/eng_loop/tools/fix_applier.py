from __future__ import annotations

import copy
from typing import Any

from eng_loop.schemas import Lesson, RecoveryPlan
from eng_loop.state import make_stage


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

    Respects the invariant: never reset BLOCKED or WAITING_FOR_INPUT stages.
    """
    if not stages_to_rollback:
        return state

    stages = state.get("stages", {})
    for stage_id in stages_to_rollback:
        if stage_id not in stages:
            continue

        existing = stages[stage_id]
        if existing.get("status") in ("blocked", "waiting_for_input"):
            continue

        stages[stage_id] = make_stage()

    state["stages"] = stages

    fix_tasks = state.get("fix_tasks", [])
    if fix_tasks:
        stage_ids = set(stages_to_rollback)
        state["fix_tasks"] = [ft for ft in fix_tasks if ft.get("source") not in stage_ids]

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


def reset_stage_for_retry(state: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """Reset a single stage for retry, preserving completed downstream stages."""
    stages = state.get("stages", {})
    if stage_id in stages:
        stages[stage_id] = make_stage()
    state["stages"] = stages
    state["blocking_condition"] = ""
    state["status"] = "running"
    return state

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from eng_loop.model import create_model_from_config
from eng_loop.schemas import ErrorClassification, Lesson, RecoveryPlan

logger = logging.getLogger(__name__)

RECOVERY_SYSTEM_PROMPT = (
    "You are a pipeline recovery agent. Your job is to analyze pipeline failures, "
    "determine the root cause, and propose concrete fix actions.\n\n"
    "You receive: the error message, the stage that failed, the current pipeline state, "
    "and any previous recovery attempts.\n\n"
    "Respond with a structured RecoveryPlan containing:\n"
    "1. root_cause: The fundamental reason for the failure\n"
    "2. error_category: One of transient, infrastructure, schema, logic, contract, context_overflow\n"
    "3. fix_actions: Concrete, actionable steps to fix the issue\n"
    "4. stages_to_rollback: Which stages should be reset before retry\n"
    "5. lessons: Lessons learned to prevent this failure in the future\n"
    "6. confidence: Your confidence in the fix (0.0-1.0)\n"
    "7. fix_prompt_injection: Text to inject into the retry prompt to guide the agent\n\n"
    "Be specific and actionable. Avoid vague suggestions like 'fix the code' or 'try again'."
)


def analyze_and_propose(
    state: dict[str, Any],
    classification: ErrorClassification,
    config: dict[str, Any],
    previous_attempts: list[RecoveryPlan] | None = None,
) -> RecoveryPlan:
    """Invoke the LLM to analyze the error and propose a recovery plan.

    Args:
        state: Current pipeline state
        classification: Pre-classified error from error_classifier
        config: Pipeline config (for model settings)
        previous_attempts: Previous recovery plans that failed

    Returns:
        RecoveryPlan with root cause analysis and fix actions
    """
    error_message = state.get("blocking_condition", "")
    current_stage = state.get("current_stage", "")
    stages = state.get("stages", {})
    stage_data = stages.get(current_stage, {})

    context = _build_context(state, current_stage, stage_data, classification, previous_attempts)

    messages = [
        SystemMessage(content=RECOVERY_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]

    try:
        model = create_model_from_config(config, stage_id="recovery-agent")
        response = model.invoke(messages)
        content = _extract_content(response)
        plan = _parse_recovery_plan(content, classification)
        return plan
    except Exception as e:
        logger.warning("recovery_agent: LLM analysis failed — using fallback plan: %s", e)
        return _fallback_recovery_plan(classification, error_message, current_stage, str(e))


def _build_context(
    state: dict[str, Any],
    current_stage: str,
    stage_data: dict[str, Any],
    classification: ErrorClassification,
    previous_attempts: list[RecoveryPlan] | None = None,
) -> str:
    """Build the context string for the recovery agent prompt."""
    error_message = state.get("blocking_condition", "")
    work_item = state.get("work_item", "")
    complexity = state.get("complexity", "unset")
    work_type = state.get("work_type", "feature")

    context_parts = [
        (
            f"## Error\n"
            f"Stage: {current_stage}\n"
            f"Blocking condition: {error_message}\n"
            f"Classification: {classification.category} ({classification.suggested_strategy})\n"
            f"Severity: {classification.severity}\n"
        ),
    ]

    context_parts.append(
        f"## Work Context\nComplexity: {complexity}\nWork type: {work_type}\nWork item: {str(work_item)[:500]}\n"
    )

    stage_output = stage_data.get("output", "")
    if stage_output:
        context_parts.append(f"## Stage Output (truncated)\n{stage_output[:1000]}\n")

    stage_attempts = stage_data.get("attempts", 0)
    context_parts.append(f"## Stage Attempts\nAttempts: {stage_attempts}\n")

    completed_stages = [sid for sid, s in state.get("stages", {}).items() if s.get("done")]
    if completed_stages:
        context_parts.append(f"## Completed Stages\n{', '.join(completed_stages)}\n")

    existing_lessons = state.get("lessons", [])
    if existing_lessons:
        context_parts.append(f"## Existing Lessons\n{chr(10).join(str(l) for l in existing_lessons[:10])}\n")

    if previous_attempts:
        attempts_text = []
        for i, attempt in enumerate(previous_attempts, 1):
            attempts_text.append(
                f"Attempt {i}: root_cause={attempt.root_cause[:200]}, "
                f"fix_actions={attempt.fix_actions}, confidence={attempt.confidence}"
            )
        context_parts.append(f"## Previous Recovery Attempts (all failed)\n{chr(10).join(attempts_text)}\n")

    return "\n".join(context_parts)


def _extract_content(response: Any) -> str:
    """Extract text content from LLM response."""
    if hasattr(response, "content"):
        if isinstance(response.content, str):
            return response.content
        if isinstance(response.content, list):
            return " ".join(str(c) for c in response.content)
    return str(response)


def _parse_recovery_plan(content: str, classification: ErrorClassification) -> RecoveryPlan:
    """Parse LLM response into a RecoveryPlan.

    Tries JSON parsing first, then falls back to structured extraction.
    """
    import json as _json

    json_text = _extract_json_from_text(content)
    if json_text:
        try:
            data = _json.loads(json_text)
            plan = RecoveryPlan(**data)
            return plan
        except (ValidationError, TypeError, KeyError):
            pass

    return _parse_structured(content, classification)


def _extract_json_from_text(text: str) -> str | None:
    """Extract JSON object from text (handles markdown code blocks)."""
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    brace_start = text.find("{")
    if brace_start >= 0:
        return text[brace_start:]

    return None


def _parse_structured(content: str, classification: ErrorClassification) -> RecoveryPlan:
    """Fallback: extract fields from structured text response.

    Fields are collected in an explicit result dict so the parsed values
    actually reach the RecoveryPlan (the previous locals() snapshot was
    never written back to the function's locals).
    """
    import re as _re

    result: dict[str, Any] = {
        "root_cause": "",
        "error_category": classification.category,
        "fix_actions": [],
        "stages_to_rollback": [],
        "lessons": [],
        "confidence": 0.5,
        "fix_prompt_injection": "",
    }

    current_section = None
    section_lines: list[str] = []

    for line in content.split("\n"):
        section_match = _re.match(
            r"^(root_cause|fix_actions|stages_to_rollback|lessons|confidence|fix_prompt_injection)\s*[:=]\s*(.*)",
            line,
            _re.IGNORECASE,
        )
        if section_match:
            if current_section and section_lines:
                _process_section(current_section, section_lines, result)
            current_section = section_match.group(1).lower()
            section_lines = [section_match.group(2).strip()]
        elif current_section:
            section_lines.append(line)

    if current_section and section_lines:
        _process_section(current_section, section_lines, result)

    if not result["root_cause"]:
        result["root_cause"] = f"Unclassified {classification.category} error"
    if not result["fix_actions"]:
        result["fix_actions"] = [f"Retry with adjusted approach for {classification.category}"]

    return RecoveryPlan(**result)


def _process_section(section: str, lines: list[str], result: dict[str, Any]) -> None:
    """Process a parsed section and update the result dict in place."""
    if section == "root_cause":
        text = " ".join(lines).strip()
        if text:
            result["root_cause"] = text
    elif section in ("fix_actions", "stages_to_rollback"):
        items = [item.strip().lstrip("-*• ") for item in lines if item.strip().strip("-*• ")]
        if items:
            result[section] = items
    elif section == "confidence":
        text = " ".join(lines).strip()
        try:
            result["confidence"] = float(text)
        except ValueError:
            pass
    elif section == "fix_prompt_injection":
        text = " ".join(lines).strip()
        if text:
            result["fix_prompt_injection"] = text
    elif section == "lessons":
        for item in (line.strip().lstrip("-*• ") for line in lines if line.strip().strip("-*• ")):
            result["lessons"].append(
                Lesson(
                    lesson_id=f"lesson_{uuid.uuid4().hex[:6]}",
                    category="",
                    pattern=item[:200],
                    fix_strategy="",
                    context="",
                    confirmed=False,
                )
            )


def _fallback_recovery_plan(
    classification: ErrorClassification,
    error_message: str,
    stage_id: str,
    llm_error: str,
) -> RecoveryPlan:
    """Generate a basic recovery plan when LLM analysis fails."""
    return RecoveryPlan(
        root_cause=f"LLM recovery analysis failed: {llm_error[:200]}",
        error_category=classification.category,
        fix_actions=[f"Retry {stage_id} with error context: {error_message[:200]}"],
        stages_to_rollback=[stage_id] if stage_id else [],
        lessons=[],
        confidence=0.3,
        fix_prompt_injection=f"Previous error: {error_message[:300]}. Try a different approach.",
    )


def generate_lessons(
    state: dict[str, Any],
    classification: ErrorClassification,
    plan: RecoveryPlan,
    success: bool,
) -> list[Lesson]:
    """Generate lessons from a recovery attempt.

    If the recovery succeeded, marks lessons as confirmed.
    If it failed, generates a lesson about what didn't work.
    """
    error_message = state.get("blocking_condition", "")
    current_stage = state.get("current_stage", "")
    lessons = []
    for lesson in plan.lessons:
        lessons.append(
            lesson.model_copy(
                update={
                    "confirmed": success,
                    "times_applied": 1 if success else 0,
                }
            )
        )

    if not lessons and not success:
        lesson_id = f"lesson_{uuid.uuid4().hex[:6]}"
        lessons.append(
            Lesson(
                lesson_id=lesson_id,
                category=classification.category,
                pattern=f"{current_stage}: {error_message[:200]}",
                fix_strategy=plan.root_cause[:200] if plan.root_cause else "Unknown",
                context=f"Attempted fix: {plan.fix_actions[:2] if plan.fix_actions else []}",
                confirmed=False,
            )
        )

    return lessons

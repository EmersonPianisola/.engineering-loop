from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


MIN_OUTPUT_LENGTH = 50
MIN_VERIFICATION_EVIDENCE = 1
MIN_BLUEPRINT_LENGTH = 20
MIN_IMPLEMENTATION_LENGTH = 50


def validate_stage_output(stage_id: str, result: dict[str, Any], content: str) -> tuple[bool, str]:
    """Validate that a stage's output meets minimum quality criteria.

    Returns (is_valid, error_message).
    If is_valid is False, the stage should NOT be marked as done.
    """
    # Check that we got structured data
    if not result:
        return False, "Empty result from LLM"

    # Stage-specific validations
    if stage_id == "verify":
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL"):
            return False, f"Invalid verdict: {verdict!r}"
        if verdict == "FAIL":
            gaps = result.get("gaps", [])
            if not gaps:
                return False, "Verdict is FAIL but no gaps provided"

    elif stage_id == "e2e.execute" or stage_id.startswith("qa."):
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL", "BLOCKED"):
            return False, f"Invalid verdict: {verdict!r}"

    elif stage_id == "impl.design":
        blueprint = result.get("blueprint", "")
        tasks = result.get("tasks", [])
        if not tasks:
            return False, "Blueprint has no tasks"
        # If tasks exist, accept even with short blueprint (content may be in task descriptions)
        if len(blueprint) < MIN_BLUEPRINT_LENGTH and len(tasks) < 2:
            return False, f"Blueprint too short ({len(blueprint)} chars, min {MIN_BLUEPRINT_LENGTH})"

    elif stage_id == "impl.code":
        summary = result.get("implementation_summary", "")
        if len(summary) < MIN_IMPLEMENTATION_LENGTH:
            return False, f"Implementation summary too short ({len(summary)} chars)"
        files = result.get("files_created", [])
        if not files:
            logger.warning("impl.code: no files_created reported")

    elif stage_id == "init":
        valid = result.get("valid", False)
        refined = result.get("work_item_refined", "")
        if not valid and not refined:
            return False, "Init: work item not valid and no refinement provided"

    elif stage_id == "init.ideate":
        tasks = result.get("decomposed_tasks", [])
        ideation = result.get("ideation_results", "")
        raw_output = result.get("raw_output", "")
        # Accept if we have tasks, substantial ideation, or any meaningful content from fallback
        has_content = tasks or len(ideation) >= MIN_OUTPUT_LENGTH or len(raw_output) >= MIN_OUTPUT_LENGTH
        if not has_content:
            return False, "Ideation produced no tasks and minimal output"

    elif stage_id == "deploy.prepare" or stage_id == "smoke.test":
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL"):
            return False, f"Invalid verdict: {verdict!r}"

    # Generic: check that we have some meaningful output
    output_str = str(result)
    if len(output_str) < MIN_OUTPUT_LENGTH:
        # Allow short output for simple stages
        if stage_id not in ("doc.update", "init.refine"):
            logger.warning("Stage %s output very short: %d chars", stage_id, len(output_str))

    return True, ""

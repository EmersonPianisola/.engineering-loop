from __future__ import annotations

import logging
from typing import Any

from eng_loop.schemas import get_schema
from eng_loop.tools.json_parse import extract_json

logger = logging.getLogger(__name__)


MIN_OUTPUT_LENGTH = 50
MIN_VERIFICATION_EVIDENCE = 1
MIN_BLUEPRINT_LENGTH = 100
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
    
    elif stage_id == "e2e.execute":
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL"):
            return False, f"Invalid verdict: {verdict!r}"
    
    elif stage_id.startswith("qa."):
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL"):
            return False, f"Invalid verdict: {verdict!r}"
    
    elif stage_id == "impl.design":
        blueprint = result.get("blueprint", "")
        if len(blueprint) < MIN_BLUEPRINT_LENGTH:
            return False, f"Blueprint too short ({len(blueprint)} chars, min {MIN_BLUEPRINT_LENGTH})"
        tasks = result.get("tasks", [])
        if not tasks:
            return False, "Blueprint has no tasks"
    
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
        if not tasks and len(ideation) < MIN_OUTPUT_LENGTH:
            return False, "Ideation produced no tasks and minimal output"
    
    elif stage_id == "deploy.prepare":
        verdict = result.get("verdict", "")
        if verdict not in ("PASS", "FAIL"):
            return False, f"Invalid verdict: {verdict!r}"
    
    elif stage_id == "smoke.test":
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


def parse_llm_response(stage_id: str, content: str) -> tuple[dict[str, Any], str]:
    """Parse LLM response using structured output or JSON extraction.
    
    Returns (result_dict, error_message).
    If error_message is non-empty, the parse failed.
    """
    schema = get_schema(stage_id)
    
    # Try schema-based extraction first if we have a model that supports it
    # This is handled by the caller using llm.with_structured_output()
    # Here we handle the fallback case
    
    try:
        result = extract_json(content)
        return result, ""
    except (ValueError, KeyError) as e:
        error_msg = f"JSON parse failed for {stage_id}: {e}"
        logger.error(error_msg)
        return {}, error_msg


def should_retry_stage(stage_id: str, result: dict[str, Any], error: str, attempts: int, max_attempts: int) -> bool:
    """Determine if a stage should be retried based on output quality.
    
    Returns True if the stage should be retried.
    """
    if not error:
        return False
    if attempts >= max_attempts:
        return False
    return True

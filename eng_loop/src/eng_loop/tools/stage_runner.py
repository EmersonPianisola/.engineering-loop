from __future__ import annotations

import json
import logging
import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import get_schema
from eng_loop.tools.evidence_gate import validate_stage_output, parse_llm_response
from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.progress import log_model_invoke, log_model_done, log_stage_done, log_stage_fail

logger = logging.getLogger(__name__)


def execute_stage(
    state: dict[str, Any],
    stage_id: str,
    prompt: str,
    next_node: str,
    *,
    artifact_key: str = "",
    artifact_dir: str = "",
    artifact_filename: str = "",
    record_decisions: bool = True,
    verdict_field: str = "verdict",
    fail_reset_stage: str = "",
) -> dict[str, Any]:
    """Execute a single stage with structured output, evidence gate, and proper error handling.
    
    Returns a dict with keys: goto, update (to be used in Command).
    """
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    
    # Skip if already done
    if stages.get(stage_id, {}).get("done", False):
        return {"goto": next_node, "update": {"stages": stages, "current_stage": next_node}}
    
    # Check attempt limit
    max_attempts = config.get("constraints", {}).get(
        f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
    )
    
    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        log_stage_fail(stage_id, "non-convergence")
        return {
            "goto": "__end__",
            "update": {
                "stages": stages,
                "status": "blocked",
                "blocking_condition": f"{stage_id} non-convergence",
            },
        }
    
    # Invoke model
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()
    
    schema = get_schema(stage_id)
    
    try:
        if schema:
            # Use structured output
            structured_model = model.with_structured_output(schema)
            response = structured_model.invoke([{"role": "user", "content": prompt}])
            if hasattr(response, "model_dump"):
                result = response.model_dump()
            elif hasattr(response, "dict"):
                result = response.dict()
            else:
                result = dict(response)
        else:
            # Fallback to JSON extraction
            response = model.invoke([{"role": "user", "content": prompt}])
            content = response.content.strip()
            result = extract_json(content)
    except Exception as e:
        logger.error("Stage %s LLM invocation failed: %s", stage_id, e)
        elapsed = time.monotonic() - t0
        log_model_done(stage_id, elapsed)
        
        # Retry if possible
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "goto": stage_id.replace(".", "-").replace("_", "-"),
                "update": {
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} LLM error: {e}"],
                    "current_stage": stage_id,
                },
            }
        
        # Max attempts reached, block
        stages[stage_id]["done"] = True
        return {
            "goto": "__end__",
            "update": {
                "stages": stages,
                "status": "blocked",
                "blocking_condition": f"{stage_id} LLM error after {max_attempts} attempts",
            },
        }
    
    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)
    
    # Evidence gate: validate output quality
    is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
    
    if not is_valid:
        logger.warning("Stage %s failed evidence gate: %s", stage_id, error_msg)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "goto": stage_id.replace(".", "-").replace("_", "-"),
                "update": {
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} evidence gate: {error_msg}"],
                    "current_stage": stage_id,
                },
            }
        
        # Max attempts, force proceed with warning
        logger.error("Stage %s failed evidence gate after %d attempts, proceeding", stage_id, max_attempts)
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = str(result)
        return {
            "goto": next_node,
            "update": {
                "stages": stages,
                "current_stage": next_node,
                "iteration": state.get("iteration", 0) + 1,
            },
        }
    
    # Check verdict-based routing (for verify/qa/deploy stages)
    verdict = result.get(verdict_field, "PASS")
    
    if verdict == "FAIL":
        gaps = result.get("gaps", result.get("errors", result.get("critical_findings", [])))
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        
        # Reset upstream stage if configured
        if fail_reset_stage:
            stages[fail_reset_stage]["done"] = False
            stages[stage_id]["done"] = False
        
        return {
            "goto": fail_reset_stage.replace(".", "-").replace("_", "-") if fail_reset_stage else next_node,
            "update": {
                "stages": stages,
                "current_stage": fail_reset_stage if fail_reset_stage else next_node,
                "errors": list(state.get("errors", [])) + [f"{stage_id} FAIL: {gaps}"],
                "iteration": state.get("iteration", 0) + 1,
            },
        }
    
    # Success: mark done
    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    
    # Write artifact if configured
    if artifact_filename and artifact_dir:
        from eng_loop.tools.file_ops import write_file
        artifact_content = result.get(artifact_key, str(result))
        artifact_root = paths.get("artifact_root", "")
        artifact_path = f"{artifact_root}/{artifact_dir}/{artifact_filename}"
        write_file(artifact_path, artifact_content)
        log_artifact(stage_id, artifact_path)
    
    # Record decisions
    update = {
        "stages": stages,
        "current_stage": next_node,
        "iteration": state.get("iteration", 0) + 1,
    }
    
    if record_decisions:
        new_decisions = list(state.get("decisions", []))
        for d in result.get("decisions", []):
            from eng_loop.tools.decisions import record_decision
            record_decision({"decisions": new_decisions}, d)
        update["decisions"] = new_decisions
    
    log_stage_done(stage_id, str(result.get("summary", result.get("complete", "done")))[:120])
    
    return {
        "goto": next_node,
        "update": update,
    }


def log_artifact(stage_id: str, path: str) -> None:
    from eng_loop.tools.progress import log_artifact as _log_artifact
    _log_artifact(stage_id, path)

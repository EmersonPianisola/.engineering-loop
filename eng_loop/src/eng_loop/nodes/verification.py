from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import E2eOutput, VerifyOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


def verify_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "verify"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto=_post_verify(state), update={"current_stage": _post_verify(state), "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_verify_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
            goto="__end__",
        )

    stage_file = get_stage_file(stage_id)
    skill_name = get_skill_name(stage_id)

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
    skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

    blueprint = state.get("stage_artifacts", {}).get("impl.design", "")
    diff = state.get("stage_artifacts", {}).get("diff", "")

    prompt = f"""You are the Independent Verifier. Author != Verifier. Perform spec-anchored check, discrimination sensor, and coverage audit.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## BLUEPRINT
{blueprint}

## DIFF
{diff}

## WORK ITEM
{state.get('work_item', '')}

Execute verification:
1. Spec-anchored check — each AC traced to file:line evidence
2. Discrimination sensor — inject behavior-level faults, confirm tests kill them
3. Coverage audit — ACs vs test coverage

Return a JSON object with these fields: verdict (PASS or FAIL), per_ac_evidence, discrimination_sensor, coverage_audit, gaps, complete.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(VerifyOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        log_model_done(stage_id, time.monotonic() - t0)
        log_stage_fail(stage_id, f"LLM error: {e}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} LLM error: {e}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="verify",
            )
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} LLM error"},
            goto="__end__",
        )

    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)

    # Evidence gate
    is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
    if not is_valid:
        log_stage_fail(stage_id, f"evidence gate: {error_msg}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} evidence: {error_msg}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="verify",
            )

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    write_file(f"{artifact_root}/validation.md", str(result))
    log_artifact(stage_id, f"{artifact_root}/validation.md")

    if verdict == "FAIL":
        gaps = result.get("gaps", [])
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = False
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        log_stage_fail(stage_id, f"FAIL: {gaps}")
        return Command(
            update={
                "stages": stages,
                "current_stage": "impl-code",
                "errors": list(state.get("errors", [])) + [f"Verify FAIL: {gaps}"],
                "iteration": state.get("iteration", 0) + 1,
            },
            goto="impl-code",
        )

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    log_stage_done(stage_id, "PASS")

    next_node = _post_verify(state)
    return Command(
        update={
            "stages": stages,
            "current_stage": next_node,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=next_node,
    )


def e2e_execute_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "e2e.execute"

    if stages.get(stage_id, {}).get("done", False):
        next_node = _post_e2e(state)
        return Command(goto=next_node, update={"current_stage": next_node, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_e2e_execute_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code", "iteration": state.get("iteration", 0) + 1},
            goto="impl-code",
        )

    stage_file = get_stage_file(stage_id)
    skill_name = get_skill_name(stage_id)

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
    skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

    prompt = f"""You are the E2E Playwright Testing agent. Execute browser E2E testing with 4-layer assertions.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## BLUEPRINT
{state.get('stage_artifacts', {}).get('impl.design', '')}

Execute:
1. Infrastructure setup — Playwright, config, Page Objects
2. Auth bypass detection + wiring
3. Scenario derivation from BDD @e2e tags
4. Four-layer assertions: DOM, Dimension, Console, Network
5. Screenshot evidence capture
6. BDD->E2E 1:1 coverage check

Return a JSON object with these fields: verdict (PASS or FAIL), test_results, console_errors, network_errors, bdd_coverage, complete.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(E2eOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        log_model_done(stage_id, time.monotonic() - t0)
        log_stage_fail(stage_id, f"LLM error: {e}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} LLM error: {e}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="e2e-execute",
            )
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code", "iteration": state.get("iteration", 0) + 1},
            goto="impl-code",
        )

    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)

    # Evidence gate
    is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
    if not is_valid:
        log_stage_fail(stage_id, f"evidence gate: {error_msg}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} evidence: {error_msg}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="e2e-execute",
            )

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    write_file(f"{artifact_root}/e2e-report.md", str(result))
    log_artifact(stage_id, f"{artifact_root}/e2e-report.md")

    if verdict == "FAIL":
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = False
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        log_stage_fail(stage_id, "FAIL")
        return Command(
            update={"stages": stages, "current_stage": "impl-code", "iteration": state.get("iteration", 0) + 1},
            goto="impl-code",
        )

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    log_stage_done(stage_id, "PASS")

    next_node = _post_e2e(state)
    return Command(
        update={
            "stages": stages,
            "current_stage": next_node,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=next_node,
    )


def _post_verify(state: dict[str, Any]) -> str:
    ui_project = state.get("ui_project", False)
    complexity = state.get("complexity", "small")
    if ui_project:
        return "e2e-execute"
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "deploy-prepare"


def _post_e2e(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "deploy-prepare"

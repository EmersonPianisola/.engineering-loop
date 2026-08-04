from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DeployPrepareOutput, SmokeTestOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


def deploy_prepare_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "deploy.prepare"

    if stages.get(stage_id, {}).get("done", False):
        next_node = _post_deploy(state)
        return Command(goto=next_node, update={"current_stage": next_node, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_deploy_prepare_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code", "iteration": state.get("iteration", 0) + 1},
            goto="impl-code",
        )

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    prompt = f"""You are the Deploy Preparation agent. Execute build, lint, type check, env config, migration verification.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## DIFF
{state.get('stage_artifacts', {}).get('diff', '')}

Execute deployment preparation checks.
Return a JSON object with these fields: build_status, lint_status, type_check_status, verdict (PASS or FAIL), errors, complete.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(DeployPrepareOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        elapsed = time.monotonic() - t0
        log_model_done(stage_id, elapsed)
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
                goto="deploy-prepare",
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
                goto="deploy-prepare",
            )

    verdict = result.get("verdict", "PASS")

    if verdict == "FAIL":
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = False
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        log_stage_fail(stage_id, f"FAIL: {result.get('errors', [])}")
        return Command(
            update={
                "stages": stages,
                "current_stage": "impl-code",
                "errors": list(state.get("errors", [])) + [f"deploy.prepare FAIL: {result.get('errors', [])}"],
                "iteration": state.get("iteration", 0) + 1,
            },
            goto="impl-code",
        )

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    log_stage_done(stage_id, "PASS")

    next_node = _post_deploy(state)
    return Command(
        update={
            "stages": stages,
            "current_stage": next_node,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=next_node,
    )


def smoke_test_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "smoke.test"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="doc-decisions", update={"current_stage": "doc-decisions", "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_smoke_test_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code", "iteration": state.get("iteration", 0) + 1},
            goto="impl-code",
        )

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    prompt = f"""You are the Smoke Test agent. Execute full user journey against production build.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

Execute:
1. Build production binary
2. Define critical paths (login, navigation, CRUD, reports, logout)
3. Run full user journey against production build
4. Screenshot at each step
5. Console + network error monitoring

Return a JSON object with these fields: verdict (PASS or FAIL), critical_paths, console_errors, network_errors, complete.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(SmokeTestOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        elapsed = time.monotonic() - t0
        log_model_done(stage_id, elapsed)
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
                goto="smoke-test",
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
                goto="smoke-test",
            )

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    write_file(f"{artifact_root}/smoke-report.md", str(result))
    log_artifact(stage_id, f"{artifact_root}/smoke-report.md")

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

    return Command(
        update={
            "stages": stages,
            "current_stage": "doc-decisions",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="doc-decisions",
    )


def _post_deploy(state: dict[str, Any]) -> str:
    ui_project = state.get("ui_project", False)
    complexity = state.get("complexity", "small")

    if ui_project:
        return "smoke-test"

    if complexity in ("medium", "large", "complex"):
        return "doc-decisions"
    return "post"

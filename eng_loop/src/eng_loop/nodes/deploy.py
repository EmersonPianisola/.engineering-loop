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
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

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

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Read build config files (package.json, pyproject.toml, Makefile, etc.)
2. Run build with bash: npm run build, poetry build, make build, etc.
3. Run lint with bash: npm run lint, ruff check, etc.
4. Run type check with bash: npm run typecheck, mypy, etc.
5. Run final test suite with bash
6. Verify env config and migrations

Return a JSON object with these fields: build_status, lint_status, type_check_status, verdict (PASS or FAIL), errors, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=DeployPrepareOutput,
        max_iterations=max_agent_iterations,
    )

    result = agent_result.data

    if agent_result.error:
        log_stage_fail(stage_id, agent_result.error)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
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
    log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

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
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

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

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Build production binary with bash
2. Write smoke test scripts
3. Run tests against production build
4. Capture console and network errors
5. Save report to {paths.get('artifact_root', '')}/smoke-report.md

Execute:
1. Build production binary
2. Define critical paths (login, navigation, CRUD, reports, logout)
3. Run full user journey against production build
4. Screenshot at each step
5. Console + network error monitoring

Return a JSON object with these fields: verdict (PASS or FAIL), critical_paths, console_errors, network_errors, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=SmokeTestOutput,
        max_iterations=max_agent_iterations,
    )

    result = agent_result.data

    if agent_result.error:
        log_stage_fail(stage_id, agent_result.error)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
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
    log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

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

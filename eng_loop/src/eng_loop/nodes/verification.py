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
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

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

## PROJECT ROOT
{paths.get('project_root', '.')}

Execute verification using your tools:
1. Read the source code files to understand what was implemented
2. Spec-anchored check — trace each AC to file:line evidence by reading actual files
3. Run tests with bash to confirm they pass
4. Discrimination sensor — use grep to find test assertions, verify they cover the right behavior
5. Coverage audit — compare ACs against test file contents
6. Write validation report to {paths.get('artifact_root', '')}/validation.md

Use read, bash, grep, and glob tools to examine actual code and run tests.
Do NOT guess — read the files and run the tests.

Return a JSON object with these fields: verdict (PASS or FAIL), per_ac_evidence, discrimination_sensor, coverage_audit, gaps, complete.
"""
    model = create_model_from_config(config, stage_id)

    # Get tools for this stage
    tools = get_tools_for_stage(stage_id, paths, config)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=VerifyOutput,
        max_iterations=max_agent_iterations,
        config=config,
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
                goto="verify",
            )
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} agent error"},
            goto="__end__",
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
    log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

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
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

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

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Read existing test files and page objects with read/glob
2. Write/update E2E test files with write/edit
3. Run tests with bash: npx playwright test or equivalent
4. Capture console and network errors from test output
5. Verify BDD→E2E 1:1 coverage using grep to find @e2e tags

Execute:
1. Infrastructure setup — Playwright, config, Page Objects
2. Auth bypass detection + wiring
3. Scenario derivation from BDD @e2e tags
4. Four-layer assertions: DOM, Dimension, Console, Network
5. Screenshot evidence capture
6. BDD→E2E 1:1 coverage check

Save the report to {paths.get('artifact_root', '')}/e2e-report.md

Return a JSON object with these fields: verdict (PASS or FAIL), test_results, console_errors, network_errors, bdd_coverage, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=E2eOutput,
        max_iterations=max_agent_iterations,
        config=config,
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
                goto="e2e-execute",
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
    log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

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

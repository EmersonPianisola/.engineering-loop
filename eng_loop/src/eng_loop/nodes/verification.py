from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import E2eOutput, VerifyOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.node_helpers import build_node_prompt, build_handoff_update
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

    prompt = build_node_prompt(
        stage_id, state, paths, config,
        role_description="Independent Verifier. Author != Verifier.",
        instructions=(
            "Perform spec-anchored check, discrimination sensor, and coverage audit.\n\n"
            "Execute verification using your tools:\n"
            "1. **graphify_explain** entities being verified — understand structure before reading\n"
            "2. **graphify_path** to trace data flows between components\n"
            "3. Read source code files to understand what was implemented (only after graphify context)\n"
            "4. Spec-anchored check — trace each AC to file:line evidence by reading actual files\n"
            "5. Run tests with bash to confirm they pass\n"
            "6. Discrimination sensor — use grep to find test assertions, verify they cover the right behavior\n"
            "7. Coverage audit — compare ACs against test file contents\n"
            f"8. Write validation report to {paths.get('artifact_root', '')}/validation.md\n\n"
            "Use graphify_explain/graphify_path FIRST, then read, bash, grep, and glob tools to examine actual code and run tests.\n"
            "Do NOT guess — read the files and run the tests.\n\n"
            "Return a JSON object with these fields: verdict (PASS or FAIL), per_ac_evidence, discrimination_sensor, coverage_audit, gaps, complete."
        ),
    )
    model = create_model_from_config(config, stage_id)

    # Get tools for this stage
    tools = get_tools_for_stage(stage_id, paths, config, state)
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

    handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
    next_node = _post_verify(state)
    return Command(
        update={
            "stages": stages,
            **handoff_update,
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

    prompt = build_node_prompt(
        stage_id, state, paths, config,
        role_description="E2E Playwright Testing agent",
        instructions=(
            "Execute browser E2E testing with 4-layer assertions.\n\n"
            "Use your tools to:\n"
            "1. Read existing test files and page objects with read/glob\n"
            "2. Write/update E2E test files with write/edit\n"
            "3. Run tests with bash: npx playwright test or equivalent\n"
            "4. Capture console and network errors from test output\n"
            "5. Verify BDD→E2E 1:1 coverage using grep to find @e2e tags\n\n"
            "Execute:\n"
            "1. Infrastructure setup — Playwright, config, Page Objects\n"
            "2. Auth bypass detection + wiring\n"
            "3. Scenario derivation from BDD @e2e tags\n"
            "4. Four-layer assertions: DOM, Dimension, Console, Network\n"
            "5. Screenshot evidence capture\n"
            "6. BDD→E2E 1:1 coverage check\n\n"
            f"Save the report to {paths.get('artifact_root', '')}/e2e-report.md\n\n"
            "Return a JSON object with these fields: verdict (PASS or FAIL), test_results, console_errors, network_errors, bdd_coverage, complete."
        ),
    )
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
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

    handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
    next_node = _post_e2e(state)
    return Command(
        update={
            "stages": stages,
            **handoff_update,
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

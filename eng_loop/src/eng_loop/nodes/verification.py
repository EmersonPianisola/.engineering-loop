from __future__ import annotations

import json
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import E2eOutput, VerifyOutput
from eng_loop.state import rollback_to_stage
from eng_loop.tools.essence_gate import essence_gate
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.node_helpers import build_handoff_update, build_node_prompt
from eng_loop.tools.progress import (
    log_artifact,
    log_stage_done,
    log_stage_fail,
)


def _build_fix_tasks(
    source: str,
    gaps: list[str],
    evidence: list[str],
) -> list[dict[str, Any]]:
    """Map verifier gaps into structured FixTask objects."""
    if isinstance(evidence, dict):
        evidence = list(evidence.values())
    fix_tasks = []
    for i, gap in enumerate(gaps):
        ev = evidence[i] if i < len(evidence) else ""
        fix_tasks.append(
            {
                "source": source,
                "gap": gap,
                "evidence": ev,
                "severity": "critical",
                "suggested_fix": "",
            }
        )
    return fix_tasks


@essence_gate("verify")
def verify_node(state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "verify"

    if stages.get(stage_id, {}).get("done", False):
        return {}

    max_attempts = config.get("constraints", {}).get("max_verify_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return {
            "stages": stages,
            "status": "blocked",
            "blocking_condition": f"{stage_id} non-convergence",
        }

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="Independent Verifier. Author != Verifier.",
        instructions=(
            "Perform spec-anchored check, discrimination sensor, and coverage audit.\n\n"
            "Execute verification using your tools:\n"
            "1. **graphify_explain** entities being verified\n"
            "2. **graphify_path** to trace data flows\n"
            "3. Read source code files to understand what was implemented\n"
            "4. Spec-anchored check — trace each AC to file:line evidence\n"
            "5. Run tests with bash to confirm they pass\n"
            "6. Discrimination sensor — verify tests cover the right behavior\n"
            "7. Coverage audit — compare ACs against test file contents\n"
            f"8. Write validation report to {paths.get('artifact_root', '')}/validation.md\n\n"
            "Return a JSON object with these fields: verdict (PASS or FAIL), per_ac_evidence, discrimination_sensor, coverage_audit, gaps, complete."
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
        output_schema=VerifyOutput,
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    if agent_result.error:
        log_stage_fail(stage_id, agent_result.error)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
            }
        stages[stage_id]["done"] = True
        return {
            "stages": stages,
            "status": "blocked",
            "blocking_condition": f"{stage_id} agent error",
        }

    is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
    if not is_valid:
        log_stage_fail(stage_id, f"evidence gate: {error_msg}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} evidence: {error_msg}"],
            }

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file

    write_file(f"{artifact_root}/validation.md", json.dumps(result, indent=2, default=str))
    log_artifact(stage_id, f"{artifact_root}/validation.md")

    if verdict == "FAIL":
        gaps = result.get("gaps", [])
        per_ac_evidence = result.get("per_ac_evidence", [])

        fix_tasks = _build_fix_tasks("verify", gaps, per_ac_evidence)

        reset_stages = rollback_to_stage(
            current_stages=stages,
            target_stage="verify",
            reset_from="impl.code",
        )

        fix_iteration = state.get("fix_iteration", 0) + 1
        log_stage_fail(stage_id, f"FAIL ({fix_iteration}): {len(gaps)} gaps")

        return {
            "stages": reset_stages,
            "rollback_target": "impl.code",
            "fix_tasks": fix_tasks,
            "fix_iteration": fix_iteration,
            "errors": list(state.get("errors", [])) + [f"Verify FAIL (iteration {fix_iteration}): {gaps}"],
        }

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

    handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
    return {
        "stages": stages,
        **handoff_update,
    }


@essence_gate("e2e.execute")
def e2e_execute_node(state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "e2e.execute"

    if stages.get(stage_id, {}).get("done", False):
        return {}

    max_attempts = config.get("constraints", {}).get("max_e2e_execute_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        fix_tasks = _build_fix_tasks(
            "e2e.execute",
            ["E2E tests exhausted max attempts"],
            [],
        )
        reset_stages = rollback_to_stage(stages, "e2e.execute", "impl.code")
        return {
            "stages": reset_stages,
            "rollback_target": "impl.code",
            "fix_tasks": fix_tasks,
            "fix_iteration": state.get("fix_iteration", 0) + 1,
        }

    # Pre-flight: verify Playwright can launch before expensive agent run
    _e2e_error = _check_e2e_prerequisites(paths)
    if _e2e_error:
        log_stage_fail(stage_id, f"pre-flight: {_e2e_error}")
        stages[stage_id]["done"] = True
        return {
            "stages": stages,
            "status": "blocked",
            "blocking_condition": f"{stage_id} pre-flight failed: {_e2e_error}",
        }

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="E2E Playwright Testing agent",
        instructions=(
            "Execute browser E2E testing with 4-layer assertions.\n\n"
            "Use your tools to read/write test files and run tests.\n\n"
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
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
            }
        fix_tasks = _build_fix_tasks("e2e.execute", [f"E2E agent error: {agent_result.error}"], [])
        reset_stages = rollback_to_stage(stages, "e2e.execute", "impl.code")
        return {
            "stages": reset_stages,
            "rollback_target": "impl.code",
            "fix_tasks": fix_tasks,
            "fix_iteration": state.get("fix_iteration", 0) + 1,
        }

    is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
    if not is_valid:
        log_stage_fail(stage_id, f"evidence gate: {error_msg}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} evidence: {error_msg}"],
            }

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file

    write_file(f"{artifact_root}/e2e-report.md", json.dumps(result, indent=2, default=str))
    log_artifact(stage_id, f"{artifact_root}/e2e-report.md")

    if verdict == "FAIL":
        test_results = result.get("test_results", [])
        fix_tasks = _build_fix_tasks("e2e.execute", test_results, [])

        reset_stages = rollback_to_stage(stages, "e2e.execute", "impl.code")
        log_stage_fail(stage_id, f"FAIL: {len(test_results)} test failures")
        return {
            "stages": reset_stages,
            "rollback_target": "impl.code",
            "fix_tasks": fix_tasks,
            "fix_iteration": state.get("fix_iteration", 0) + 1,
        }

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    log_stage_done(stage_id, f"PASS (tools: {agent_result.tool_calls_made})")

    handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
    return {
        "stages": stages,
        **handoff_update,
    }


def _check_e2e_prerequisites(paths: dict[str, Any]) -> str | None:
    """Pre-flight check for E2E testing environment.

    Returns None if OK, or an error message string if prerequisites are missing.
    Fails fast to avoid wasting 50+ minutes on unfixable browser issues.
    """
    import shutil
    import subprocess

    project_root = paths.get("project_root", ".")

    # Check if npx is available
    if not shutil.which("npx"):
        return "npx not found — Node.js/npm not installed"

    # Quick check: can playwright respond?
    try:
        result = subprocess.run(
            ["npx", "playwright", "--version"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr_fragment = (result.stderr or result.stdout or "unknown error")[:300]
            return f"playwright --version failed: {stderr_fragment}"
    except subprocess.TimeoutExpired:
        return "playwright --version timed out (30s) — browser may be stuck downloading"
    except FileNotFoundError:
        return "npx not found in PATH"

    return None


def _parallel_dispatch_active(state: dict[str, Any]) -> bool:
    """True when the graph is built with the parallel QA fan-out (dispatcher)."""
    config = state.get("config", {})
    if not config.get("dynamic_graph", {}).get("parallel_qa", False):
        return False
    from eng_loop.nodes.qa_parallel import _get_active_qa_nodes

    return len(_get_active_qa_nodes(state)) >= 2

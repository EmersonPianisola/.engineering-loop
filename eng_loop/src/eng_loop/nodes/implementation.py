from __future__ import annotations

import json
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DocUpdateOutput, ImplCodeOutput, ImplDesignOutput
from eng_loop.tools.essence_gate import essence_gate
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.node_helpers import build_handoff_update, build_node_prompt
from eng_loop.tools.progress import (
    log_artifact,
    log_stage_done,
    log_stage_fail,
)


@essence_gate("impl.design")
def impl_design_node(state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.design"

    if stages.get(stage_id, {}).get("done", False):
        return {}

    max_attempts = config.get("constraints", {}).get("max_impl_design_attempts", 2)

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
        role_description="Implementation Architect",
        instructions=(
            "Plan the execution of the work item. Use glob/grep/read to explore the project.\n"
            "Create a brief implementation plan.\n\n"
            f"Save the blueprint to {paths.get('artifact_root', '')}/blueprints/blueprint.md\n\n"
            "Return a JSON object with these fields: blueprint, tasks, file_structure, complete, decisions."
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
        output_schema=ImplDesignOutput,
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

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    blueprint = result.get("blueprint", "")
    if isinstance(blueprint, dict):
        import json

        blueprint = json.dumps(blueprint, indent=2, ensure_ascii=False)
    if blueprint:
        from eng_loop.tools.file_ops import write_file

        artifact_root = paths.get("artifact_root", "")
        write_file(f"{artifact_root}/blueprints/blueprint.md", blueprint)
        log_artifact(stage_id, f"{artifact_root}/blueprints/blueprint.md")

    new_decisions = list(state.get("decisions", []))
    for d in result.get("decisions", []):
        from eng_loop.tools.decisions import record_decision

        record_decision({"decisions": new_decisions}, d)

    log_stage_done(
        stage_id,
        f"blueprint: {len(blueprint)} chars, {len(result.get('tasks', []))} tasks, tools: {agent_result.tool_calls_made}",
    )

    handoff_update = build_handoff_update(stage_id, result, new_decisions, state)
    return {
        "stages": stages,
        "decisions": new_decisions,
        "stage_artifacts": {**state.get("stage_artifacts", {}), "impl.design": blueprint},
        **handoff_update,
    }


@essence_gate("impl.code")
def impl_code_node(state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.code"

    if stages.get(stage_id, {}).get("done", False):
        return {}

    max_attempts = config.get("constraints", {}).get("max_impl_code_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return {
            "stages": stages,
            "status": "blocked",
            "blocking_condition": f"{stage_id} non-convergence",
        }

    # Read structured feedback from verifier/QA
    fix_tasks = state.get("fix_tasks", [])
    fix_iteration = state.get("fix_iteration", 0)
    is_fix_mode = bool(fix_tasks)

    # Lessons are injected centrally by PromptBuilder (## LESSONS section:
    # confirmed + top-N candidates for this stage) — no inline dump here.

    # Build prompt based on mode
    if is_fix_mode:
        fix_tasks_json = json.dumps(fix_tasks, indent=2, ensure_ascii=False)
        extra_sections = (
            f"## FIX MODE — Iteration {fix_iteration}\n\n"
            "You are in FIX MODE. The verifier found issues in the previous implementation.\n"
            "Address EACH gap below. Read the relevant files first, then apply fixes.\n"
            "Run tests after each fix to confirm it works.\n\n"
            "### Issues to Fix:\n"
            f"{fix_tasks_json}\n\n"
            "### Instructions:\n"
            "1. For each gap, read the file at the given evidence location\n"
            "2. Understand what's wrong\n"
            "3. Apply the minimal fix needed\n"
            "4. Run the relevant tests to confirm the fix works\n"
            "5. Do NOT rewrite the entire implementation — only fix the gaps\n"
        )

        role_description = "Implementation Fix agent — address verifier findings"
        instructions = (
            f"The project root is {paths.get('project_root', '.')}. All file paths should be relative to it.\n\n"
            "After fixing all issues, run the full test suite to confirm nothing is broken.\n"
            "Return a JSON object with these fields: implementation_summary, files_created, tests_passed, complete, decisions, diff."
        )
    else:
        extra_sections = ""

        role_description = "Implementation agent"
        instructions = (
            "**Your primary task is the WORK ITEM above.** Execute it using your tools (read, write, edit, bash, glob, grep).\n\n"
            "If the work item involves writing code, follow TDD:\n"
            "1. Read relevant files first\n"
            "2. Write test file, run test — it must fail (red)\n"
            "3. Implement code, run test — it must pass (green)\n"
            "4. Commit with bash: git add + git commit\n\n"
            f"The project root is {paths.get('project_root', '.')}. All file paths should be relative to it.\n\n"
            "Return a JSON object with these fields: implementation_summary, files_created, tests_passed, complete, decisions, diff."
        )

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description=role_description,
        extra_sections=extra_sections,
        instructions=instructions,
    )
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=ImplCodeOutput,
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

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    new_decisions = list(state.get("decisions", []))
    for d in result.get("decisions", []):
        from eng_loop.tools.decisions import record_decision

        record_decision({"decisions": new_decisions}, d)

    new_artifacts = dict(state.get("stage_artifacts", {}))
    new_artifacts["impl.code"] = result.get("implementation_summary", "")
    new_artifacts["diff"] = result.get("diff", "")

    handoff_update = build_handoff_update(stage_id, result, new_decisions, state)

    if is_fix_mode:
        log_stage_done(
            stage_id,
            f"FIX MODE iter={fix_iteration}, files: {len(result.get('files_created', []))}, tests: {result.get('tests_passed')}, tools: {agent_result.tool_calls_made}",
        )
    else:
        log_stage_done(
            stage_id,
            f"files: {len(result.get('files_created', []))}, tests: {result.get('tests_passed')}, tools: {agent_result.tool_calls_made}",
        )

    return {
        "stages": stages,
        "decisions": new_decisions,
        "stage_artifacts": new_artifacts,
        **handoff_update,
        # Clear fix state on successful completion
        "fix_tasks": [],
        "rollback_target": "",
    }


@essence_gate("doc.update")
def doc_update_node(state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.update"

    if stages.get(stage_id, {}).get("done", False):
        return {}

    max_attempts = config.get("constraints", {}).get("max_doc_update_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return {}

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="Project Documentation Updater",
        instructions=(
            "Update existing project files (README, CHANGELOG, docs, inline comments).\n\n"
            "Use your tools to find and update existing documentation files.\n\n"
            "Return a JSON object with these fields: files_updated, complete."
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
        output_schema=DocUpdateOutput,
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
        return {}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    log_stage_done(stage_id, f"updated: {result.get('files_updated', [])}, tools: {agent_result.tool_calls_made}")

    return {
        "stages": stages,
    }

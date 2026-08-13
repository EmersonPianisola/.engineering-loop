from __future__ import annotations

import json
import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import ImplCodeOutput, ImplDesignOutput, DocUpdateOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.node_helpers import build_node_prompt, build_handoff_update
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name
from eng_loop.tools.next_active import resolve_next


def impl_design_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.design"

    if stages.get(stage_id, {}).get("done", False):
        _n = resolve_next("impl-code", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_impl_design_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
            goto="__end__",
        )

    prompt = build_node_prompt(
        stage_id, state, paths, config,
        role_description="Implementation Architect",
        instructions=(
            "Plan the execution of the work item. Use glob/grep/read to explore the project.\n"
            "Create a brief implementation plan (not overly detailed — just enough to guide implementation).\n\n"
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
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="impl-design",
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
                goto="impl-design",
            )

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    blueprint = result.get("blueprint", "")
    if blueprint:
        from eng_loop.tools.file_ops import write_file
        artifact_root = paths.get("artifact_root", "")
        write_file(f"{artifact_root}/blueprints/blueprint.md", blueprint)
        log_artifact(stage_id, f"{artifact_root}/blueprints/blueprint.md")

    new_decisions = list(state.get("decisions", []))
    for d in result.get("decisions", []):
        from eng_loop.tools.decisions import record_decision
        record_decision({"decisions": new_decisions}, d)

    log_stage_done(stage_id, f"blueprint: {len(blueprint)} chars, {len(result.get('tasks', []))} tasks, tools: {agent_result.tool_calls_made}")

    handoff_update = build_handoff_update(stage_id, result, new_decisions, state)

    _n = resolve_next("impl-code", state)
    return Command(
        update={
            "stages": stages,
            "decisions": new_decisions,
            "stage_artifacts": {**state.get("stage_artifacts", {}), "impl.design": blueprint},
            **handoff_update,
            "current_stage": _n,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=_n,
    )


def impl_code_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.code"

    if stages.get(stage_id, {}).get("done", False):
        _n = resolve_next("doc-update", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_impl_code_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
            goto="__end__",
        )

    confirmed_lessons = ""
    if config.get("lessons", {}).get("enabled", True):
        from eng_loop.tools.lessons import load_lessons, get_confirmed_lessons
        lessons_data = load_lessons(paths.get("artifact_root", ""))
        confirmed = get_confirmed_lessons(lessons_data)
        if confirmed:
            confirmed_lessons = json.dumps(confirmed, indent=2, ensure_ascii=False)

    extra = ""
    if confirmed_lessons:
        extra = f"## CONFIRMED LESSONS\n{confirmed_lessons}"

    prompt = build_node_prompt(
        stage_id, state, paths, config,
        role_description="Implementation agent",
        extra_sections=extra,
        instructions=(
            "**Your primary task is the WORK ITEM above.** Execute it using your tools (read, write, edit, bash, glob, grep).\n\n"
            "If the work item involves writing code, follow TDD:\n"
            "1. Read relevant files first\n"
            "2. Write test file, run test — it must fail (red)\n"
            "3. Implement code, run test — it must pass (green)\n"
            "4. Commit with bash: git add + git commit\n\n"
            "If the work item involves generating documents, reports, or summaries:\n"
            "1. Explore the project with glob/read/grep\n"
            "2. Write the requested output file\n"
            "3. Verify the file exists and is correct\n\n"
            f"The project root is {paths.get('project_root', '.')}. All file paths should be relative to it.\n\n"
            "Return a JSON object with these fields: implementation_summary, files_created, tests_passed, complete, decisions, diff."
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
        output_schema=ImplCodeOutput,
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
                goto="impl-code",
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
                goto="impl-code",
            )

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

    log_stage_done(stage_id, f"files: {len(result.get('files_created', []))}, tests: {result.get('tests_passed')}, tools: {agent_result.tool_calls_made}")

    _n = resolve_next("doc-update", state)
    return Command(
        update={
            "stages": stages,
            "decisions": new_decisions,
            "stage_artifacts": new_artifacts,
            **handoff_update,
            "current_stage": _n,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=_n,
    )


def doc_update_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.update"

    if stages.get(stage_id, {}).get("done", False):
        _n = resolve_next("verify", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_doc_update_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        _n = resolve_next("verify", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    prompt = build_node_prompt(
        stage_id, state, paths, config,
        role_description="Project Documentation Updater",
        instructions=(
            "Update existing project files (README, CHANGELOG, docs, inline comments).\n\n"
            "Use your tools to:\n"
            "1. Use glob to find existing documentation files (README, CHANGELOG, docs/)\n"
            "2. Read each file to understand current content\n"
            "3. Use edit to update existing files with new information\n"
            "4. Do NOT create new files — only update what already exists\n\n"
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
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="doc-update",
            )
        stages[stage_id]["done"] = True
        _n = resolve_next("verify", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    log_stage_done(stage_id, f"updated: {result.get('files_updated', [])}, tools: {agent_result.tool_calls_made}")

    _n = resolve_next("verify", state)
    return Command(
        update={
            "stages": stages,
            "current_stage": _n,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=_n,
    )

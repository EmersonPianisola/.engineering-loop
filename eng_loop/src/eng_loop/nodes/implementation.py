from __future__ import annotations

import json
import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import ImplCodeOutput, ImplDesignOutput, DocUpdateOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.graphify import get_graphify_injection
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


def impl_design_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.design"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="impl-code", update={"current_stage": "impl-code", "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_impl_design_attempts", 2)

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

    # Inject graphify instructions if knowledge graph is available
    graphify_injection = get_graphify_injection(state, paths)

    prompt = f"""You are the Implementation Architect. Create the implementation blueprint.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}
{graphify_injection}

## WORK ITEM
{state.get('work_item', '')}

## ARCHITECTURE CONTEXT
{state.get('stage_artifacts', {}).get('arch.solution', 'No architecture artifacts.')}

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to explore the project structure:
1. Use glob to find existing files and understand the project layout
2. Use grep to search for relevant patterns in existing code
3. Read key files to understand existing architecture and conventions
4. Create a detailed implementation blueprint with file structure, contracts, data flows, and execution order

Save the blueprint to {paths.get('artifact_root', '')}/blueprints/blueprint.md

Return a JSON object with these fields: blueprint, tasks, file_structure, complete, decisions.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
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

    return Command(
        update={
            "stages": stages,
            "decisions": new_decisions,
            "stage_artifacts": {**state.get("stage_artifacts", {}), "impl.design": blueprint},
            "current_stage": "impl-code",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="impl-code",
    )


def impl_code_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.code"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="doc-update", update={"current_stage": "doc-update", "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_impl_code_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
            goto="__end__",
        )

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    blueprint = state.get("stage_artifacts", {}).get("impl.design", "")
    if not blueprint:
        from eng_loop.tools.file_ops import read_file
        blueprint = read_file(f"{paths.get('artifact_root', '')}/blueprints/blueprint.md")

    confirmed_lessons = ""
    if config.get("lessons", {}).get("enabled", True):
        from eng_loop.tools.lessons import load_lessons, get_confirmed_lessons
        lessons_data = load_lessons(paths.get("artifact_root", ""))
        confirmed = get_confirmed_lessons(lessons_data)
        if confirmed:
            confirmed_lessons = json.dumps(confirmed, indent=2, ensure_ascii=False)

    # Inject graphify instructions if knowledge graph is available
    graphify_injection = get_graphify_injection(state, paths)

    prompt = f"""You are the Implementation agent. Execute TDD code implementation.

## PROCEDURE
{stage_proc}

## BLUEPRINT
{blueprint}

## WORK ITEM
{state.get('work_item', '')}

## CONFIRMED LESSONS
{confirmed_lessons or "No lessons."}
{graphify_injection}

## PROJECT ROOT
{paths.get('project_root', '.')}

Execute in TDD mode:
1. For each task in the blueprint:
   a. Read existing files to understand context
   b. Write test file first
   c. Run test with bash — it must fail (red)
   d. Write/implement code to satisfy the test
   e. Run test with bash — it must pass (green)
   f. Commit with bash: git add + git commit
2. After all tasks: provide summary as JSON

Use your tools: read files, write code, edit existing files, run tests with bash, search with grep/glob.
The project root is {paths.get('project_root', '.')}. All file paths should be relative to it.

Return a JSON object with these fields: implementation_summary, files_created, tests_passed, complete, decisions, diff.
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

    log_stage_done(stage_id, f"files: {len(result.get('files_created', []))}, tests: {result.get('tests_passed')}, tools: {agent_result.tool_calls_made}")

    return Command(
        update={
            "stages": stages,
            "decisions": new_decisions,
            "stage_artifacts": new_artifacts,
            "current_stage": "doc-update",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="doc-update",
    )


def doc_update_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.update"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="verify", update={"current_stage": "verify", "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_doc_update_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="verify", update={"current_stage": "verify", "iteration": state.get("iteration", 0) + 1})

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    diff = state.get("stage_artifacts", {}).get("diff", "")
    blueprint = state.get("stage_artifacts", {}).get("impl.design", "")

    prompt = f"""You are the Project Documentation Updater. Update existing project files (README, CHANGELOG, docs, inline comments).

## PROCEDURE
{stage_proc}

## DIFF
{diff}

## BLUEPRINT
{blueprint}

## WORK ITEM
{state.get('work_item', '')}

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Use glob to find existing documentation files (README, CHANGELOG, docs/)
2. Read each file to understand current content
3. Use edit to update existing files with new information
4. Do NOT create new files — only update what already exists

Return a JSON object with these fields: files_updated, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
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
        return Command(goto="verify", update={"current_stage": "verify", "iteration": state.get("iteration", 0) + 1})

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    log_stage_done(stage_id, f"updated: {result.get('files_updated', [])}, tools: {agent_result.tool_calls_made}")

    return Command(
        update={
            "stages": stages,
            "current_stage": "verify",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="verify",
    )

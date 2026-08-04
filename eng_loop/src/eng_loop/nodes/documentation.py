from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DocDecisionsOutput, DocProjectOutput
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


def doc_decisions_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.decisions"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="doc-project", update={"current_stage": "doc-project", "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_doc_decisions_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="doc-project", update={"current_stage": "doc-project", "iteration": state.get("iteration", 0) + 1})

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    decisions = state.get("decisions", [])

    prompt = f"""You are the Decision Log Consolidator. Consolidate AD-NNN decisions into formal MADR format.

## PROCEDURE
{stage_proc}

## DECISIONS RECORDED
{decisions}

## WORK ITEM
{state.get('work_item', '')}

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Read existing decision artifacts and stage outputs
2. Write the consolidated decision log to {paths.get('artifact_root', '')}/decision-log.md

Consolidate into MADR format.
Return a JSON object with these fields: decision_log, decisions_count, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 15)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=DocDecisionsOutput,
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
                goto="doc-decisions",
            )
        stages[stage_id]["done"] = True
        return Command(goto="doc-project", update={"current_stage": "doc-project", "iteration": state.get("iteration", 0) + 1})

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    decision_log = result.get("decision_log", "")
    write_file(f"{artifact_root}/decision-log.md", decision_log)
    log_artifact(stage_id, f"{artifact_root}/decision-log.md")

    log_stage_done(stage_id, f"{result.get('decisions_count', 0)} decisions, tools: {agent_result.tool_calls_made}")

    return Command(
        update={
            "stages": stages,
            "stage_artifacts": {**state.get("stage_artifacts", {}), "doc.decisions": decision_log},
            "current_stage": "doc-project",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="doc-project",
    )


def doc_project_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.project"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="post", update={"current_stage": "post", "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_doc_project_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="post", update={"current_stage": "post", "iteration": state.get("iteration", 0) + 1})

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    decision_log = state.get("stage_artifacts", {}).get("doc.decisions", "")
    if not decision_log:
        from eng_loop.tools.file_ops import read_file
        decision_log = read_file(f"{paths.get('artifact_root', '')}/decision-log.md")

    prompt = f"""You are the Project Documentation agent. Generate README, setup guide, architecture overview, and user manual using arc42 + C4 Model.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## DECISION LOG
{decision_log}

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Explore the project structure with glob
2. Read key source files to understand architecture
3. Write documentation files to the project

Generate project documentation.
Return a JSON object with these fields: readme, setup_guide, architecture_overview, user_manual, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=DocProjectOutput,
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
                goto="doc-project",
            )
        stages[stage_id]["done"] = True
        return Command(goto="post", update={"current_stage": "post", "iteration": state.get("iteration", 0) + 1})

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    log_stage_done(stage_id, f"documentation generated, tools: {agent_result.tool_calls_made}")

    return Command(
        update={
            "stages": stages,
            "current_stage": "post",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="post",
    )

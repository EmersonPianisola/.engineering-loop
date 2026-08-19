from __future__ import annotations

from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DocDecisionsOutput, DocProjectOutput
from eng_loop.tools.essence_gate import essence_gate
from eng_loop.tools.next_active import resolve_next
from eng_loop.tools.node_helpers import build_handoff_update, build_node_prompt
from eng_loop.tools.progress import (
    log_artifact,
    log_stage_done,
    log_stage_fail,
)


@essence_gate("doc.decisions")
def doc_decisions_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.decisions"

    if stages.get(stage_id, {}).get("done", False):
        _n = resolve_next("doc-project", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_doc_decisions_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        _n = resolve_next("doc-project", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    decisions = state.get("decisions", [])
    extra = f"## DECISIONS RECORDED\n{decisions}" if decisions else ""

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="Decision Log Consolidator",
        include_skill=False,
        extra_sections=extra,
        instructions=(
            "Consolidate AD-NNN decisions into formal MADR format.\n\n"
            "Use your tools to:\n"
            "1. Read existing decision artifacts and stage outputs\n"
            f"2. Write the consolidated decision log to {paths.get('artifact_root', '')}/decision-log.md\n\n"
            "Return a JSON object with these fields: decision_log, decisions_count, complete."
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
        output_schema=DocDecisionsOutput,
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
                goto="doc-decisions",
            )
        stages[stage_id]["done"] = True
        _n = resolve_next("doc-project", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file

    decision_log = result.get("decision_log", "")
    if isinstance(decision_log, dict):
        import json

        decision_log = json.dumps(decision_log, indent=2, ensure_ascii=False)
    write_file(f"{artifact_root}/decision-log.md", decision_log)
    log_artifact(stage_id, f"{artifact_root}/decision-log.md")

    log_stage_done(stage_id, f"{result.get('decisions_count', 0)} decisions, tools: {agent_result.tool_calls_made}")

    handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
    _n = resolve_next("doc-project", state)

    return Command(
        update={
            "stages": stages,
            "stage_artifacts": {**state.get("stage_artifacts", {}), "doc.decisions": decision_log},
            **handoff_update,
            "current_stage": _n,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=_n,
    )


@essence_gate("doc.project")
def doc_project_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.project"

    if stages.get(stage_id, {}).get("done", False):
        _n = resolve_next("post", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    max_attempts = config.get("constraints", {}).get("max_doc_project_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        _n = resolve_next("post", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    decision_log = state.get("stage_artifacts", {}).get("doc.decisions", "")
    if not decision_log:
        from eng_loop.tools.file_ops import read_file

        decision_log = read_file(f"{paths.get('artifact_root', '')}/decision-log.md")

    extra = f"## DECISION LOG\n{decision_log}" if decision_log else ""

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="Project Documentation agent",
        include_skill=False,
        extra_sections=extra,
        instructions=(
            "Generate README, setup guide, architecture overview, and user manual using arc42 + C4 Model.\n\n"
            "Use your tools to:\n"
            "1. Explore the project structure with glob\n"
            "2. Read key source files to understand architecture\n"
            "3. Write documentation files to the project\n\n"
            "Return a JSON object with these fields: readme, setup_guide, architecture_overview, user_manual, complete."
        ),
    )
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=DocProjectOutput,
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
                goto="doc-project",
            )
        stages[stage_id]["done"] = True
        _n = resolve_next("post", state)
        return Command(goto=_n, update={"current_stage": _n, "iteration": state.get("iteration", 0) + 1})

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    log_stage_done(stage_id, f"documentation generated, tools: {agent_result.tool_calls_made}")

    handoff_update = build_handoff_update(stage_id, result, state.get("decisions", []), state)
    _n = resolve_next("post", state)

    return Command(
        update={
            "stages": stages,
            **handoff_update,
            "current_stage": _n,
            "iteration": state.get("iteration", 0) + 1,
        },
        goto=_n,
    )

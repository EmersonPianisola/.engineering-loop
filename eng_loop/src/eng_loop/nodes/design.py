from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DesignOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.graphify import get_graphify_injection
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


DESIGN_STAGES = [
    "design.user-research",
    "design.personas",
    "design.info-arch",
    "design.interaction",
    "design.design-system",
    "design.visual-design",
]

DESIGN_NEXT_MAP = {
    "design.user-research": "design-personas",
    "design.personas": "design-info-arch",
    "design.info-arch": "design-interaction",
    "design.interaction": "design-design-system",
    "design.design-system": "design-visual-design",
    "design.visual-design": "_design_complete",
}


def design_node(stage_id: str):
    def node_fn(state: dict[str, Any]) -> Command[str]:
        from eng_loop.tools.agent_runner import run_agent, AgentResult
        from eng_loop.tools.agent_tools import get_tools_for_stage

        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})

        if stages.get(stage_id, {}).get("done", False):
            next_node = _resolve_next(stage_id, state)
            return Command(goto=next_node, update={"current_stage": next_node, "iteration": state.get("iteration", 0) + 1})

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            next_node = _resolve_next(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
                goto=next_node,
            )

        stage_file = get_stage_file(stage_id)
        skill_name = get_skill_name(stage_id)

        stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
        skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

        # Inject graphify instructions if knowledge graph is available
        graphify_injection = get_graphify_injection(state, paths)

        prompt = f"""You are the Design agent for stage: {stage_id}.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}
{graphify_injection}

## WORK ITEM
{state.get('work_item', '')}

## IDEATION
{state.get('ideation', '')}

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools (read, glob, grep) to explore the project for context.
Execute the design task.
Return a JSON object with these fields: design_output, artifacts, complete, decisions.
"""
        model = create_model_from_config(config, stage_id)

        tools = get_tools_for_stage(stage_id, paths, config)
        max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 20)

        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id=stage_id,
            output_schema=DesignOutput,
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
                    goto=stage_id.replace(".", "-").replace("_", "-"),
                )
            stages[stage_id]["done"] = True
            next_node = _resolve_next(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} agent error"},
                goto=next_node,
            )

        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = str(result)

        artifact_root = paths.get("artifact_root", "")
        design_output = result.get("design_output", "")
        if design_output:
            from eng_loop.tools.file_ops import write_file
            safe_name = stage_id.replace(".", "-").replace("_", "-")
            artifact_path = f"{artifact_root}/design/{safe_name}.md"
            write_file(artifact_path, design_output)
            log_artifact(stage_id, artifact_path)

        new_decisions = list(state.get("decisions", []))
        for d in result.get("decisions", []):
            from eng_loop.tools.decisions import record_decision
            record_decision({"decisions": new_decisions}, d)

        next_node = _resolve_next(stage_id, state)
        log_stage_done(stage_id, f"output: {len(design_output)} chars, tools: {agent_result.tool_calls_made}")

        return Command(
            update={
                "stages": stages,
                "decisions": new_decisions,
                "current_stage": next_node,
                "iteration": state.get("iteration", 0) + 1,
            },
            goto=next_node,
        )

    return node_fn


def _resolve_next(stage_id: str, state: dict[str, Any]) -> str:
    next_node = DESIGN_NEXT_MAP.get(stage_id, _post_design(state))
    if next_node == "_design_complete":
        next_node = _post_design(state)
    return next_node


def _post_design(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "arch-requirements"
    return "impl-design"


def get_design_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in DESIGN_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result

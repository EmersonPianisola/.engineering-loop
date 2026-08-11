from __future__ import annotations

import json
import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.tools.progress import log_model_invoke, log_model_done, log_stage_done, log_stage_fail
from langgraph.types import Command, interrupt


def essence_gate_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_essence_tools

    stage_id = state.get("current_stage", "")
    if not stage_id:
        return Command(goto="__end__")

    stages = state.get("stages", {})
    stage = stages.get(stage_id, {})

    if stage.get("essence_checked", False):
        return Command(goto=_next_node_name(stage_id))

    config = state.get("config", {})
    essence_config = config.get("essence", {})
    if not essence_config.get("enabled", True):
        new_stages = dict(stages)
        new_stages[stage_id] = dict(stage, essence_checked=True)
        return Command(
            update={"stages": new_stages},
            goto=_next_node_name(stage_id),
        )

    essence_inputs = _gather_essence_inputs(stage_id, state)

    # Run essence with agent tools (read-only: read + glob)
    from eng_loop.templates import load_skill, load_stage_procedure

    paths = state.get("paths", {})
    skill_root = paths.get("framework_skill_root", "")
    stage_root = paths.get("framework_stage_root", "")

    skill_content = load_skill(skill_root, "essence")
    stage_proc = load_stage_procedure(stage_root, stage_id.replace(".", "-").replace("_", "-"))

    prompt = f"""You are the Essence Sidecar validator. Apply the Four Lenses to validate inputs for stage {stage_id}.

## SKILL
{skill_content}

## STAGE PROCEDURE
{stage_proc}

## INPUTS TO VALIDATE
Work item: {essence_inputs['work_item']}
Complexity: {essence_inputs['complexity']}

## PROJECT ROOT
{paths.get('project_root', '.')}

## FOUR LENSES
Lens 1: Subjective/ambiguous terms — identify and flag
Lens 2: Hidden assumptions — surface them
Lens 3: Literal traps — detect misinterpretations
Lens 4: Conflicting priorities — identify tensions

Use read/glob to examine relevant project files if needed for context.

Return a JSON object with these fields: lenses_1_3 (list), lens_4 (null or string), suggested_adjustments (list).
"""
    model = create_model_from_config(config, stage_id)
    tools = get_essence_tools(paths)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 10)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=f"{stage_id}.essence",
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    essence_result = {
        "findings": {
            "lenses_1_3": len(result.get("lenses_1_3", [])) > 0,
            "lens_4": result.get("lens_4"),
        },
        "adjustments": result.get("suggested_adjustments", []),
    }

    if essence_result.get("findings", {}).get("lenses_1_3"):
        max_retries = config.get("max_essence_retries_per_stage", 5)
        current_retries = stage.get("essence_retries", 0)
        if current_retries >= max_retries:
            return Command(
                update={
                    "status": "blocked",
                    "blocking_condition": "essence non-convergence",
                    "stages": stages,
                },
                goto="__end__",
            )
        adjusted = _adjust_inputs_inline(essence_result, state)
        new_state = dict(state, **adjusted)
        new_stages = dict(stages)
        new_stages[stage_id] = dict(stage, essence_retries=current_retries + 1)
        return Command(
            update={"stages": new_stages},
            goto="essence_gate",
        )

    if essence_result.get("findings", {}).get("lens_4"):
        tension = essence_result["findings"]["lens_4"]
        decision = interrupt({
            "type": "essence_lens_4",
            "stage": stage_id,
            "tension": tension,
            "question": "Conflicting priorities detected. How should we proceed?",
        })
        _capture_decision(state, tension, decision)

    new_stages = dict(stages)
    new_stages[stage_id] = dict(stage, essence_checked=True)
    return Command(
        update={"stages": new_stages},
        goto=_next_node_name(stage_id),
    )


def _adjust_inputs_inline(essence_result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"work_item": state.get("work_item", "")}


def _capture_decision(state: dict[str, Any], tension: str, decision: str) -> None:
    context_file = state.get("paths", {}).get("context_file", "")
    if context_file:
        from eng_loop.tools.file_ops import append_file
        append_file(context_file, f"\n## Essence Lens 4 Decision\n**Tension**: {tension}\n**Decision**: {decision}\n")


def _next_node_name(stage_id: str) -> str:
    return stage_id.replace(".", "-").replace("_", "-")

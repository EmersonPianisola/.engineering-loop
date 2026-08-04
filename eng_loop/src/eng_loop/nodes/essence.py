from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command, interrupt


def essence_gate_node(state: dict[str, Any]) -> Command[str]:
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
        stages[stage_id]["essence_checked"] = True
        return Command(
            update={"stages": stages},
            goto=_next_node_name(stage_id),
        )

    essence_inputs = _gather_essence_inputs(stage_id, state)
    essence_result = _run_essence_validation(essence_inputs, state)

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

    stages[stage_id]["essence_checked"] = True
    return Command(
        update={"stages": stages},
        goto=_next_node_name(stage_id),
    )


def _gather_essence_inputs(stage_id: str, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "work_item": state.get("work_item", ""),
        "stage_artifacts": state.get("stage_artifacts", {}),
        "complexity": state.get("complexity", "unset"),
    }


def _run_essence_validation(inputs: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.templates import load_skill, load_stage_procedure

    paths = state.get("paths", {})
    skill_root = paths.get("framework_skill_root", "")
    stage_root = paths.get("framework_stage_root", "")

    skill_content = load_skill(skill_root, "essence")
    stage_proc = load_stage_procedure(stage_root, inputs["stage_id"].replace(".", "-").replace("_", "-"))

    model = create_model_from_config(state.get("config", {}), inputs["stage_id"])
    prompt = f"""You are the Essence Sidecar validator. Apply the Four Lenses to validate inputs for stage {inputs['stage_id']}.

## SKILL
{skill_content}

## STAGE PROCEDURE
{stage_proc}

## INPUTS TO VALIDATE
Work item: {inputs['work_item']}
Complexity: {inputs['complexity']}

## FOUR LENSES
Lens 1: Subjective/ambiguous terms — identify and flag
Lens 2: Hidden assumptions — surface them
Lens 3: Literal traps — detect misinterpretations
Lens 4: Conflicting priorities — identify tensions

Return JSON:
{{
  "lenses_1_3": [list of findings or empty],
  "lens_4": null or description of tension,
  "suggested_adjustments": [adjustments for lenses 1-3]
}}
"""
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()
    import json
    try:
        result = json.loads(content)
        return {
            "findings": {
                "lenses_1_3": len(result.get("lenses_1_3", [])) > 0,
                "lens_4": result.get("lens_4"),
            },
            "adjustments": result.get("suggested_adjustments", []),
        }
    except json.JSONDecodeError:
        return {"findings": {"lenses_1_3": False, "lens_4": None}, "adjustments": []}


def _adjust_inputs_inline(essence_result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"work_item": state.get("work_item", "")}


def _capture_decision(state: dict[str, Any], tension: str, decision: str) -> None:
    context_file = state.get("paths", {}).get("context_file", "")
    if context_file:
        from eng_loop.tools.file_ops import append_file
        append_file(context_file, f"\n## Essence Lens 4 Decision\n**Tension**: {tension}\n**Decision**: {decision}\n")


def _next_node_name(stage_id: str) -> str:
    return stage_id.replace(".", "-").replace("_", "-")

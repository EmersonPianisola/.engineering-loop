from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name
from eng_loop.tools.autosizing import classify_complexity, deactivate_inactive_stages, detect_ui_project
from eng_loop.tools.file_ops import save_json


def init_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.state import next_incomplete_stage

    config = state.get("config", {})
    paths = state.get("paths", {})
    stages = dict(state.get("stages", {}))

    ui_project = detect_ui_project(paths)
    work_item = state.get("work_item", "")

    complexity = classify_complexity(work_item, config)
    stages = deactivate_inactive_stages(stages, complexity, ui_project)

    stage_file = get_stage_file("init")
    skill_name = get_skill_name("init")

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
    skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

    prompt = f"""You are the Engineering Loop INIT agent. Validate the work item, discover skills, and prepare for the loop.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{work_item}

## COMPLEXITY CLASSIFICATION
{complexity}

Validate the input and return JSON:
{{
  "valid": true/false,
  "work_item_refined": "refined work item text",
  "estimated_files": N,
  "estimated_tasks": N,
  "notes": "any observations"
}}
"""
    stage_id = "init"
    model = create_model_from_config(state.get("config", {}), stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
        valid = result.get("valid", False)
    except (json.JSONDecodeError, TypeError):
        valid = False
        result = {}

    if not valid:
        return Command(
            update={
                "status": "blocked",
                "blocking_condition": "input not ready for engineering",
                "stages": stages,
                "complexity": complexity,
                "ui_project": ui_project,
            },
            goto="__end__",
        )

    stages["init"]["done"] = True
    stages["init"]["attempts"] = 1

    refined = result.get("work_item_refined", work_item)

    return Command(
        update={
            "stages": stages,
            "complexity": complexity,
            "ui_project": ui_project,
            "work_item": refined,
            "current_stage": "init-ideate",
            "iteration": 1,
        },
        goto="init-ideate",
    )


def init_ideate_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    stage_id = "init.ideate"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="init-bdd")

    config = state.get("config", {})
    paths = state.get("paths", {})
    max_attempts = config.get("constraints", {}).get("max_init_ideate_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
            goto="__end__",
        )

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), "init-ideate")
    skill_content = load_skill(paths.get("framework_skill_root", ""), "bmad-ideation")

    prompt = f"""You are the BMAD Ideation agent. Apply Party Mode (9 roles), Brainstorming (62 techniques), SDD extraction, and impact-gated decomposition.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

Return JSON:
{{
  "ideation_results": "structured ideation output",
  "decomposed_tasks": ["task1", "task2"],
  "ready_for_next": true/false
}}
"""
    model = create_model_from_config(state.get("config", {}), stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    return Command(
        update={
            "stages": stages,
            "ideation": result.get("ideation_results", ""),
            "current_stage": "init-bdd",
        },
        goto="init-bdd",
    )


def init_bdd_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    stage_id = "init.bdd"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="init-refine")

    config = state.get("config", {})
    paths = state.get("paths", {})
    max_attempts = config.get("constraints", {}).get("max_init_bdd_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="init-refine")

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), "init-bdd")
    skill_content = load_skill(paths.get("framework_skill_root", ""), "bmad-bdd-mapper")

    prompt = f"""You are the BDD Journey Mapper. Map full user journeys with Gherkin scenarios.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

Return JSON:
{{
  "journey_map": "journey mapping output",
  "gherkin_scenarios": ["scenario1", "scenario2"],
  "complete": true/false
}}
"""
    model = create_model_from_config(state.get("config", {}), stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    artifact_root = paths.get("artifact_root", "")
    journey_content = result.get("journey_map", "")
    if journey_content:
        from eng_loop.tools.file_ops import write_file
        write_file(f"{artifact_root}/bdd-journeys/journey.md", journey_content)

    return Command(
        update={"stages": stages, "current_stage": "init-refine"},
        goto="init-refine",
    )


def init_refine_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    stage_id = "init.refine"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto=_next_phase_node(state))

    config = state.get("config", {})
    paths = state.get("paths", {})
    max_attempts = config.get("constraints", {}).get("max_init_refine_attempts", 5)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto=_next_phase_node(state))

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), "init-refine")

    prompt = f"""You are the Idea Refinement agent. Refine the ad-hoc work item into an engineering-ready specification.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

Return JSON:
{{
  "refined_work_item": "refined text",
  "ready_for_architecture": true/false
}}
"""
    model = create_model_from_config(state.get("config", {}), stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    refined = result.get("refined_work_item", state.get("work_item", ""))
    next_node = _next_phase_node(state)

    return Command(
        update={
            "stages": stages,
            "work_item": refined,
            "current_stage": next_node,
        },
        goto=next_node,
    )


def _next_phase_node(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "arch-requirements"
    return "impl-design"

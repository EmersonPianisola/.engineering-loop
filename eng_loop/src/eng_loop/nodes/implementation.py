from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


def impl_design_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.design"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="impl-code")

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

    prompt = f"""You are the Implementation Architect. Create the implementation blueprint.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## ARCHITECTURE CONTEXT
{state.get('stage_artifacts', {}).get('arch.solution', 'No architecture artifacts.')}

Create a detailed implementation blueprint with file structure, contracts, data flows, and execution order. Return JSON:
{{
  "blueprint": "full blueprint document",
  "tasks": ["task1", "task2"],
  "file_structure": ["path1", "path2"],
  "complete": true/false,
  "decisions": ["AD-NNN decisions"]
}}
"""
    model = create_model_from_config(config, stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {"blueprint": content, "tasks": [], "complete": True, "decisions": []}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    blueprint = result.get("blueprint", "")
    if blueprint:
        from eng_loop.tools.file_ops import write_file
        artifact_root = paths.get("artifact_root", "")
        write_file(f"{artifact_root}/blueprints/blueprint.md", blueprint)

    new_decisions = list(state.get("decisions", []))
    for d in result.get("decisions", []):
        from eng_loop.tools.decisions import record_decision
        record_decision({"decisions": new_decisions}, d)

    return Command(
        update={
            "stages": stages,
            "decisions": new_decisions,
            "current_stage": "impl-code",
        },
        goto="impl-code",
    )


def impl_code_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "impl.code"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="doc-update")

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
            import json
            confirmed_lessons = json.dumps(confirmed, indent=2, ensure_ascii=False)

    prompt = f"""You are the Implementation agent. Execute TDD code implementation.

## PROCEDURE
{stage_proc}

## BLUEPRINT
{blueprint}

## WORK ITEM
{state.get('work_item', '')}

## CONFIRMED LESSONS
{confirmed_lessons or "No lessons."}

Execute in TDD mode: test first (must fail/red), implement code, verify pass/green, atomic commit per task.

Return JSON:
{{
  "implementation_summary": "what was implemented",
  "files_created": ["list of files"],
  "tests_passed": true/false,
  "complete": true/false,
  "decisions": ["AD-NNN decisions"],
  "diff": "git diff or summary of changes"
}}
"""
    model = create_model_from_config(config, stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {"implementation_summary": content, "complete": True, "decisions": [], "diff": ""}

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

    return Command(
        update={
            "stages": stages,
            "decisions": new_decisions,
            "stage_artifacts": new_artifacts,
            "current_stage": "doc-update",
        },
        goto="doc-update",
    )


def doc_update_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.update"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="verify")

    max_attempts = config.get("constraints", {}).get("max_doc_update_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="verify")

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

Update existing documentation files. Do NOT create new files. Return JSON:
{{
  "files_updated": ["list of files updated"],
  "complete": true/false
}}
"""
    model = create_model_from_config(config, stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {"files_updated": [], "complete": True}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    return Command(
        update={
            "stages": stages,
            "current_stage": "verify",
        },
        goto="verify",
    )

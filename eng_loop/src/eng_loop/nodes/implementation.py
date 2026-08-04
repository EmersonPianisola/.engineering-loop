from __future__ import annotations

import json
import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import ImplCodeOutput, ImplDesignOutput, DocUpdateOutput
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


def impl_design_node(state: dict[str, Any]) -> Command[str]:
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

    prompt = f"""You are the Implementation Architect. Create the implementation blueprint.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## ARCHITECTURE CONTEXT
{state.get('stage_artifacts', {}).get('arch.solution', 'No architecture artifacts.')}

Create a detailed implementation blueprint with file structure, contracts, data flows, and execution order.
Return a JSON object with these fields: blueprint, tasks, file_structure, complete, decisions.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(ImplDesignOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        log_model_done(stage_id, time.monotonic() - t0)
        log_stage_fail(stage_id, f"LLM error: {e}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} LLM error: {e}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="impl-design",
            )
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} LLM error"},
            goto="__end__",
        )

    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)

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

    log_stage_done(stage_id, f"blueprint: {len(blueprint)} chars, {len(result.get('tasks', []))} tasks")

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

Return a JSON object with these fields: implementation_summary, files_created, tests_passed, complete, decisions, diff.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(ImplCodeOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        log_model_done(stage_id, time.monotonic() - t0)
        log_stage_fail(stage_id, f"LLM error: {e}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} LLM error: {e}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="impl-code",
            )
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} LLM error"},
            goto="__end__",
        )

    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)

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

    log_stage_done(stage_id, f"files: {len(result.get('files_created', []))}, tests: {result.get('tests_passed')}")

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

Update existing documentation files. Do NOT create new files.
Return a JSON object with these fields: files_updated, complete.
"""
    model = create_model_from_config(config, stage_id)
    log_model_invoke(stage_id)
    t0 = time.monotonic()

    try:
        structured = model.with_structured_output(DocUpdateOutput)
        response = structured.invoke([{"role": "user", "content": prompt}])
        if hasattr(response, "model_dump"):
            result = response.model_dump()
        else:
            result = dict(response)
    except Exception as e:
        log_model_done(stage_id, time.monotonic() - t0)
        log_stage_fail(stage_id, f"LLM error: {e}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return Command(
                update={
                    "stages": stages,
                    "errors": list(state.get("errors", [])) + [f"{stage_id} LLM error: {e}"],
                    "current_stage": stage_id,
                    "iteration": state.get("iteration", 0) + 1,
                },
                goto="doc-update",
            )
        stages[stage_id]["done"] = True
        return Command(goto="verify", update={"current_stage": "verify", "iteration": state.get("iteration", 0) + 1})

    elapsed = time.monotonic() - t0
    log_model_done(stage_id, elapsed)

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    log_stage_done(stage_id, f"updated: {result.get('files_updated', [])}")

    return Command(
        update={
            "stages": stages,
            "current_stage": "verify",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="verify",
    )

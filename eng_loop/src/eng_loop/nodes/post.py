from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


def post_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "post"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="__end__")

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    decisions = state.get("decisions", [])
    errors = state.get("errors", [])

    lessons_data = {}
    if config.get("lessons", {}).get("enabled", True):
        from eng_loop.tools.lessons import load_lessons, get_confirmed_lessons, promote_to_pending, save_lessons
        lessons_data = load_lessons(paths.get("artifact_root", ""))
        confirmed = get_confirmed_lessons(lessons_data)
        promoted = promote_to_pending(lessons_data.get("local", {}))

        if promoted:
            save_lessons(paths.get("artifact_root", ""), lessons_data.get("local", {}), "lessons-pending.json")

    prompt = f"""You are the Post-Loop Finalize agent. Complete skill improvement, lessons consolidation, and finalization.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## DECISIONS
{decisions}

## ERRORS ENCOUNTERED
{errors}

## CONFIRMED LESSONS
{len(confirmed) if confirmed else 0}

Execute:
1. Skill improvement — extract lessons, update skills
2. Lessons share — identify new confirmed lessons
3. Finalize — verify all tasks, run full test suite, lint/build, commit, report

Return JSON:
{{
  "summary": "execution summary",
  "lessons_to_share": N,
  "final_status": "done",
  "complete": true
}}
"""
    model = create_model_from_config(config, stage_id)
    response = model.invoke([{"role": "user", "content": prompt}])
    content = response.content.strip()

    import json
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        result = {"summary": content, "final_status": "done", "complete": True}

    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    summary = result.get("summary", "")
    if summary:
        from eng_loop.tools.file_ops import write_file
        artifact_root = paths.get("artifact_root", "")
        write_file(f"{artifact_root}/post-loop-summary.md", summary)

    return Command(
        update={
            "stages": stages,
            "status": "done",
            "current_stage": "",
        },
        goto="__end__",
    )

from __future__ import annotations

import time
from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import PostOutput
from eng_loop.tools.progress import (
    log_model_invoke, log_model_done, log_stage_done, log_stage_fail, log_artifact,
)
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


def post_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import run_agent, AgentResult
    from eng_loop.tools.agent_tools import get_tools_for_stage

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
    confirmed = []
    if config.get("lessons", {}).get("enabled", True):
        from eng_loop.tools.lessons import load_lessons, get_confirmed_lessons, promote_to_pending, save_lessons
        lessons_data = load_lessons(paths.get("artifact_root", ""))
        confirmed = get_confirmed_lessons(lessons_data) or []
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

## PROJECT ROOT
{paths.get('project_root', '.')}

Use your tools to:
1. Run full test suite with bash
2. Run lint/build with bash
3. Commit changes with bash: git add + git commit
4. Write final summary to {paths.get('artifact_root', '')}/post-loop-summary.md

Execute:
1. Skill improvement — extract lessons, update skills
2. Lessons share — identify new confirmed lessons
3. Finalize — verify all tasks, run full test suite, lint/build, commit, report

Return a JSON object with these fields: summary, lessons_to_share, final_status, complete.
"""
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=PostOutput,
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    if agent_result.error:
        log_stage_fail(stage_id, agent_result.error)
        # Post is the last stage, proceed with what we have
        result = {"summary": str(agent_result.error), "final_status": "done", "complete": True, "lessons_to_share": 0}

    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    summary = result.get("summary", "")
    if summary:
        from eng_loop.tools.file_ops import write_file
        artifact_root = paths.get("artifact_root", "")
        write_file(f"{artifact_root}/post-loop-summary.md", summary)
        log_artifact(stage_id, f"{artifact_root}/post-loop-summary.md")

    log_stage_done(stage_id, result.get("final_status", "done"))

    return Command(
        update={
            "stages": stages,
            "status": "done",
            "current_stage": "",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="__end__",
    )

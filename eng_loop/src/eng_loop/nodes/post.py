from __future__ import annotations

import os
from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import PostOutput
from eng_loop.state import compute_task_outcome, get_work_item_text
from eng_loop.templates import get_stage_file, load_stage_procedure
from eng_loop.tools.essence_gate import essence_gate
from eng_loop.tools.progress import (
    log_artifact,
    log_stage_done,
    log_stage_fail,
)


@essence_gate("post")
def post_node(state: dict[str, Any]) -> Command[str]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "post"
    artifact_root = paths.get("artifact_root", "")

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="__end__")

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    decisions = state.get("decisions", [])
    errors = state.get("errors", [])
    work_item = state.get("work_item", {})
    code_map = []
    if isinstance(work_item, dict):
        code_map = work_item.get("code_map", [])
    work_item_text = get_work_item_text(state)

    lessons_data = {}
    confirmed = []
    if config.get("lessons", {}).get("enabled", True):
        from eng_loop.tools.lessons import get_confirmed_lessons, load_lessons, promote_to_pending, save_lessons

        lessons_data = load_lessons(artifact_root)
        confirmed = get_confirmed_lessons(lessons_data) or []
        promoted = promote_to_pending(lessons_data.get("local", {}))

        if promoted:
            save_lessons(artifact_root, lessons_data.get("local", {}), "lessons-pending.json")

    # Build artifact evidence: check which expected files actually exist
    artifact_evidence = {}
    for artifact_path in code_map:
        exists = os.path.exists(artifact_path)
        artifact_evidence[artifact_path] = {
            "exists": exists,
            "verified": False,
        }

    # Check all artifacts in artifact_root that were created during this run
    if os.path.isdir(artifact_root):
        for fname in os.listdir(artifact_root):
            fpath = os.path.join(artifact_root, fname)
            if os.path.isfile(fpath) and fname not in (
                "post-loop-summary.md",
                "lessons.json",
                "lessons-shared.json",
                "lessons-pending.json",
                "LESSONS.md",
            ):
                canonical = f"artifacts/{fname}"
                if canonical not in artifact_evidence:
                    artifact_evidence[canonical] = {"exists": True, "verified": False}

    prompt = f"""You are the Post-Loop Finalize agent. Complete skill improvement, lessons consolidation, and finalization.

## PROCEDURE
{stage_proc}

## WORK ITEM
{work_item_text}

## DECISIONS
{decisions}

## ERRORS ENCOUNTERED
{errors}

## CONFIRMED LESSONS
{len(confirmed) if confirmed else 0}

## PROJECT ROOT
{paths.get("project_root", ".")}

## ARTIFACT EVIDENCE
Expected artifacts (from work item code_map):
{artifact_evidence or "None specified"}

Use your tools to:
1. Verify expected artifacts exist and are non-empty
2. Run full test suite with bash (if applicable)
3. Run lint/build with bash (if applicable)
4. Commit changes with bash: git add + git commit
5. Write final summary to {artifact_root}/post-loop-summary.md

Execute:
1. Skill improvement — extract lessons, update skills
2. Lessons share — identify new confirmed lessons
3. Finalize — verify all tasks, check artifacts, run tests, lint, commit, report

Return a JSON object with these fields: summary, lessons_to_share, final_status, complete.
Set final_status to "failed" if artifacts are missing or work item was not completed.
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
        result = {
            "summary": str(agent_result.error),
            "final_status": "failed",
            "complete": True,
            "lessons_to_share": 0,
        }

    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    summary = result.get("summary", "")
    if summary:
        from eng_loop.tools.file_ops import write_file

        write_file(f"{artifact_root}/post-loop-summary.md", summary)
        log_artifact(stage_id, f"{artifact_root}/post-loop-summary.md")

    post_final_status = (
        result.get("final_status", "failed") if agent_result.error else result.get("final_status", "done")
    )
    log_stage_done(stage_id, post_final_status)

    # Compute honest task outcome — post failure means task failure
    task_outcome = compute_task_outcome(stages, post_final_status)

    return Command(
        update={
            "stages": stages,
            "status": task_outcome,
            "task_outcome": task_outcome,
            "artifact_evidence": artifact_evidence,
            "current_stage": "",
            "iteration": state.get("iteration", 0) + 1,
        },
        goto="__end__",
    )

from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


def doc_decisions_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.decisions"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="doc-project")

    max_attempts = config.get("constraints", {}).get("max_doc_decisions_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="doc-project")

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    decisions = state.get("decisions", [])

    prompt = f"""You are the Decision Log Consolidator. Consolidate AD-NNN decisions into formal MADR format.

## PROCEDURE
{stage_proc}

## DECISIONS RECORDED
{decisions}

## WORK ITEM
{state.get('work_item', '')}

Consolidate into MADR format. Return JSON:
{{
  "decision_log": "MADR formatted decision log",
  "decisions_count": N,
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
        result = {"decision_log": content, "complete": True}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    write_file(f"{artifact_root}/decision-log.md", result.get("decision_log", ""))

    return Command(
        update={
            "stages": stages,
            "current_stage": "doc-project",
        },
        goto="doc-project",
    )


def doc_project_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "doc.project"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="post")

    max_attempts = config.get("constraints", {}).get("max_doc_project_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        return Command(goto="post")

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    decision_log = state.get("stage_artifacts", {}).get("doc.decisions", "")
    if not decision_log:
        from eng_loop.tools.file_ops import read_file
        decision_log = read_file(f"{paths.get('artifact_root', '')}/decision-log.md")

    prompt = f"""You are the Project Documentation agent. Generate README, setup guide, architecture overview, and user manual using arc42 + C4 Model.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## DECISION LOG
{decision_log}

Generate project documentation. Return JSON:
{{
  "readme": "README content",
  "setup_guide": "setup.md content",
  "architecture_overview": "architecture overview",
  "user_manual": "user manual content",
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
        result = {"readme": content, "complete": True}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    return Command(
        update={
            "stages": stages,
            "current_stage": "post",
        },
        goto="post",
    )

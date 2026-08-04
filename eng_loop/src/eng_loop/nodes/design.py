from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
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
        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})

        if stages.get(stage_id, {}).get("done", False):
            next_node = DESIGN_NEXT_MAP.get(stage_id, _post_design(state))
            if next_node == "_design_complete":
                next_node = _post_design(state)
            return Command(goto=next_node)

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            next_node = DESIGN_NEXT_MAP.get(stage_id, _post_design(state))
            if next_node == "_design_complete":
                next_node = _post_design(state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
                goto=next_node,
            )

        stage_file = get_stage_file(stage_id)
        skill_name = get_skill_name(stage_id)

        stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
        skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

        prompt = f"""You are the Design agent for stage: {stage_id}.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## IDEATION
{state.get('ideation', '')}

Execute the design task and return JSON:
{{
  "design_output": "structured design output",
  "artifacts": ["list of artifact descriptions"],
  "complete": true/false,
  "decisions": ["AD-NNN style decisions made"]
}}
"""
        model = create_model_from_config(config, stage_id)
        response = model.invoke([{"role": "user", "content": prompt}])
        content = response.content.strip()

        import json
        try:
            result = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            result = {"design_output": content, "complete": True, "artifacts": [], "decisions": []}

        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["done"] = True
        stages[stage_id]["output"] = str(result)

        artifact_root = paths.get("artifact_root", "")
        design_output = result.get("design_output", "")
        if design_output:
            from eng_loop.tools.file_ops import write_file
            safe_name = stage_id.replace(".", "-").replace("_", "-")
            write_file(f"{artifact_root}/design/{safe_name}.md", design_output)

        new_decisions = list(state.get("decisions", []))
        for d in result.get("decisions", []):
            from eng_loop.tools.decisions import record_decision
            record_decision({"decisions": new_decisions}, d)

        next_node = DESIGN_NEXT_MAP.get(stage_id, _post_design(state))
        if next_node == "_design_complete":
            next_node = _post_design(state)

        return Command(
            update={
                "stages": stages,
                "decisions": new_decisions,
                "current_stage": next_node,
            },
            goto=next_node,
        )

    return node_fn


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

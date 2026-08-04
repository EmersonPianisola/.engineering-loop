from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


ARCH_STAGES = {
    "arch.requirements": "requirements-refiner",
    "arch.solution": "solution-designer",
    "arch.review": "architecture-reviewer",
}

ARCH_NEXT_MAP = {
    "arch.requirements": "arch-solution",
    "arch.solution": "_arch_post_solution",
    "arch.review": "impl-design",
}


def arch_node(stage_id: str):
    def node_fn(state: dict[str, Any]) -> Command[str]:
        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})

        if stages.get(stage_id, {}).get("done", False):
            next_node = _resolve_next(stage_id, state)
            return Command(goto=next_node)

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            next_node = _resolve_next(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
                goto=next_node,
            )

        stage_file = get_stage_file(stage_id)
        skill_name = get_skill_name(stage_id)

        stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
        skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

        context = _build_arch_context(stage_id, state)

        prompt = f"""You are the Architecture agent for stage: {stage_id}.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## CONTEXT
{context}

Execute the architecture task and return JSON:
{{
  "architecture_output": "structured output",
  "complete": true/false,
  "decisions": ["AD-NNN decisions"],
  "critical_findings": []
}}
"""
        model = create_model_from_config(config, stage_id)
        response = model.invoke([{"role": "user", "content": prompt}])
        content = response.content.strip()

        import json
        try:
            result = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            result = {"architecture_output": content, "complete": True, "decisions": [], "critical_findings": []}

        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["output"] = str(result)

        critical_findings = result.get("critical_findings", [])
        if critical_findings and stage_id == "arch.review":
            return Command(
                update={
                    "stages": stages,
                    "current_stage": "arch-requirements",
                },
                goto="arch-requirements",
            )

        stages[stage_id]["done"] = True

        artifact_root = paths.get("artifact_root", "")
        arch_output = result.get("architecture_output", "")
        if arch_output:
            from eng_loop.tools.file_ops import write_file
            safe_name = stage_id.replace(".", "-").replace("_", "-")
            write_file(f"{artifact_root}/architectures/{safe_name}.md", arch_output)

        new_decisions = list(state.get("decisions", []))
        for d in result.get("decisions", []):
            from eng_loop.tools.decisions import record_decision
            record_decision({"decisions": new_decisions}, d)

        next_node = _resolve_next(stage_id, state)

        return Command(
            update={
                "stages": stages,
                "decisions": new_decisions,
                "current_stage": next_node,
            },
            goto=next_node,
        )

    return node_fn


def _build_arch_context(stage_id: str, state: dict[str, Any]) -> str:
    artifacts = state.get("stage_artifacts", {})
    parts = []
    if stage_id in ("arch.solution", "arch.review"):
        req = artifacts.get("arch.requirements", "")
        if req:
            parts.append(f"## Requirements\n{req}")
    if stage_id == "arch.review":
        sol = artifacts.get("arch.solution", "")
        if sol:
            parts.append(f"## Solution\n{sol}")
    return "\n".join(parts) if parts else "No prior architecture artifacts."


def _resolve_next(stage_id: str, state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if stage_id == "arch.solution":
        if complexity == "complex":
            return "arch-review"
        return "impl-design"
    if stage_id == "arch.review":
        return "impl-design"
    return ARCH_NEXT_MAP.get(stage_id, "impl-design")


def get_arch_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in ARCH_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result

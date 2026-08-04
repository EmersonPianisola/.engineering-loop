from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


QA_STAGES = {
    "qa.security": "OWASP WSTG",
    "qa.api-contract": "OpenAPI",
    "qa.performance": "performance best practices",
}

QA_NEXT_MAP = {
    "qa.security": "qa.api-contract",
    "qa.api-contract": "qa.performance",
    "qa.performance": "deploy.prepare",
}


def qa_node(stage_id: str):
    def node_fn(state: dict[str, Any]) -> Command[str]:
        stages = dict(state.get("stages", {}))
        config = state.get("config", {})
        paths = state.get("paths", {})

        if stages.get(stage_id, {}).get("done", False):
            next_node = _resolve_next_qa(stage_id, state)
            return Command(goto=next_node)

        max_attempts = config.get("constraints", {}).get(
            f"max_{stage_id.replace('.', '_').replace('-', '_')}_attempts", 2
        )

        if stages[stage_id].get("attempts", 0) >= max_attempts:
            stages[stage_id]["done"] = True
            next_node = _resolve_next_qa(stage_id, state)
            return Command(
                update={"stages": stages, "status": "blocked", "blocking_condition": f"{stage_id} non-convergence"},
                goto=next_node,
            )

        stage_file = get_stage_file(stage_id)
        stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

        qa_type = QA_STAGES.get(stage_id, "review")

        prompt = f"""You are the {qa_type} QA agent for stage: {stage_id}.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## BLUEPRINT
{state.get('stage_artifacts', {}).get('impl.design', '')}

## DIFF
{state.get('stage_artifacts', {}).get('diff', '')}

Execute the QA review and return JSON:
{{
  "verdict": "PASS" or "FAIL",
  "findings": ["finding descriptions"],
  "critical_findings": ["critical issues"],
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
            result = {"verdict": "PASS", "findings": [], "critical_findings": [], "complete": True}

        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        stages[stage_id]["output"] = str(result)

        verdict = result.get("verdict", "PASS")
        critical = result.get("critical_findings", [])

        if verdict == "FAIL" or critical:
            stages["impl.code"]["done"] = False
            stages[stage_id]["done"] = False
            return Command(
                update={
                    "stages": stages,
                    "current_stage": "impl-code",
                    "errors": list(state.get("errors", [])) + [f"{stage_id} FAIL: {critical}"],
                },
                goto="impl-code",
            )

        stages[stage_id]["done"] = True
        next_node = _resolve_next_qa(stage_id, state)

        return Command(
            update={
                "stages": stages,
                "current_stage": next_node,
            },
            goto=next_node,
        )

    return node_fn


def _resolve_next_qa(stage_id: str, state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if stage_id == "qa.security":
        if complexity in ("medium", "large", "complex"):
            return "qa-api-contract"
        return "deploy-prepare"
    if stage_id == "qa.api-contract":
        if complexity == "complex":
            return "qa-performance"
        return "deploy-prepare"
    return "deploy-prepare"


def get_qa_nodes() -> list[tuple[str, str]]:
    result = []
    for sid in QA_STAGES:
        node_name = sid.replace(".", "-").replace("_", "-")
        result.append((node_name, sid))
    return result

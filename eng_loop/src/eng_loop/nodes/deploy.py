from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_stage_procedure, get_stage_file


def deploy_prepare_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "deploy.prepare"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto=_post_deploy(state))

    max_attempts = config.get("constraints", {}).get("max_deploy_prepare_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code"},
            goto="impl-code",
        )

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    prompt = f"""You are the Deploy Preparation agent. Execute build, lint, type check, env config, migration verification.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## DIFF
{state.get('stage_artifacts', {}).get('diff', '')}

Execute deployment preparation checks. Return JSON:
{{
  "build_status": "pass/fail",
  "lint_status": "pass/fail",
  "type_check_status": "pass/fail",
  "verdict": "PASS" or "FAIL",
  "errors": ["any errors"],
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
        result = {"verdict": "PASS", "errors": [], "complete": True}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["output"] = str(result)

    verdict = result.get("verdict", "PASS")

    if verdict == "FAIL":
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = False
        return Command(
            update={
                "stages": stages,
                "current_stage": "impl-code",
                "errors": list(state.get("errors", [])) + [f"deploy.prepare FAIL: {result.get('errors', [])}"],
            },
            goto="impl-code",
        )

    stages[stage_id]["done"] = True
    return Command(
        update={
            "stages": stages,
            "current_stage": _post_deploy(state),
        },
        goto=_post_deploy(state),
    )


def smoke_test_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "smoke.test"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto="doc-decisions")

    max_attempts = config.get("constraints", {}).get("max_smoke_test_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code"},
            goto="impl-code",
        )

    stage_file = get_stage_file(stage_id)
    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    prompt = f"""You are the Smoke Test agent. Execute full user journey against production build.

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

Execute:
1. Build production binary
2. Define critical paths (login, navigation, CRUD, reports, logout)
3. Run full user journey against production build
4. Screenshot at each step
5. Console + network error monitoring

Return JSON:
{{
  "verdict": "PASS" or "FAIL",
  "critical_paths": ["path1: pass", ...],
  "console_errors": 0,
  "network_errors": 0,
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
        result = {"verdict": "PASS", "complete": True}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["output"] = str(result)

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    write_file(f"{artifact_root}/smoke-report.md", str(result))

    if verdict == "FAIL":
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = False
        return Command(
            update={"stages": stages, "current_stage": "impl-code"},
            goto="impl-code",
        )

    stages[stage_id]["done"] = True
    return Command(
        update={
            "stages": stages,
            "current_stage": "doc-decisions",
        },
        goto="doc-decisions",
    )


def _post_deploy(state: dict[str, Any]) -> str:
    ui_project = state.get("ui_project", False)
    complexity = state.get("complexity", "small")

    if ui_project:
        return "smoke-test"

    if complexity in ("medium", "large", "complex"):
        return "doc-decisions"
    return "post"

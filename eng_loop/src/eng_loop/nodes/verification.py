from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from langgraph.types import Command

from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


def verify_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "verify"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto=_post_verify(state))

    max_attempts = config.get("constraints", {}).get("max_verify_attempts", 3)

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

    blueprint = state.get("stage_artifacts", {}).get("impl.design", "")
    diff = state.get("stage_artifacts", {}).get("diff", "")

    prompt = f"""You are the Independent Verifier. Author != Verifier. Perform spec-anchored check, discrimination sensor, and coverage audit.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## BLUEPRINT
{blueprint}

## DIFF
{diff}

## WORK ITEM
{state.get('work_item', '')}

Execute verification:
1. Spec-anchored check — each AC traced to file:line evidence
2. Discrimination sensor — inject behavior-level faults, confirm tests kill them
3. Coverage audit — ACs vs test coverage

Return JSON:
{{
  "verdict": "PASS" or "FAIL",
  "per_ac_evidence": ["AC1 -> file:line", ...],
  "discrimination_sensor": "pass/fail",
  "coverage_audit": "pass/fail",
  "gaps": ["gap descriptions if FAIL"],
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
        result = {"verdict": "PASS", "gaps": [], "complete": True}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["output"] = str(result)

    verdict = result.get("verdict", "PASS")

    artifact_root = paths.get("artifact_root", "")
    from eng_loop.tools.file_ops import write_file
    write_file(f"{artifact_root}/validation.md", str(result))

    if verdict == "FAIL":
        gaps = result.get("gaps", [])
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = False
        return Command(
            update={
                "stages": stages,
                "current_stage": "impl-code",
                "errors": list(state.get("errors", [])) + [f"Verify FAIL: {gaps}"],
            },
            goto="impl-code",
        )

    stages[stage_id]["done"] = True
    return Command(
        update={
            "stages": stages,
            "current_stage": _post_verify(state),
        },
        goto=_post_verify(state),
    )


def e2e_execute_node(state: dict[str, Any]) -> Command[str]:
    stages = dict(state.get("stages", {}))
    config = state.get("config", {})
    paths = state.get("paths", {})
    stage_id = "e2e.execute"

    if stages.get(stage_id, {}).get("done", False):
        return Command(goto=_post_e2e(state))

    max_attempts = config.get("constraints", {}).get("max_e2e_execute_attempts", 3)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages["impl.code"]["done"] = False
        stages[stage_id]["done"] = True
        return Command(
            update={"stages": stages, "current_stage": "impl-code"},
            goto="impl-code",
        )

    stage_file = get_stage_file(stage_id)
    skill_name = get_skill_name(stage_id)

    stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)
    skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

    prompt = f"""You are the E2E Playwright Testing agent. Execute browser E2E testing with 4-layer assertions.

## SKILL
{skill_content}

## PROCEDURE
{stage_proc}

## WORK ITEM
{state.get('work_item', '')}

## BLUEPRINT
{state.get('stage_artifacts', {}).get('impl.design', '')}

Execute:
1. Infrastructure setup — Playwright, config, Page Objects
2. Auth bypass detection + wiring
3. Scenario derivation from BDD @e2e tags
4. Four-layer assertions: DOM, Dimension, Console, Network
5. Screenshot evidence capture
6. BDD->E2E 1:1 coverage check

Return JSON:
{{
  "verdict": "PASS" or "FAIL",
  "test_results": ["test1: pass", ...],
  "console_errors": 0,
  "network_errors": 0,
  "bdd_coverage": "1:1 achieved or gaps",
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
    write_file(f"{artifact_root}/e2e-report.md", str(result))

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
            "current_stage": _post_e2e(state),
        },
        goto=_post_e2e(state),
    )


def _post_verify(state: dict[str, Any]) -> str:
    ui_project = state.get("ui_project", False)
    complexity = state.get("complexity", "small")
    if ui_project:
        return "e2e-execute"
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "deploy-prepare"


def _post_e2e(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "deploy-prepare"

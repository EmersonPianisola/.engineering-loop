from __future__ import annotations

from typing import Any, Literal

from eng_loop.state import (
    STAGE_ORDER,
    all_active_stages_done,
    get_active_stages,
    get_max_attempts,
    next_incomplete_stage,
)


def route_after_essence(state: dict[str, Any]) -> str:
    stage_id = state.get("current_stage", "")
    if not stage_id:
        return "__end__"
    return stage_id.replace(".", "-").replace("_", "-")


def route_after_stage(state: dict[str, Any]) -> str:
    stage_id = state.get("current_stage", "")
    if not stage_id:
        return "__end__"

    stages = state.get("stages", {})
    stage = stages.get(stage_id, {})

    if not stage.get("done", False):
        config = state.get("config", {})
        max_att = get_max_attempts(config, stage_id)
        if stage.get("attempts", 0) < max_att:
            return stage_id.replace(".", "-").replace("_", "-")

    return _find_next_stage(state)


def route_check_loop(state: dict[str, Any]) -> Literal["continue_loop", "__end__"]:
    if state.get("status") in ("blocked", "halted"):
        return "__end__"
    if all_active_stages_done(state):
        return "__end__"

    iteration = state.get("iteration", 0)
    max_iterations = state.get("config", {}).get("max_loop_iterations", 50)
    if iteration >= max_iterations:
        return "__end__"

    return "continue_loop"


def route_blocked(state: dict[str, Any]) -> Literal["__end__"]:
    return "__end__"


def _find_next_stage(state: dict[str, Any]) -> str:
    next_sid = next_incomplete_stage(state)
    if not next_sid:
        return "__end__"
    return next_sid.replace(".", "-").replace("_", "-")


def route_init_complete(state: dict[str, Any]) -> str:
    if state.get("status") == "blocked":
        return "__end__"
    return "init-ideate"


def route_design_complete(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "arch-requirements"
    return "impl-design"


def route_arch_complete(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity == "complex":
        return "arch-review"
    return "impl-design"


def route_verify_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("verify", {}).get("done", False):
        return "impl-code"
    return _post_verify_route(state)


def route_e2e_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("e2e.execute", {}).get("done", False):
        return "impl-code"
    return _post_e2e_route(state)


def route_qa_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    current = state.get("current_stage", "")
    if not stages.get(current, {}).get("done", False):
        return "impl-code"
    return _next_qa_or_deploy(state)


def route_deploy_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("deploy.prepare", {}).get("done", False):
        return "impl-code"
    ui_project = state.get("ui_project", False)
    if ui_project:
        return "smoke-test"
    return _post_deploy_route(state)


def route_smoke_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("smoke.test", {}).get("done", False):
        return "impl-code"
    return _post_deploy_route(state)


def _post_verify_route(state: dict[str, Any]) -> str:
    ui_project = state.get("ui_project", False)
    complexity = state.get("complexity", "small")
    if ui_project:
        return "e2e-execute"
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "deploy-prepare"


def _post_e2e_route(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "deploy-prepare"


def _next_qa_or_deploy(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    current = state.get("current_stage", "")
    if current == "qa.security" and complexity in ("medium", "large", "complex"):
        return "qa-api-contract"
    if current == "qa.api-contract" and complexity == "complex":
        return "qa-performance"
    return "deploy-prepare"


def _post_deploy_route(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "doc-decisions"
    return "post"

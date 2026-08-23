from __future__ import annotations

from typing import Any, Literal

from eng_loop.state import (
    all_active_stages_done,
    get_max_attempts,
    next_incomplete_stage,
)
from eng_loop.tools.trace_logger import trace as _trace


def route_after_essence(state: dict[str, Any]) -> str:
    stage_id = state.get("current_stage", "")
    if not stage_id:
        return "__end__"
    result = stage_id.replace(".", "-").replace("_", "-")
    _trace.route_decision("route_after_essence", result, reason="essence complete, route to first stage")
    return result


def route_after_stage(state: dict[str, Any]) -> str:
    stage_id = state.get("current_stage", "")
    if not stage_id:
        _trace.route_decision("route_after_stage", "__end__", reason="no current_stage")
        return "__end__"

    stages = state.get("stages", {})
    stage = stages.get(stage_id, {})

    if not stage.get("done", False):
        config = state.get("config", {})
        max_att = get_max_attempts(config, stage_id)
        if stage.get("attempts", 0) < max_att:
            att = stage.get("attempts", 0)
            node = stage_id.replace(".", "-").replace("_", "-")
            _trace.route_decision(
                "route_after_stage",
                node,
                reason=f"NOT DONE, retry {att}/{max_att}",
            )
            return node

    # T4: If context bus has unresolved critical findings, re-route to current
    # stage for another attempt rather than advancing blindly
    bus = state.get("context_bus")
    if bus and bus.entry_count > 0:
        for entry in bus._entries:
            if entry.entry_type == "critical_finding":
                node = stage_id.replace(".", "-").replace("_", "-")
                _trace.route_decision(
                    "route_after_stage",
                    node,
                    reason="critical_finding in context_bus, re-attempt",
                )
                return node

    result = _find_next_stage(state)
    _trace.route_decision("route_after_stage", result, reason="DONE, advance to next")
    return result


def route_check_loop(state: dict[str, Any]) -> Literal["continue_loop", "__end__"]:
    if state.get("status") in ("blocked", "halted", "waiting_for_input"):
        _trace.route_decision("route_check_loop", "__end__", reason=f"status={state.get('status')}")
        return "__end__"
    if all_active_stages_done(state):
        _trace.route_decision("route_check_loop", "__end__", reason="all stages done")
        return "__end__"

    iteration = state.get("iteration", 0)
    max_iterations = state.get("config", {}).get("max_loop_iterations", 50)
    if iteration >= max_iterations:
        _trace.route_decision("route_check_loop", "__end__", reason=f"max iterations {iteration}/{max_iterations}")
        return "__end__"

    _trace.route_decision("route_check_loop", "continue_loop", reason=f"iteration {iteration}/{max_iterations}")
    return "continue_loop"


def route_blocked(state: dict[str, Any]) -> Literal["__end__"]:
    return "__end__"


def route_waiting_for_input(state: dict[str, Any]) -> Literal["__end__"]:
    """Waiting for user input is a terminal graph state.

    The CLI handles the interaction loop outside the graph.
    On resume, the graph is re-invoked from the blocked stage.
    """
    return "__end__"


def _find_next_stage(state: dict[str, Any]) -> str:
    next_sid = next_incomplete_stage(state)
    if not next_sid:
        return "__end__"
    return next_sid.replace(".", "-").replace("_", "-")


def route_init_complete(state: dict[str, Any]) -> str:
    if state.get("status") in ("blocked", "waiting_for_input"):
        _trace.route_decision("route_init_complete", "__end__", reason=f"status={state.get('status')}")
        return "__end__"
    _trace.route_decision("route_init_complete", "init-ideate", reason="init.setup done")
    return "init-ideate"


def route_design_complete(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        _trace.route_decision("route_design_complete", "arch-requirements", reason=f"complexity={complexity}")
        return "arch-requirements"
    _trace.route_decision("route_design_complete", "impl-design", reason=f"complexity={complexity}, skip arch")
    return "impl-design"


def route_arch_complete(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity == "complex":
        _trace.route_decision("route_arch_complete", "arch-review", reason=f"complexity={complexity}")
        return "arch-review"
    _trace.route_decision("route_arch_complete", "impl-design", reason=f"complexity={complexity}, skip review")
    return "impl-design"


def route_verify_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("verify", {}).get("done", False):
        _trace.route_decision("route_verify_result", "impl-code", reason="verify NOT DONE, rollback")
        return "impl-code"
    result = _post_verify_route(state)
    _trace.route_decision("route_verify_result", result, reason="verify DONE, advance")
    return result


def route_e2e_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("e2e.execute", {}).get("done", False):
        _trace.route_decision("route_e2e_result", "impl-code", reason="e2e NOT DONE, rollback")
        return "impl-code"
    result = _post_e2e_route(state)
    _trace.route_decision("route_e2e_result", result, reason="e2e DONE, advance")
    return result


def route_qa_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    current = state.get("current_stage", "")
    if not stages.get(current, {}).get("done", False):
        _trace.route_decision("route_qa_result", "impl-code", reason=f"qa stage {current} NOT DONE, rollback")
        return "impl-code"
    result = _next_qa_or_deploy(state)
    _trace.route_decision("route_qa_result", result, reason=f"qa stage {current} DONE, advance")
    return result


def route_deploy_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("deploy.prepare", {}).get("done", False):
        _trace.route_decision("route_deploy_result", "impl-code", reason="deploy NOT DONE, rollback")
        return "impl-code"
    ui_project = state.get("ui_project", False)
    if ui_project:
        _trace.route_decision("route_deploy_result", "smoke-test", reason="ui_project, run smoke")
        return "smoke-test"
    result = _post_deploy_route(state)
    _trace.route_decision("route_deploy_result", result, reason="deploy DONE, advance")
    return result


def route_smoke_result(state: dict[str, Any]) -> str:
    stages = state.get("stages", {})
    if not stages.get("smoke.test", {}).get("done", False):
        _trace.route_decision("route_smoke_result", "impl-code", reason="smoke NOT DONE, rollback")
        return "impl-code"
    result = _post_deploy_route(state)
    _trace.route_decision("route_smoke_result", result, reason="smoke DONE, advance")
    return result


def _post_verify_route(state: dict[str, Any]) -> str:
    return "qa-static"


def _post_e2e_route(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "qa-security"
    return "qa-human-flow"


def _next_qa_or_deploy(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    current = state.get("current_stage", "")
    if current == "qa.static":
        return "qa-unit"
    if current == "qa.unit" and complexity in ("medium", "large", "complex"):
        return "qa-integration"
    if current == "qa.unit":
        return "e2e-execute"
    if current == "qa.integration":
        return "e2e-execute"
    if current == "qa.security" and complexity == "complex":
        return "qa-performance"
    if current == "qa.security":
        return "qa-human-flow"
    if current == "qa.performance":
        return "qa-human-flow"
    if current == "qa.human-flow" and state.get("ui_project", False):
        return "qa-human-ux"
    if current == "qa.human-flow":
        return "deploy-prepare"
    if current == "qa.human-ux":
        return "deploy-prepare"
    return "deploy-prepare"


def _post_deploy_route(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "doc-decisions"
    return "post"

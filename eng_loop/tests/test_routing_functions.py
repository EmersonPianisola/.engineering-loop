from __future__ import annotations

from typing import Any

from eng_loop.routing import (
    _find_next_stage,
    _next_qa_or_deploy,
    _post_deploy_route,
    _post_e2e_route,
    _post_verify_route,
    route_after_essence,
    route_after_stage,
    route_arch_complete,
    route_blocked,
    route_check_loop,
    route_deploy_result,
    route_design_complete,
    route_e2e_result,
    route_init_complete,
    route_qa_result,
    route_smoke_result,
    route_verify_result,
)
from eng_loop.state import get_active_stages, init_stages


def _make_state(
    *,
    current_stage: str = "",
    complexity: str = "small",
    ui_project: bool = False,
    work_type: str = "feature",
    status: str = "running",
    iteration: int = 0,
    stages: dict[str, dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stages is None:
        stages = {}
    if config is None:
        config = {}
    base = init_stages()
    for k, v in stages.items():
        if k in base:
            base[k].update(v)
        else:
            base[k] = v
    return {
        "current_stage": current_stage,
        "complexity": complexity,
        "ui_project": ui_project,
        "work_type": work_type,
        "status": status,
        "iteration": iteration,
        "stages": base,
        "config": config,
    }


class TestRouteAfterEssence:
    def test_returns_node_name_dots_to_hyphens(self):
        state = _make_state(current_stage="init.ideate")
        assert route_after_essence(state) == "init-ideate"

    def test_returns_node_name_underscores_to_hyphens(self):
        state = _make_state(current_stage="qa.human_flow")
        assert route_after_essence(state) == "qa-human-flow"

    def test_returns_node_name_simple_stage(self):
        state = _make_state(current_stage="verify")
        assert route_after_essence(state) == "verify"

    def test_returns_end_for_empty_current_stage(self):
        state = _make_state(current_stage="")
        assert route_after_essence(state) == "__end__"

    def test_returns_end_for_missing_current_stage(self):
        state = _make_state()
        state.pop("current_stage")
        assert route_after_essence(state) == "__end__"


class TestRouteAfterStage:
    def test_retry_when_not_done_and_attempts_below_max(self):
        state = _make_state(
            current_stage="impl.code",
            stages={"impl.code": {"done": False, "attempts": 1}},
        )
        assert route_after_stage(state) == "impl-code"

    def test_next_stage_when_done(self):
        state = _make_state(
            current_stage="init",
            stages={"init": {"done": True, "attempts": 1}},
        )
        assert route_after_stage(state) == "init-ideate"

    def test_next_stage_when_max_attempts_reached(self):
        state = _make_state(
            current_stage="impl.code",
            complexity="small",
            stages={"impl.code": {"done": False, "attempts": 2}},
        )
        result = route_after_stage(state)
        assert result != "impl-code"

    def test_custom_max_attempts(self):
        state = _make_state(
            current_stage="impl.code",
            complexity="small",
            stages={"impl.code": {"done": False, "attempts": 3}},
            config={"constraints": {"max_impl_code_attempts": 4}},
        )
        assert route_after_stage(state) == "impl-code"

    def test_returns_end_for_empty_current_stage(self):
        state = _make_state(current_stage="")
        assert route_after_stage(state) == "__end__"

    def test_converts_stage_id_to_node_name(self):
        state = _make_state(
            current_stage="qa.human.flow",
            stages={"qa.human.flow": {"done": False, "attempts": 0}},
        )
        assert route_after_stage(state) == "qa-human-flow"


class TestRouteCheckLoop:
    def test_returns_end_when_blocked(self):
        state = _make_state(status="blocked")
        assert route_check_loop(state) == "__end__"

    def test_returns_end_when_halted(self):
        state = _make_state(status="halted")
        assert route_check_loop(state) == "__end__"

    def test_returns_end_when_all_stages_done(self):
        state = _make_state(complexity="small")
        for sid in get_active_stages("small", False):
            state["stages"][sid]["done"] = True
        assert route_check_loop(state) == "__end__"

    def test_returns_end_when_iteration_exceeds_max(self):
        state = _make_state(iteration=50, config={"max_loop_iterations": 50})
        assert route_check_loop(state) == "__end__"

    def test_returns_end_when_iteration_equals_max(self):
        state = _make_state(iteration=5, config={"max_loop_iterations": 5})
        assert route_check_loop(state) == "__end__"

    def test_returns_continue_loop_when_conditions_allow(self):
        state = _make_state(
            current_stage="impl.code",
            complexity="small",
            iteration=3,
            config={"max_loop_iterations": 50},
            stages={"impl.code": {"done": False, "attempts": 1}},
        )
        assert route_check_loop(state) == "continue_loop"

    def test_default_max_iterations_is_50(self):
        state = _make_state(
            current_stage="impl.code",
            complexity="small",
            iteration=49,
            stages={"impl.code": {"done": False, "attempts": 1}},
        )
        assert route_check_loop(state) == "continue_loop"

    def test_returns_end_at_default_max(self):
        state = _make_state(
            current_stage="impl.code",
            complexity="small",
            iteration=50,
            stages={"impl.code": {"done": False, "attempts": 1}},
        )
        assert route_check_loop(state) == "__end__"


class TestRouteBlocked:
    def test_always_returns_end(self):
        assert route_blocked({}) == "__end__"

    def test_returns_end_with_state(self):
        state = _make_state(status="blocked")
        assert route_blocked(state) == "__end__"


class TestRouteInitComplete:
    def test_returns_end_when_blocked(self):
        state = _make_state(status="blocked")
        assert route_init_complete(state) == "__end__"

    def test_returns_init_ideate_when_not_blocked(self):
        state = _make_state(status="running")
        assert route_init_complete(state) == "init-ideate"

    def test_returns_init_ideate_default_status(self):
        state = _make_state()
        assert route_init_complete(state) == "init-ideate"


class TestRouteDesignComplete:
    def test_returns_arch_requirements_for_medium(self):
        state = _make_state(complexity="medium")
        assert route_design_complete(state) == "arch-requirements"

    def test_returns_arch_requirements_for_large(self):
        state = _make_state(complexity="large")
        assert route_design_complete(state) == "arch-requirements"

    def test_returns_arch_requirements_for_complex(self):
        state = _make_state(complexity="complex")
        assert route_design_complete(state) == "arch-requirements"

    def test_returns_impl_design_for_small(self):
        state = _make_state(complexity="small")
        assert route_design_complete(state) == "impl-design"

    def test_returns_impl_design_for_default(self):
        state = _make_state()
        state.pop("complexity")
        assert route_design_complete(state) == "impl-design"


class TestRouteArchComplete:
    def test_returns_arch_review_for_complex(self):
        state = _make_state(complexity="complex")
        assert route_arch_complete(state) == "arch-review"

    def test_returns_impl_design_for_small(self):
        state = _make_state(complexity="small")
        assert route_arch_complete(state) == "impl-design"

    def test_returns_impl_design_for_medium(self):
        state = _make_state(complexity="medium")
        assert route_arch_complete(state) == "impl-design"

    def test_returns_impl_design_for_large(self):
        state = _make_state(complexity="large")
        assert route_arch_complete(state) == "impl-design"


class TestRouteVerifyResult:
    def test_returns_impl_code_when_verify_not_done(self):
        state = _make_state(stages={"verify": {"done": False}})
        assert route_verify_result(state) == "impl-code"

    def test_returns_post_verify_route_when_done(self):
        state = _make_state(
            complexity="small",
            ui_project=False,
            stages={"verify": {"done": True}},
        )
        assert route_verify_result(state) == "qa-static"

    def test_returns_qa_static_for_ui_project(self):
        state = _make_state(
            complexity="small",
            ui_project=True,
            stages={"verify": {"done": True}},
        )
        assert route_verify_result(state) == "qa-static"

    def test_returns_qa_static_for_medium(self):
        state = _make_state(
            complexity="medium",
            ui_project=False,
            stages={"verify": {"done": True}},
        )
        assert route_verify_result(state) == "qa-static"


class TestRouteE2eResult:
    def test_returns_impl_code_when_e2e_not_done(self):
        state = _make_state(stages={"e2e.execute": {"done": False}})
        assert route_e2e_result(state) == "impl-code"

    def test_returns_qa_human_flow_for_small(self):
        state = _make_state(
            complexity="small",
            stages={"e2e.execute": {"done": True}},
        )
        assert route_e2e_result(state) == "qa-human-flow"

    def test_returns_qa_security_for_medium(self):
        state = _make_state(
            complexity="medium",
            stages={"e2e.execute": {"done": True}},
        )
        assert route_e2e_result(state) == "qa-security"

    def test_returns_qa_security_for_complex(self):
        state = _make_state(
            complexity="complex",
            stages={"e2e.execute": {"done": True}},
        )
        assert route_e2e_result(state) == "qa-security"


class TestRouteQaResult:
    def test_returns_impl_code_when_qa_not_done(self):
        state = _make_state(
            current_stage="qa.security",
            stages={"qa.security": {"done": False}},
        )
        assert route_qa_result(state) == "impl-code"

    def test_returns_next_qa_or_deploy_when_done(self):
        state = _make_state(
            current_stage="qa.security",
            complexity="medium",
            stages={"qa.security": {"done": True}},
        )
        assert route_qa_result(state) == "qa-human-flow"

    def test_returns_human_flow_for_small(self):
        state = _make_state(
            current_stage="qa.security",
            complexity="small",
            stages={"qa.security": {"done": True}},
        )
        assert route_qa_result(state) == "qa-human-flow"

    def test_returns_qa_performance_from_security_complex(self):
        state = _make_state(
            current_stage="qa.security",
            complexity="complex",
            stages={"qa.security": {"done": True}},
        )
        assert route_qa_result(state) == "qa-performance"

    def test_returns_human_flow_from_performance(self):
        state = _make_state(
            current_stage="qa.performance",
            complexity="complex",
            stages={"qa.performance": {"done": True}},
        )
        assert route_qa_result(state) == "qa-human-flow"


class TestRouteDeployResult:
    def test_returns_impl_code_when_deploy_not_done(self):
        state = _make_state(stages={"deploy.prepare": {"done": False}})
        assert route_deploy_result(state) == "impl-code"

    def test_returns_smoke_test_for_ui_project(self):
        state = _make_state(
            ui_project=True,
            stages={"deploy.prepare": {"done": True}},
        )
        assert route_deploy_result(state) == "smoke-test"

    def test_returns_post_deploy_route_for_non_ui(self):
        state = _make_state(
            ui_project=False,
            complexity="small",
            stages={"deploy.prepare": {"done": True}},
        )
        assert route_deploy_result(state) == "post"

    def test_returns_doc_decisions_for_medium(self):
        state = _make_state(
            ui_project=False,
            complexity="medium",
            stages={"deploy.prepare": {"done": True}},
        )
        assert route_deploy_result(state) == "doc-decisions"


class TestRouteSmokeResult:
    def test_returns_impl_code_when_smoke_not_done(self):
        state = _make_state(stages={"smoke.test": {"done": False}})
        assert route_smoke_result(state) == "impl-code"

    def test_returns_post_deploy_route_when_done(self):
        state = _make_state(
            complexity="small",
            stages={"smoke.test": {"done": True}},
        )
        assert route_smoke_result(state) == "post"

    def test_returns_doc_decisions_for_medium(self):
        state = _make_state(
            complexity="medium",
            stages={"smoke.test": {"done": True}},
        )
        assert route_smoke_result(state) == "doc-decisions"


class TestPostVerifyRoute:
    def test_returns_qa_static_for_ui_project(self):
        state = _make_state(ui_project=True, complexity="small")
        assert _post_verify_route(state) == "qa-static"

    def test_returns_qa_static_for_ui_project_regardless_complexity(self):
        state = _make_state(ui_project=True, complexity="complex")
        assert _post_verify_route(state) == "qa-static"

    def test_returns_qa_static_for_medium(self):
        state = _make_state(ui_project=False, complexity="medium")
        assert _post_verify_route(state) == "qa-static"

    def test_returns_qa_static_for_large(self):
        state = _make_state(ui_project=False, complexity="large")
        assert _post_verify_route(state) == "qa-static"

    def test_returns_qa_static_for_complex(self):
        state = _make_state(ui_project=False, complexity="complex")
        assert _post_verify_route(state) == "qa-static"

    def test_returns_qa_static_for_small(self):
        state = _make_state(ui_project=False, complexity="small")
        assert _post_verify_route(state) == "qa-static"


class TestPostE2eRoute:
    def test_returns_qa_security_for_medium(self):
        state = _make_state(complexity="medium")
        assert _post_e2e_route(state) == "qa-security"

    def test_returns_qa_security_for_large(self):
        state = _make_state(complexity="large")
        assert _post_e2e_route(state) == "qa-security"

    def test_returns_qa_security_for_complex(self):
        state = _make_state(complexity="complex")
        assert _post_e2e_route(state) == "qa-security"

    def test_returns_qa_human_flow_for_small(self):
        state = _make_state(complexity="small")
        assert _post_e2e_route(state) == "qa-human-flow"


class TestNextQaOrDeploy:
    def test_from_qa_static_returns_qa_unit(self):
        state = _make_state(current_stage="qa.static", complexity="medium")
        assert _next_qa_or_deploy(state) == "qa-unit"

    def test_from_qa_unit_medium_returns_integration(self):
        state = _make_state(current_stage="qa.unit", complexity="medium")
        assert _next_qa_or_deploy(state) == "qa-integration"

    def test_from_qa_unit_small_returns_e2e(self):
        state = _make_state(current_stage="qa.unit", complexity="small")
        assert _next_qa_or_deploy(state) == "e2e-execute"

    def test_from_qa_integration_returns_e2e(self):
        state = _make_state(current_stage="qa.integration", complexity="medium")
        assert _next_qa_or_deploy(state) == "e2e-execute"

    def test_from_qa_security_complex_returns_performance(self):
        state = _make_state(current_stage="qa.security", complexity="complex")
        assert _next_qa_or_deploy(state) == "qa-performance"

    def test_from_qa_security_medium_returns_human_flow(self):
        state = _make_state(current_stage="qa.security", complexity="medium")
        assert _next_qa_or_deploy(state) == "qa-human-flow"

    def test_from_qa_performance_returns_human_flow(self):
        state = _make_state(current_stage="qa.performance", complexity="complex")
        assert _next_qa_or_deploy(state) == "qa-human-flow"

    def test_from_qa_human_flow_ui_returns_ux(self):
        state = _make_state(current_stage="qa.human-flow", ui_project=True)
        assert _next_qa_or_deploy(state) == "qa-human-ux"

    def test_from_qa_human_flow_non_ui_returns_deploy(self):
        state = _make_state(current_stage="qa.human-flow", ui_project=False)
        assert _next_qa_or_deploy(state) == "deploy-prepare"

    def test_from_qa_human_ux_returns_deploy(self):
        state = _make_state(current_stage="qa.human-ux", ui_project=True)
        assert _next_qa_or_deploy(state) == "deploy-prepare"

    def test_from_empty_stage_returns_deploy(self):
        state = _make_state(current_stage="", complexity="complex")
        assert _next_qa_or_deploy(state) == "deploy-prepare"


class TestPostDeployRoute:
    def test_returns_doc_decisions_for_medium(self):
        state = _make_state(complexity="medium")
        assert _post_deploy_route(state) == "doc-decisions"

    def test_returns_doc_decisions_for_large(self):
        state = _make_state(complexity="large")
        assert _post_deploy_route(state) == "doc-decisions"

    def test_returns_doc_decisions_for_complex(self):
        state = _make_state(complexity="complex")
        assert _post_deploy_route(state) == "doc-decisions"

    def test_returns_post_for_small(self):
        state = _make_state(complexity="small")
        assert _post_deploy_route(state) == "post"


class TestFindNextStage:
    def test_returns_next_incomplete_stage(self):
        state = _make_state(
            complexity="small",
            stages={"init": {"done": True}},
        )
        assert _find_next_stage(state) == "init-ideate"

    def test_returns_next_incomplete_with_dot_conversion(self):
        state = _make_state(
            complexity="small",
            stages={
                "init": {"done": True},
                "init.ideate": {"done": True},
            },
        )
        assert _find_next_stage(state) == "init-refine"

    def test_returns_end_when_all_complete(self):
        state = _make_state(complexity="small")
        for sid in get_active_stages("small", False):
            state["stages"][sid]["done"] = True
        assert _find_next_stage(state) == "__end__"

    def test_skips_inactive_stages(self):
        state = _make_state(
            complexity="small",
            stages={
                "init": {"done": True},
                "init.ideate": {"done": True},
            },
        )
        assert _find_next_stage(state) != "init-bdd"

    def test_handles_underscore_conversion(self):
        state = _make_state(
            complexity="medium",
            stages={s: {"done": True} for s in get_active_stages("medium", False) if s != "qa.api-contract"},
        )
        assert _find_next_stage(state) == "qa-api-contract"

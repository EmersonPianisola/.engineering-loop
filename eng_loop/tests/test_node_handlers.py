from __future__ import annotations

from langgraph.types import Command

from eng_loop.node_registry import build_registry
from eng_loop.state import make_initial_state


def _make_state(complexity: str = "small", ui_project: bool = False, work_type: str = "feature") -> dict:
    return make_initial_state(
        {"constraints": {}},
        {"project_root": ".", "artifact_root": ""},
    ) | {
        "complexity": complexity,
        "ui_project": ui_project,
        "work_type": work_type,
    }


def _mark_done(state: dict, stage_id: str) -> dict:
    stages = dict(state["stages"])
    stages[stage_id] = dict(stages.get(stage_id, {}), done=True)
    return dict(state, stages=stages)


# ============================================================
# INIT NODE HANDLERS
# ============================================================


class TestInitBddNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("init.bdd")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("init.bdd")
        state = _mark_done(_make_state("large"), "init.bdd")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestInitHelpers:
    def test_next_phase_node_small(self):
        from eng_loop.nodes.init import _next_phase_node

        state = _make_state("small")
        assert _next_phase_node(state) == "impl-design"

    def test_next_phase_node_medium(self):
        from eng_loop.nodes.init import _next_phase_node

        state = _make_state("medium")
        assert _next_phase_node(state) == "arch-requirements"

    def test_next_phase_node_large(self):
        from eng_loop.nodes.init import _next_phase_node

        state = _make_state("large")
        assert _next_phase_node(state) == "arch-requirements"

    def test_resolve_work_item_plain_string(self):
        from eng_loop.nodes.init import _resolve_work_item

        assert _resolve_work_item("  fix login bug  ") == "fix login bug"

    def test_resolve_work_item_quoted(self):
        from eng_loop.nodes.init import _resolve_work_item

        assert _resolve_work_item('"add dark mode"') == "add dark mode"


# ============================================================
# DESIGN NODE HANDLERS
# ============================================================


class TestDesignUserResearchNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("design.user-research")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("design.user-research")
        state = _mark_done(_make_state("large"), "design.user-research")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDesignPersonasNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("design.personas")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("design.personas")
        state = _mark_done(_make_state("large"), "design.personas")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDesignInfoArchNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("design.info-arch")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("design.info-arch")
        state = _mark_done(_make_state("large"), "design.info-arch")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDesignInteractionNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("design.interaction")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("design.interaction")
        state = _mark_done(_make_state("large"), "design.interaction")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDesignDesignSystemNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("design.design-system")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("design.design-system")
        state = _mark_done(_make_state("large"), "design.design-system")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDesignVisualDesignNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("design.visual-design")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("design.visual-design")
        state = _mark_done(_make_state("large"), "design.visual-design")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDesignHelpers:
    def test_resolve_next_user_research(self):
        from eng_loop.nodes.design import _resolve_next

        state = _make_state("large")
        assert _resolve_next("design.user-research", state) == "design-personas"

    def test_resolve_next_personas(self):
        from eng_loop.nodes.design import _resolve_next

        state = _make_state("large")
        assert _resolve_next("design.personas", state) == "design-info-arch"

    def test_resolve_next_info_arch(self):
        from eng_loop.nodes.design import _resolve_next

        state = _make_state("large")
        assert _resolve_next("design.info-arch", state) == "design-interaction"

    def test_resolve_next_interaction(self):
        from eng_loop.nodes.design import _resolve_next

        state = _make_state("large")
        assert _resolve_next("design.interaction", state) == "design-design-system"

    def test_resolve_next_design_system(self):
        from eng_loop.nodes.design import _resolve_next

        state = _make_state("large")
        assert _resolve_next("design.design-system", state) == "design-visual-design"

    def test_resolve_next_visual_design_small(self):
        from eng_loop.nodes.design import _resolve_next

        state = _make_state("small")
        result = _resolve_next("design.visual-design", state)
        assert result in ("impl-design", "__end__")

    def test_post_design_small(self):
        from eng_loop.nodes.design import _post_design

        state = _make_state("small")
        assert _post_design(state) == "impl-design"

    def test_post_design_medium(self):
        from eng_loop.nodes.design import _post_design

        state = _make_state("medium")
        assert _post_design(state) == "arch-requirements"

    def test_post_design_large(self):
        from eng_loop.nodes.design import _post_design

        state = _make_state("large")
        assert _post_design(state) == "arch-requirements"

    def test_get_design_nodes(self):
        from eng_loop.nodes.design import get_design_nodes

        nodes = get_design_nodes()
        assert len(nodes) == 6
        assert ("design-user-research", "design.user-research") in nodes
        assert ("design-visual-design", "design.visual-design") in nodes


# ============================================================
# ARCHITECTURE NODE HANDLERS
# ============================================================


class TestArchRequirementsNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("arch.requirements")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("arch.requirements")
        state = _mark_done(_make_state("medium"), "arch.requirements")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestArchSolutionNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("arch.solution")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("arch.solution")
        state = _mark_done(_make_state("medium"), "arch.solution")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestArchReviewNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("arch.review")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("arch.review")
        state = _mark_done(_make_state("complex"), "arch.review")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestArchitectureHelpers:
    def test_resolve_next_requirements(self):
        from eng_loop.nodes.architecture import _resolve_next

        state = _make_state("medium")
        assert _resolve_next("arch.requirements", state) == "arch-solution"

    def test_resolve_next_solution_medium(self):
        from eng_loop.nodes.architecture import _resolve_next

        state = _make_state("medium")
        assert _resolve_next("arch.solution", state) == "impl-design"

    def test_resolve_next_solution_complex(self):
        from eng_loop.nodes.architecture import _resolve_next

        state = _make_state("complex")
        assert _resolve_next("arch.solution", state) == "arch-review"

    def test_resolve_next_review(self):
        from eng_loop.nodes.architecture import _resolve_next

        state = _make_state("complex")
        assert _resolve_next("arch.review", state) == "impl-design"

    def test_build_arch_context_requirements(self):
        from eng_loop.nodes.architecture import _build_arch_context

        state = _make_state("medium")
        result = _build_arch_context("arch.requirements", state)
        assert "No prior architecture artifacts." in result

    def test_build_arch_context_solution_with_artifacts(self):
        from eng_loop.nodes.architecture import _build_arch_context

        state = _make_state("medium") | {"stage_artifacts": {"arch.requirements": "req content"}}
        result = _build_arch_context("arch.solution", state)
        assert "## Requirements" in result
        assert "req content" in result

    def test_build_arch_context_review_with_artifacts(self):
        from eng_loop.nodes.architecture import _build_arch_context

        state = _make_state("complex") | {
            "stage_artifacts": {
                "arch.requirements": "req content",
                "arch.solution": "sol content",
            }
        }
        result = _build_arch_context("arch.review", state)
        assert "## Requirements" in result
        assert "## Solution" in result

    def test_get_arch_nodes(self):
        from eng_loop.nodes.architecture import get_arch_nodes

        nodes = get_arch_nodes()
        assert len(nodes) == 3
        assert ("arch-requirements", "arch.requirements") in nodes
        assert ("arch-review", "arch.review") in nodes


# ============================================================
# VERIFICATION NODE HANDLERS
# ============================================================


class TestE2eExecuteNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("e2e.execute")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("e2e.execute")
        state = _mark_done(_make_state("small", ui_project=True), "e2e.execute")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestVerificationHelpers:
    def test_post_verify_ui_project(self):
        from eng_loop.nodes.verification import _post_verify

        state = _make_state("small", ui_project=True)
        assert _post_verify(state) == "e2e-execute"

    def test_post_verify_small_no_ui(self):
        from eng_loop.nodes.verification import _post_verify

        state = _make_state("small", ui_project=False)
        assert _post_verify(state) == "deploy-prepare"

    def test_post_verify_medium_no_ui(self):
        from eng_loop.nodes.verification import _post_verify

        state = _make_state("medium", ui_project=False)
        assert _post_verify(state) == "qa-security"

    def test_post_e2e_small(self):
        from eng_loop.nodes.verification import _post_e2e

        state = _make_state("small", ui_project=True)
        assert _post_e2e(state) == "deploy-prepare"

    def test_post_e2e_medium(self):
        from eng_loop.nodes.verification import _post_e2e

        state = _make_state("medium", ui_project=True)
        assert _post_e2e(state) == "qa-security"


# ============================================================
# QA NODE HANDLERS
# ============================================================


class TestQaPerformanceNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("qa.performance")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("qa.performance")
        state = _mark_done(_make_state("complex"), "qa.performance")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestQaHelpers:
    def test_resolve_next_qa_security_medium(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("medium")
        assert _resolve_next_qa("qa.security", state) == "qa-human-flow"

    def test_resolve_next_qa_security_complex(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("complex")
        assert _resolve_next_qa("qa.security", state) == "qa-performance"

    def test_resolve_next_qa_security_small(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("small")
        assert _resolve_next_qa("qa.security", state) == "deploy-prepare"

    def test_resolve_next_qa_api_contract_complex(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("complex")
        assert _resolve_next_qa("qa.api-contract", state) == "qa-performance"

    def test_resolve_next_qa_api_contract_medium(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("medium")
        assert _resolve_next_qa("qa.api-contract", state) == "deploy-prepare"

    def test_resolve_next_qa_performance(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("complex")
        assert _resolve_next_qa("qa.performance", state) == "qa-human-flow"

    def test_resolve_next_qa_human_flow_ui(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("medium")
        state["ui_project"] = True
        assert _resolve_next_qa("qa.human.flow", state) == "qa-human-ux"

    def test_resolve_next_qa_human_flow_non_ui(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("medium")
        state["ui_project"] = False
        assert _resolve_next_qa("qa.human.flow", state) == "deploy-prepare"

    def test_resolve_next_qa_human_ux(self):
        from eng_loop.nodes.qa import _resolve_next_qa

        state = _make_state("medium")
        assert _resolve_next_qa("qa.human.ux", state) == "deploy-prepare"

    def test_get_qa_nodes(self):
        from eng_loop.nodes.qa import get_qa_nodes

        nodes = get_qa_nodes()
        assert len(nodes) == 8
        assert ("qa-security", "qa.security") in nodes
        assert ("qa-performance", "qa.performance") in nodes


# ============================================================
# DEPLOY NODE HANDLERS
# ============================================================


class TestSmokeTestNode:
    def test_handler_callable(self):
        registry = build_registry()
        spec = registry.get("smoke.test")
        assert spec is not None
        assert callable(spec.handler)

    def test_done_path_returns_command(self):
        registry = build_registry()
        spec = registry.get("smoke.test")
        state = _mark_done(_make_state("small", ui_project=True), "smoke.test")
        result = spec.handler(state)
        assert isinstance(result, Command)
        assert hasattr(result, "goto")
        assert hasattr(result, "update")


class TestDeployHelpers:
    def test_post_deploy_ui_project(self):
        from eng_loop.nodes.deploy import _post_deploy

        state = _make_state("small", ui_project=True)
        assert _post_deploy(state) == "smoke-test"

    def test_post_deploy_small_no_ui(self):
        from eng_loop.nodes.deploy import _post_deploy

        state = _make_state("small", ui_project=False)
        assert _post_deploy(state) == "post"

    def test_post_deploy_medium_no_ui(self):
        from eng_loop.nodes.deploy import _post_deploy

        state = _make_state("medium", ui_project=False)
        assert _post_deploy(state) == "doc-decisions"


# ============================================================
# ESSENCE HELPERS
# ============================================================

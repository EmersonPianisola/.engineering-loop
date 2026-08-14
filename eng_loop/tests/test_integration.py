from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from langgraph.types import Command

from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import build_registry
from eng_loop.routing import (
    route_after_stage,
    route_blocked,
    route_check_loop,
    route_deploy_result,
    route_qa_result,
    route_verify_result,
)
from eng_loop.state import (
    STAGE_ORDER,
    get_active_stages,
    init_stages,
    is_stage_active,
    make_initial_state,
    next_incomplete_stage,
)
from eng_loop.tools.agent_runner import AgentResult
from eng_loop.tools.autosizing import (
    DOCUMENTATION_EXCLUDED_STAGES,
    OPERATIONAL_EXCLUDED_STAGES,
    deactivate_for_work_type,
)
from eng_loop.tools.next_active import _is_active, resolve_next

_MOCK_DATA = {
    "valid": True,
    "complete": True,
    "work_item_refined": "refined work item for implementation",
    "ideation_results": "Comprehensive ideation analysis covering all requirements and implementation approach",
    "decomposed_tasks": ["task1", "task2"],
    "blueprint": "Implementation blueprint with detailed architecture and task breakdown",
    "tasks": ["task1", "task2"],
    "file_structure": ["src/main.py", "tests/test_main.py"],
    "implementation_summary": "Implemented the feature with comprehensive test coverage and full documentation",
    "files_created": ["file1.py", "test_file1.py"],
    "tests_passed": True,
    "verdict": "PASS",
    "per_ac_evidence": ["AC1 -> file.py:10", "AC2 -> file.py:20"],
    "discrimination_sensor": "pass",
    "coverage_audit": "pass",
    "gaps": [],
    "refined_work_item": "refined specification ready for architecture phase",
    "ready_for_architecture": True,
    "journey_map": "User journey mapped with key touchpoints identified",
    "gherkin_scenarios": ["Scenario: user login"],
    "architecture_output": "Architecture design documented with key decisions",
    "design_output": "Design artifacts created for all personas",
    "findings": [],
    "critical_findings": [],
    "build_status": "pass",
    "lint_status": "pass",
    "type_check_status": "pass",
    "errors": [],
    "test_results": ["all tests passed"],
    "console_errors": 0,
    "network_errors": 0,
    "critical_paths": ["login flow verified"],
    "decision_log": "Decisions consolidated",
    "decisions_count": 3,
    "readme": "README content",
    "summary": "Loop completed successfully",
    "lessons_to_share": 2,
    "final_status": "done",
}


def _make_state(
    complexity: str = "small",
    ui_project: bool = False,
    work_type: str = "feature",
    work_item: str = "Add new feature",
    config: dict | None = None,
    paths: dict | None = None,
) -> dict:
    tmpdir = tempfile.mkdtemp()
    artifact_root = str(Path(tmpdir) / "artifacts")
    return make_initial_state(
        config or {"constraints": {}},
        paths or {"project_root": tmpdir, "artifact_root": artifact_root},
    ) | {
        "complexity": complexity,
        "ui_project": ui_project,
        "work_type": work_type,
        "work_item": work_item,
        "_tmpdir": tmpdir,
    }


def _mark_done(state: dict, stage_id: str) -> dict:
    stages = {k: dict(v) for k, v in state["stages"].items()}
    stages[stage_id] = dict(stages[stage_id], done=True, attempts=max(stages[stage_id].get("attempts", 0), 1))
    return dict(state, stages=stages, current_stage=stage_id)


def _set_attempts(state: dict, stage_id: str, attempts: int) -> dict:
    stages = {k: dict(v) for k, v in state["stages"].items()}
    stages[stage_id] = dict(stages[stage_id], attempts=attempts)
    return dict(state, stages=stages)


def _apply_update(state: dict, update: dict) -> dict:
    result = dict(state)
    for k, v in update.items():
        if k == "stages" and isinstance(v, dict):
            merged = {sk: dict(sv) for sk, sv in state.get("stages", {}).items()}
            for sk, sv in v.items():
                if isinstance(sv, dict):
                    merged[sk] = dict(merged.get(sk, {}), **sv)
                else:
                    merged[sk] = sv
            result[k] = merged
        else:
            result[k] = v
    return result


def _mark_all_done_before(state: dict, stage_id: str) -> dict:
    idx = STAGE_ORDER.index(stage_id) if stage_id in STAGE_ORDER else 0
    result = state
    for i in range(idx):
        result = _mark_done(result, STAGE_ORDER[i])
    return result


def test_small_feature_flow():
    mock_result = AgentResult(data=_MOCK_DATA)
    with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
        from eng_loop.nodes.init import init_node

        state = _make_state("small", False, "feature")
        result = init_node(state)
        assert isinstance(result, Command)
        assert result.goto == "init-ideate"
        updated = _apply_update(state, result.update or {})
        assert updated["complexity"] == "small"
        assert updated["stages"]["init"]["done"] is True
        assert updated["stages"]["init.bdd"]["done"] is True

        from eng_loop.nodes.init import init_ideate_node

        result = init_ideate_node(updated)
        assert isinstance(result, Command)
        assert result.goto == "init-refine"

        from eng_loop.nodes.init import init_refine_node

        state2 = _apply_update(updated, result.update or {})
        result = init_refine_node(state2)
        assert isinstance(result, Command)
        assert result.goto == "impl-design"

        from eng_loop.nodes.implementation import impl_design_node

        state3 = _apply_update(state2, result.update or {})
        result = impl_design_node(state3)
        assert isinstance(result, Command)
        assert result.goto == "impl-code"

        from eng_loop.nodes.implementation import impl_code_node

        state4 = _apply_update(state3, result.update or {})
        result = impl_code_node(state4)
        assert isinstance(result, Command)
        assert result.goto == "doc-update"

        from eng_loop.nodes.implementation import doc_update_node

        state5 = _apply_update(state4, result.update or {})
        result = doc_update_node(state5)
        assert isinstance(result, Command)
        assert result.goto == "verify"

        state6 = _apply_update(state5, result.update or {})
        with patch("eng_loop.tools.file_ops.write_file"):
            from eng_loop.nodes.verification import verify_node

            result = verify_node(state6)
            assert isinstance(result, Command)
            assert result.goto == "deploy-prepare"

        from eng_loop.nodes.deploy import deploy_prepare_node

        state7 = _apply_update(state6, result.update or {})
        result = deploy_prepare_node(state7)
        assert isinstance(result, Command)
        assert result.goto == "post"

        from eng_loop.nodes.post import post_node

        state8 = _apply_update(state7, result.update or {})
        result = post_node(state8)
        assert isinstance(result, Command)
        assert result.goto == "__end__"


def test_medium_feature_flow():
    mock_result = AgentResult(data=_MOCK_DATA)
    with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
        from eng_loop.nodes.init import init_node

        state = _make_state("medium", False, "feature")
        result = init_node(state)
        assert isinstance(result, Command)
        assert result.goto == "init-ideate"
        updated = _apply_update(state, result.update or {})
        assert updated["complexity"] == "medium"

        from eng_loop.nodes.architecture import arch_node

        state2 = _mark_done(updated, "init")
        state2 = _mark_done(state2, "init.ideate")
        state2 = _mark_done(state2, "init.refine")
        state2["stages"]["arch.requirements"] = dict(state2["stages"]["arch.requirements"], done=False, attempts=0)
        state2["current_stage"] = "arch.requirements"

        arch_req_handler = arch_node("arch.requirements")
        result = arch_req_handler(state2)
        assert isinstance(result, Command)
        assert result.goto == "arch-solution"

        arch_sol_handler = arch_node("arch.solution")
        state3 = _apply_update(state2, result.update or {})
        state3 = _mark_done(state3, "arch.requirements")
        state3["current_stage"] = "arch.solution"
        result = arch_sol_handler(state3)
        assert isinstance(result, Command)
        assert result.goto == "impl-design"

        active = get_active_stages("medium", False)
        assert "arch.requirements" in active
        assert "arch.solution" in active
        assert "qa.security" in active
        assert "qa.api-contract" in active
        assert "doc.decisions" in active
        assert "doc.project" in active
        assert "arch.review" not in active
        assert "qa.performance" not in active

        state_verify = _make_state("medium", False)
        state_verify = _mark_done(state_verify, "verify")
        route = route_verify_result(state_verify)
        assert route == "qa-security"

        state_qa = _make_state("medium", False)
        state_qa = _mark_done(state_qa, "qa.security")
        state_qa["current_stage"] = "qa.security"
        route = route_qa_result(state_qa)
        assert route == "qa-api-contract"

        state_deploy = _make_state("medium", False)
        state_deploy = _mark_done(state_deploy, "qa.api-contract")
        state_deploy["current_stage"] = "qa.api-contract"
        route = route_qa_result(state_deploy)
        assert route == "deploy-prepare"

        state_doc = _make_state("medium", False)
        state_doc = _mark_done(state_doc, "deploy.prepare")
        route = route_deploy_result(state_doc)
        assert route == "doc-decisions"


def test_documentation_work_flow():
    state = _make_state("small", False, "documentation")
    active = get_active_stages("small", False, "documentation")
    assert "init" in active
    assert "init.ideate" in active
    assert "init.refine" in active
    assert "impl.code" in active
    assert "post" in active
    assert "impl.design" not in active
    assert "verify" not in active
    assert "deploy.prepare" not in active
    assert "arch.requirements" not in active

    for sid in DOCUMENTATION_EXCLUDED_STAGES:
        assert sid not in active

    stages = deactivate_for_work_type(init_stages(), "documentation")
    assert stages["impl.design"]["done"] is True
    assert stages["verify"]["done"] is True
    assert stages["deploy.prepare"]["done"] is True
    assert stages["impl.code"]["done"] is False
    assert stages["init"]["done"] is False

    next_stage = next_incomplete_stage(state)
    assert next_stage == "init"

    mock_result = AgentResult(data=_MOCK_DATA)
    with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
        from eng_loop.nodes.init import init_node

        result = init_node(state)
        assert isinstance(result, Command)
        assert result.goto == "init-ideate"

        registry = build_registry()
        active_specs = registry.filter(complexity="small", ui_project=False, work_type="documentation")
        active_ids = {s.id for s in active_specs}
        assert "impl.design" not in active_ids
        assert "verify" not in active_ids
        assert "deploy.prepare" not in active_ids
        assert "init" in active_ids
        assert "impl.code" in active_ids
        assert "post" in active_ids


def test_operational_work_flow():
    state = _make_state("small", False, "operational")
    active = get_active_stages("small", False, "operational")
    assert "init" in active
    assert "init.ideate" in active
    assert "init.refine" in active
    assert "post" in active
    assert "impl.code" not in active
    assert "impl.design" not in active
    assert "verify" not in active
    assert "arch.requirements" not in active

    for sid in OPERATIONAL_EXCLUDED_STAGES:
        assert sid not in active

    stages = deactivate_for_work_type(init_stages(), "operational")
    assert stages["impl.code"]["done"] is True
    assert stages["impl.design"]["done"] is True
    assert stages["verify"]["done"] is True
    assert stages["init"]["done"] is False
    assert stages["post"]["done"] is False

    for sid in OPERATIONAL_EXCLUDED_STAGES:
        assert is_stage_active(sid, "small", False, "operational") is False

    assert is_stage_active("init", "small", False, "operational") is True
    assert is_stage_active("post", "small", False, "operational") is True
    assert is_stage_active("impl.code", "small", False, "operational") is False

    mock_result = AgentResult(data=_MOCK_DATA)
    with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
        from eng_loop.nodes.init import init_node

        result = init_node(state)
        assert isinstance(result, Command)
        assert result.goto == "init-ideate"


def test_verify_fail_loopback():
    state = _make_state("small", False, "feature")
    state = _mark_done(state, "impl.code")
    state = _mark_done(state, "doc.update")
    state["stages"]["verify"] = dict(state["stages"]["verify"], done=False, attempts=1)
    state["current_stage"] = "verify"

    route = route_verify_result(state)
    assert route == "impl-code"

    fail_data = dict(_MOCK_DATA)
    fail_data["verdict"] = "FAIL"
    fail_data["gaps"] = ["missing test coverage for edge case"]
    mock_fail = AgentResult(data=fail_data)

    with (
        patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_fail),
        patch("eng_loop.tools.file_ops.write_file"),
    ):
        from eng_loop.nodes.verification import verify_node

        result = verify_node(state)
        assert isinstance(result, Command)
        assert result.goto == "impl-code"

        update = result.update or {}
        impl_code_stage = update.get("stages", {}).get("impl.code", {})
        assert impl_code_stage.get("done") is False


def test_blocked_max_attempts():
    state = _make_state("small", False, "feature")
    state["config"] = {"constraints": {"max_impl_code_attempts": 2}}
    state = _set_attempts(state, "impl.code", 3)
    state["stages"]["impl.code"]["done"] = False
    state["current_stage"] = "impl.code"

    state = _mark_all_done_before(state, "impl.code")
    state["stages"]["impl.code"] = dict(state["stages"]["impl.code"], done=False, attempts=3)
    state["current_stage"] = "impl.code"

    route = route_after_stage(state)
    assert route == "impl-code"

    state["status"] = "blocked"
    state["blocking_condition"] = "max attempts exceeded for impl.code"
    check = route_check_loop(state)
    assert check == "__end__"

    blocked = route_blocked(state)
    assert blocked == "__end__"


def test_small_complexity_bypasses_bdd():
    state = _make_state("small", False, "feature")
    assert is_stage_active("init.bdd", "small", False) is False
    assert _is_active("init.bdd", state) is False

    resolved = resolve_next("init-bdd", state)
    assert resolved == "init-refine"

    active = get_active_stages("small", False)
    assert "init.bdd" not in active
    assert "init.ideate" in active
    assert "init.refine" in active

    resolved_from_ideate = resolve_next("init-ideate", state)
    assert resolved_from_ideate == "init-ideate"

    registry = build_registry()
    active_specs = registry.filter(complexity="small", ui_project=False)
    active_ids = {s.id for s in active_specs}
    assert "init.bdd" not in active_ids

    from eng_loop.edge_rules import build_edge_rules

    engine = build_edge_rules()
    active_node_names = {s.node_name for s in active_specs} | {"__start__"}
    resolved_rules = engine.resolve_with_bypass(active_node_names, state)
    bypass_rules = [r for r in resolved_rules if r.edge_type == "bypass"]
    assert any(r.from_node == "init-ideate" and r.to_node == "init-refine" for r in bypass_rules)


def test_state_persistence_save_resume():
    state = _make_state("medium", True, "feature", "Build dashboard")
    state["stages"]["init"]["done"] = True
    state["stages"]["init"]["attempts"] = 1
    state["decisions"] = ["AD-001: Use React"]
    state["stage_artifacts"] = {"init": "init output"}
    state["errors"] = ["timeout on first attempt"]
    state["handoffs"] = {"init": "handoff data from init"}
    state["timing"] = {"init": {"start": 0, "end": 5}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(state, f, indent=2, default=str)
        tmp_path = f.name

    try:
        with open(tmp_path, "r") as f:
            loaded = json.load(f)

        assert loaded["complexity"] == "medium"
        assert loaded["ui_project"] is True
        assert loaded["work_type"] == "feature"
        assert loaded["work_item"] == "Build dashboard"
        assert loaded["stages"]["init"]["done"] is True
        assert loaded["stages"]["init"]["attempts"] == 1
        assert loaded["decisions"] == ["AD-001: Use React"]
        assert loaded["stage_artifacts"]["init"] == "init output"
        assert loaded["errors"] == ["timeout on first attempt"]
        assert loaded["handoffs"]["init"] == "handoff data from init"
        assert loaded["timing"]["init"]["start"] == 0

        restored = make_initial_state(loaded.get("config", {}), loaded.get("paths", {}))
        restored.update(
            {
                "complexity": loaded["complexity"],
                "ui_project": loaded["ui_project"],
                "work_type": loaded["work_type"],
                "work_item": loaded["work_item"],
                "stages": loaded["stages"],
                "decisions": loaded["decisions"],
                "stage_artifacts": loaded["stage_artifacts"],
                "errors": loaded["errors"],
                "handoffs": loaded["handoffs"],
                "timing": loaded["timing"],
            }
        )
        assert restored["stages"]["init"]["done"] is True
        assert restored["decisions"] == ["AD-001: Use React"]
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def test_context_handoff_between_stages():
    state = _make_state("medium", False, "feature")
    state["handoffs"] = {}

    state["handoffs"]["init"] = "Complexity: medium, UI: false, Work: Add API endpoint"
    assert state["handoffs"]["init"] == "Complexity: medium, UI: false, Work: Add API endpoint"

    state["handoffs"]["arch.requirements"] = "REST API with JWT auth, PostgreSQL backend"
    assert state["handoffs"]["init"] == "Complexity: medium, UI: false, Work: Add API endpoint"
    assert state["handoffs"]["arch.requirements"] == "REST API with JWT auth, PostgreSQL backend"

    state["handoffs"]["impl.design"] = "Blueprint: 3 endpoints, 2 middleware, 5 tests"
    assert len(state["handoffs"]) == 3
    assert "init" in state["handoffs"]
    assert "arch.requirements" in state["handoffs"]
    assert "impl.design" in state["handoffs"]

    state["stage_artifacts"] = {"init": "init artifact content"}
    assert state["stage_artifacts"]["init"] == "init artifact content"

    state["stage_artifacts"]["arch.requirements"] = "arch artifact content"
    assert state["stage_artifacts"]["init"] == "init artifact content"
    assert state["stage_artifacts"]["arch.requirements"] == "arch artifact content"

    state["decisions"] = ["AD-001: Use PostgreSQL"]
    state["decisions"].append("AD-002: JWT over sessions")
    assert len(state["decisions"]) == 2
    assert "AD-001: Use PostgreSQL" in state["decisions"]


def test_dynamic_graph_complex_ui_all_nodes():
    state = _make_state("complex", True, "feature")
    builder = GraphBuilder()
    _, topology = builder.build(state)

    assert len(topology.active_nodes) == 26
    assert topology.nodes_included == 26
    assert topology.total_available == 26

    for sid in STAGE_ORDER:
        assert sid in topology.active_nodes, f"Missing node: {sid}"

    assert "init" in topology.active_nodes
    assert "init.bdd" in topology.active_nodes
    assert "design.user-research" in topology.active_nodes
    assert "design.visual-design" in topology.active_nodes
    assert "arch.requirements" in topology.active_nodes
    assert "arch.review" in topology.active_nodes
    assert "impl.code" in topology.active_nodes
    assert "verify" in topology.active_nodes
    assert "e2e.execute" in topology.active_nodes
    assert "qa.security" in topology.active_nodes
    assert "qa.performance" in topology.active_nodes
    assert "deploy.prepare" in topology.active_nodes
    assert "smoke.test" in topology.active_nodes
    assert "doc.decisions" in topology.active_nodes
    assert "post" in topology.active_nodes

    active = get_active_stages("complex", True)
    assert len(active) == 26

    registry = build_registry()
    all_specs = registry.filter(complexity="complex", ui_project=True)
    assert len(all_specs) == 26

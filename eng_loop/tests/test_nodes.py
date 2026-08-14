from __future__ import annotations

"""Tests for node handlers - validates each node processes state correctly."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from langgraph.types import Command

from eng_loop.node_registry import build_registry
from eng_loop.state import make_initial_state


def _make_mock_agent_result(data, error=None):
    """Create a mock AgentResult for testing node handlers."""
    mock = MagicMock()
    mock.data = data
    mock.error = error
    mock.iterations = 1
    mock.elapsed = 0.5
    mock.tool_calls_made = 2
    return mock


# ============================================================
# NODE REGISTRY VALIDATION
# ============================================================

class TestNodeRegistry:
    def test_all_handlers_callable(self):
        registry = build_registry()
        for spec in registry.all_specs():
            assert callable(spec.handler), f"Handler not callable for {spec.id}"

    def test_all_specs_have_description(self):
        registry = build_registry()
        for spec in registry.all_specs():
            assert spec.description, f"Missing description for {spec.id}"

    def test_all_specs_have_phase(self):
        registry = build_registry()
        for spec in registry.all_specs():
            assert spec.phase, f"Missing phase for {spec.id}"

    def test_node_name_conversion(self):
        registry = build_registry()
        for spec in registry.all_specs():
            assert "." not in spec.node_name, f"Node name should use hyphens: {spec.node_name}"
            expected = spec.id.replace(".", "-")
            assert spec.node_name == expected, f"Expected {expected}, got {spec.node_name}"


# ============================================================
# NODE HANDLERS - STATE PROCESSING
# ============================================================

class TestInitNode:
    def test_init_node_receives_state(self):
        registry = build_registry()
        spec = registry.get("init")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test work item"
        mock_result = _make_mock_agent_result({
            "valid": True,
            "work_item_refined": "Test work item",
            "estimated_files": 5,
            "estimated_tasks": 3,
            "notes": "validated",
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)

    def test_init_ideate_node(self):
        registry = build_registry()
        spec = registry.get("init.ideate")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({
            "ideation_results": "some ideas",
            "decomposed_tasks": ["task1"],
            "ready_for_next": True,
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)

    def test_init_refine_node(self):
        registry = build_registry()
        spec = registry.get("init.refine")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({
            "refined_work_item": "Refined test",
            "ready_for_architecture": True,
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)


class TestImplNodes:
    def test_impl_design_node(self):
        registry = build_registry()
        spec = registry.get("impl.design")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({
            "blueprint": "plan", "tasks": [], "file_structure": {}, "complete": True, "decisions": [],
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)

    def test_impl_code_node(self):
        registry = build_registry()
        spec = registry.get("impl.code")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({
            "implementation_summary": "done", "files_created": [], "tests_passed": True,
            "complete": True, "decisions": [], "diff": "",
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)

    def test_doc_update_node(self):
        registry = build_registry()
        spec = registry.get("doc.update")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({"files_updated": [], "complete": True})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)


class TestVerifyNodes:
    def test_verify_node(self):
        registry = build_registry()
        spec = registry.get("verify")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["work_item"] = "Test"
            state["paths"] = {"artifact_root": tmp}
            mock_result = _make_mock_agent_result({
                "verdict": "PASS", "per_ac_evidence": [], "discrimination_sensor": {},
                "coverage_audit": {}, "gaps": [], "complete": True,
            })
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
                result = spec.handler(state)
            assert isinstance(result, Command)


class TestQANodes:
    def test_qa_security_node(self):
        registry = build_registry()
        spec = registry.get("qa.security")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({
            "verdict": "PASS", "findings": [], "critical_findings": [], "complete": True,
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)

    def test_qa_api_contract_node(self):
        registry = build_registry()
        spec = registry.get("qa.api-contract")
        assert spec is not None
        state = make_initial_state({}, {})
        mock_result = _make_mock_agent_result({
            "verdict": "PASS", "findings": [], "critical_findings": [], "complete": True,
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)


class TestDeployNodes:
    def test_deploy_prepare_node(self):
        registry = build_registry()
        spec = registry.get("deploy.prepare")
        assert spec is not None
        state = make_initial_state({}, {})
        state["work_item"] = "Test"
        mock_result = _make_mock_agent_result({
            "build_status": "ok", "lint_status": "ok", "type_check_status": "ok",
            "verdict": "PASS", "errors": [], "complete": True,
        })
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            result = spec.handler(state)
        assert isinstance(result, Command)


class TestDocNodes:
    def test_doc_decisions_node(self):
        registry = build_registry()
        spec = registry.get("doc.decisions")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["paths"] = {"artifact_root": tmp}
            mock_result = _make_mock_agent_result({
                "decisions_document": "AD-001: Use REST", "complete": True,
            })
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
                result = spec.handler(state)
            assert isinstance(result, Command)

    def test_doc_project_node(self):
        registry = build_registry()
        spec = registry.get("doc.project")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["paths"] = {"artifact_root": tmp}
            mock_result = _make_mock_agent_result({
                "project_documentation": "arc42 doc", "complete": True,
            })
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
                result = spec.handler(state)
            assert isinstance(result, Command)


class TestPostNode:
    def test_post_node(self):
        registry = build_registry()
        spec = registry.get("post")
        assert spec is not None
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["paths"] = {"artifact_root": tmp}
            state["config"] = {"lessons": {"enabled": False}}
            mock_result = _make_mock_agent_result({
                "summary": "done", "lessons_to_share": 0, "final_status": "done", "complete": True,
            })
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
                result = spec.handler(state)
            assert isinstance(result, Command)


# ============================================================
# NODE METADATA VALIDATION
# ============================================================

class TestNodeMetadata:
    def test_complexity_thresholds(self):
        registry = build_registry()
        assert registry.get("init").min_complexity == "small"
        assert registry.get("impl.code").min_complexity == "small"
        assert registry.get("arch.requirements").min_complexity == "medium"
        assert registry.get("arch.review").min_complexity == "complex"
        assert registry.get("design.user-research").min_complexity == "large"

    def test_ui_required_nodes(self):
        registry = build_registry()
        assert registry.get("e2e.execute").requires_ui is True
        assert registry.get("smoke.test").requires_ui is True
        assert registry.get("impl.code").requires_ui is False

    def test_parallel_group(self):
        registry = build_registry()
        assert registry.get("qa.security").parallel_group == "qa"
        assert registry.get("qa.api-contract").parallel_group == "qa"
        assert registry.get("qa.performance").parallel_group == "qa"

    def test_excluded_work_types(self):
        registry = build_registry()
        assert "documentation" in registry.get("impl.design").excluded_for_work_types
        assert "documentation" in registry.get("verify").excluded_for_work_types
        assert "documentation" in registry.get("deploy.prepare").excluded_for_work_types

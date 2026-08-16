from __future__ import annotations

"""FASE 1D — Handler tests with realistic state."""

from unittest.mock import MagicMock, patch

from langgraph.types import Command

from eng_loop.node_registry import build_registry
from eng_loop.state import make_initial_state


def _mr(data, error=None):
    m = MagicMock()
    m.data = data
    m.error = error
    m.iterations = 1
    m.elapsed = 0.5
    m.tool_calls_made = 2
    return m


def _fs(complexity="medium", ui_project=False):
    s = make_initial_state({}, {})
    s["work_item"] = "Implement user authentication with OAuth2"
    s["complexity"] = complexity
    s["ui_project"] = ui_project
    s["config"] = {
        "agent": {"max_agent_iterations": 25},
        "constraints": {
            "max_init_ideate_attempts": 3,
            "max_init_bdd_attempts": 2,
            "max_init_refine_attempts": 5,
            "max_impl_design_attempts": 2,
            "max_impl_code_attempts": 3,
            "max_verify_attempts": 3,
        },
        "lessons": {"enabled": False},
    }
    s["paths"] = {
        "project_root": "/tmp/test-project",
        "artifact_root": "/tmp/test-project/.eng/artifacts",
        "framework_stage_root": "",
        "framework_skill_root": "",
    }
    s["decisions"] = []
    s["errors"] = []
    s["handoffs"] = {}
    s["stage_artifacts"] = {}
    s["iteration"] = 0
    return s


class TestCommandReturnType:
    def test_impl_code_returns_command_with_goto(self):
        spec = build_registry().get("impl.code")
        mock = _mr(
            {
                "implementation_summary": "Auth",
                "files_created": ["a.py"],
                "tests_passed": True,
                "complete": True,
                "decisions": [],
                "diff": "",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(_fs())
        assert isinstance(result, Command)
        assert result.goto is not None
        assert result.update is not None

    def test_verify_returns_command_with_update(self):
        spec = build_registry().get("verify")
        mock = _mr(
            {
                "verdict": "PASS",
                "per_ac_evidence": [],
                "discrimination_sensor": {},
                "coverage_audit": {},
                "gaps": [],
                "complete": True,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(_fs())
        assert isinstance(result, Command)
        assert "stages" in result.update


class TestEmptyWorkItem:
    def test_init_empty_work_item(self):
        spec = build_registry().get("init")
        s = _fs()
        s["work_item"] = ""
        mock = _mr(
            {"valid": False, "work_item_refined": "", "estimated_files": 0, "estimated_tasks": 0, "notes": "empty"}
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert result.goto == "__end__"

    def test_impl_code_empty_work_item(self):
        spec = build_registry().get("impl.code")
        s = _fs()
        s["work_item"] = ""
        mock = _mr(
            {
                "implementation_summary": "",
                "files_created": [],
                "tests_passed": False,
                "complete": True,
                "decisions": [],
                "diff": "",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert isinstance(result, Command)


class TestInvalidPaths:
    def test_missing_paths(self):
        spec = build_registry().get("impl.code")
        s = _fs()
        s["paths"] = {}
        mock = _mr(
            {
                "implementation_summary": "d",
                "files_created": [],
                "tests_passed": True,
                "complete": True,
                "decisions": [],
                "diff": "",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert isinstance(result, Command)

    def test_empty_artifact_root(self):
        import tempfile

        spec = build_registry().get("verify")
        with tempfile.TemporaryDirectory() as tmp:
            s = _fs()
            s["paths"]["artifact_root"] = tmp
            mock = _mr(
                {
                    "verdict": "PASS",
                    "per_ac_evidence": [],
                    "discrimination_sensor": {},
                    "coverage_audit": {},
                    "gaps": [],
                    "complete": True,
                }
            )
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
                result = spec.handler(s)
            assert isinstance(result, Command)


class TestMissingConfigDefaults:
    def test_empty_config(self):
        spec = build_registry().get("impl.code")
        s = _fs()
        s["config"] = {}
        mock = _mr(
            {
                "implementation_summary": "d",
                "files_created": [],
                "tests_passed": True,
                "complete": True,
                "decisions": [],
                "diff": "",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert isinstance(result, Command)

    def test_no_constraints(self):
        spec = build_registry().get("verify")
        s = _fs()
        s["config"] = {"agent": {"max_agent_iterations": 25}}
        mock = _mr(
            {
                "verdict": "PASS",
                "per_ac_evidence": [],
                "discrimination_sensor": {},
                "coverage_audit": {},
                "gaps": [],
                "complete": True,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert isinstance(result, Command)

    def test_init_default_complexity(self):
        spec = build_registry().get("init")
        s = make_initial_state({}, {})
        s["work_item"] = "Test"
        s["complexity"] = "unset"
        mock = _mr({"valid": True, "work_item_refined": "T", "estimated_files": 1, "estimated_tasks": 1, "notes": "ok"})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert isinstance(result, Command)

from __future__ import annotations

"""FASE 1C — Missing node handler tests.

Covers: init.bdd, 6 design stages, 3 arch stages, e2e.execute, qa.performance, smoke.test
"""

import tempfile
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


def _st(stages=None, tmpdir=None):
    s = make_initial_state({}, {})
    s["work_item"] = "Test"
    s["complexity"] = "large"
    s["ui_project"] = False
    s["paths"] = {"artifact_root": tmpdir or ""}
    if stages:
        s["stages"].update(stages)
    return s


class TestInitBddNode:
    def test_success(self):
        spec = build_registry().get("init.bdd")
        mock = _mr({"journey_map": "map", "gherkin_scenarios": ["s1"], "complete": True})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(_st())
        assert isinstance(result, Command)
        assert result.goto == "init-refine"

    def test_done_skips(self):
        spec = build_registry().get("init.bdd")
        result = spec.handler(_st({"init.bdd": {"done": True, "attempts": 1}}))
        assert result.goto == "init-refine"

    def test_max_attempts(self):
        spec = build_registry().get("init.bdd")
        s = _st({"init.bdd": {"done": False, "attempts": 2}})
        s["config"] = {"constraints": {"max_init_bdd_attempts": 2}}
        result = spec.handler(s)
        assert result.goto == "init-refine"

    def test_error_retry(self):
        spec = build_registry().get("init.bdd")
        mock = _mr({}, error="err")
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(_st())
        assert result.goto == "init-bdd"


DESIGN_STAGES = [
    ("design.user-research", "design-personas"),
    ("design.personas", "design-info-arch"),
    ("design.info-arch", "design-interaction"),
    ("design.interaction", "design-design-system"),
    ("design.design-system", "design-visual-design"),
    ("design.visual-design", "arch-requirements"),
]


class TestDesignNodes:
    def _ds(self, sid, done=False):
        s = _st()
        s["stages"][sid] = {"done": done, "attempts": 0 if not done else 1}
        return s

    def test_all_design_success(self):
        reg = build_registry()
        for stage_id, expected_next in DESIGN_STAGES:
            spec = reg.get(stage_id)
            assert spec is not None, f"Missing {stage_id}"
            mock = _mr({"design_output": "output", "artifacts": [], "complete": True, "decisions": []})
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
                result = spec.handler(self._ds(stage_id))
            assert isinstance(result, Command), f"{stage_id} failed"
            assert result.goto == expected_next, f"{stage_id}: expected {expected_next}, got {result.goto}"

    def test_all_design_done_skip(self):
        reg = build_registry()
        for stage_id, expected_next in DESIGN_STAGES:
            spec = reg.get(stage_id)
            result = spec.handler(self._ds(stage_id, done=True))
            assert result.goto == expected_next, f"{stage_id} skip: expected {expected_next}"

    def test_design_max_attempts(self):
        spec = build_registry().get("design.personas")
        s = self._ds("design.personas")
        s["stages"]["design.personas"]["attempts"] = 2
        s["config"] = {"constraints": {"max_design_personas_attempts": 2}}
        result = spec.handler(s)
        assert isinstance(result, Command)


class TestArchNodes:
    def _as(self, sid, done=False):
        s = _st()
        s["complexity"] = "medium"
        s["stages"][sid] = {"done": done, "attempts": 0 if not done else 1}
        return s

    def test_arch_requirements_success(self):
        spec = build_registry().get("arch.requirements")
        mock = _mr({"architecture_output": "req", "complete": True, "decisions": [], "critical_findings": []})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(self._as("arch.requirements"))
        assert result.goto == "arch-solution"

    def test_arch_requirements_done(self):
        spec = build_registry().get("arch.requirements")
        result = spec.handler(self._as("arch.requirements", done=True))
        assert result.goto == "arch-solution"

    def test_arch_solution_success(self):
        spec = build_registry().get("arch.solution")
        mock = _mr({"architecture_output": "sol", "complete": True, "decisions": [], "critical_findings": []})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(self._as("arch.solution"))
        assert result.goto == "impl-design"

    def test_arch_solution_complex_to_review(self):
        spec = build_registry().get("arch.solution")
        mock = _mr({"architecture_output": "sol", "complete": True, "decisions": [], "critical_findings": []})
        s = self._as("arch.solution")
        s["complexity"] = "complex"
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert result.goto == "arch-review"

    def test_arch_review_success(self):
        spec = build_registry().get("arch.review")
        mock = _mr({"architecture_output": "review", "complete": True, "decisions": [], "critical_findings": []})
        s = self._as("arch.review")
        s["complexity"] = "complex"
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert result.goto == "impl-design"

    def test_arch_review_critical_loops(self):
        spec = build_registry().get("arch.review")
        mock = _mr({"architecture_output": "review", "complete": True, "decisions": [], "critical_findings": ["f1"]})
        s = self._as("arch.review")
        s["complexity"] = "complex"
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert result.goto == "arch-requirements"

    def test_arch_max_attempts(self):
        spec = build_registry().get("arch.requirements")
        s = self._as("arch.requirements")
        s["stages"]["arch.requirements"]["attempts"] = 2
        s["config"] = {"constraints": {"max_arch_requirements_attempts": 2}}
        result = spec.handler(s)
        assert isinstance(result, Command)


class TestE2eExecuteNode:
    def test_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = build_registry().get("e2e.execute")
            s = _st(tmpdir=tmp)
            s["ui_project"] = True
            mock = _mr(
                {
                    "verdict": "PASS",
                    "test_results": [],
                    "console_errors": [],
                    "network_errors": [],
                    "bdd_coverage": 1.0,
                    "complete": True,
                }
            )
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
                result = spec.handler(s)
            assert isinstance(result, Command)

    def test_done(self):
        spec = build_registry().get("e2e.execute")
        s = _st({"e2e.execute": {"done": True, "attempts": 1}})
        result = spec.handler(s)
        assert isinstance(result, Command)

    def test_fail_loops(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = build_registry().get("e2e.execute")
            s = _st(tmpdir=tmp)
            s["ui_project"] = True
            mock = _mr(
                {
                    "verdict": "FAIL",
                    "test_results": [],
                    "console_errors": [],
                    "network_errors": [],
                    "bdd_coverage": 0.5,
                    "complete": False,
                }
            )
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
                result = spec.handler(s)
            assert result.goto == "impl-code"

    def test_max_attempts(self):
        spec = build_registry().get("e2e.execute")
        s = _st({"e2e.execute": {"done": False, "attempts": 3}})
        s["config"] = {"constraints": {"max_e2e_execute_attempts": 3}}
        result = spec.handler(s)
        assert result.goto == "impl-code"


class TestQaPerformanceNode:
    def test_success(self):
        spec = build_registry().get("qa.performance")
        s = _st()
        s["complexity"] = "complex"
        mock = _mr({"verdict": "PASS", "findings": [], "critical_findings": [], "complete": True})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert result.goto == "deploy-prepare"

    def test_done(self):
        spec = build_registry().get("qa.performance")
        s = _st({"qa.performance": {"done": True, "attempts": 1}})
        result = spec.handler(s)
        assert result.goto == "deploy-prepare"

    def test_fail_loops(self):
        spec = build_registry().get("qa.performance")
        s = _st()
        s["complexity"] = "complex"
        mock = _mr({"verdict": "FAIL", "findings": ["slow"], "critical_findings": ["timeout"], "complete": False})
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
            result = spec.handler(s)
        assert result.goto == "impl-code"


class TestSmokeTestNode:
    def test_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = build_registry().get("smoke.test")
            s = _st(tmpdir=tmp)
            s["ui_project"] = True
            mock = _mr(
                {"verdict": "PASS", "critical_paths": [], "console_errors": [], "network_errors": [], "complete": True}
            )
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
                result = spec.handler(s)
            assert isinstance(result, Command)

    def test_done(self):
        spec = build_registry().get("smoke.test")
        s = _st({"smoke.test": {"done": True, "attempts": 1}})
        result = spec.handler(s)
        assert isinstance(result, Command)

    def test_fail_loops(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = build_registry().get("smoke.test")
            s = _st(tmpdir=tmp)
            s["ui_project"] = True
            mock = _mr(
                {
                    "verdict": "FAIL",
                    "critical_paths": [],
                    "console_errors": ["err"],
                    "network_errors": [],
                    "complete": False,
                }
            )
            with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock):
                result = spec.handler(s)
            assert result.goto == "impl-code"

    def test_max_attempts(self):
        spec = build_registry().get("smoke.test")
        s = _st({"smoke.test": {"done": False, "attempts": 3}})
        s["config"] = {"constraints": {"max_smoke_test_attempts": 3}}
        result = spec.handler(s)
        assert result.goto == "impl-code"

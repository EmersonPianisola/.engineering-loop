from __future__ import annotations

"""Tests for topology compliance checking."""

from eng_loop.state import make_initial_state
from eng_loop.tools.topology_compliance import (
    ComplianceResult,
    _find_last_done_stage,
    _find_skipped_stages,
    _get_expected_next_stage,
    check_compliance,
)


class TestComplianceResult:
    def test_ok_result(self):
        result = ComplianceResult(ok=True)
        assert result.ok is True
        assert "OK" in str(result)

    def test_blocked_result(self):
        result = ComplianceResult(ok=False, violations=["skip"], expected_next="init")
        assert result.ok is False
        assert "BLOCKED" in str(result)
        assert "VIOLATION" in str(result)

    def test_to_json(self):
        result = ComplianceResult(ok=True, expected_next="init")
        data = result.to_json()
        assert '"ok": true' in data


class TestFindLastDoneStage:
    def test_no_done_stages(self):
        stages = {"init": {"done": False}, "verify": {"done": False}}
        assert _find_last_done_stage(stages) is None

    def test_single_done(self):
        stages = {"init": {"done": True}, "verify": {"done": False}}
        assert _find_last_done_stage(stages) == "init"

    def test_multiple_done(self):
        stages = {
            "init": {"done": True},
            "impl.code": {"done": True},
            "verify": {"done": False},
        }
        assert _find_last_done_stage(stages) == "impl.code"


class TestFindSkippedStages:
    def test_no_skip(self):
        stages = {
            "init": {"done": True},
            "init.ideate": {"done": True},
            "init.refine": {"done": False},
        }
        skipped = _find_skipped_stages(stages, "init.ideate", "init.refine", "small", False, "feature")
        assert skipped == []

    def test_skip_detected(self):
        stages = {
            "init": {"done": True},
            "init.ideate": {"done": False},
            "init.refine": {"done": False},
        }
        skipped = _find_skipped_stages(stages, "init", "init.refine", "small", False, "feature")
        assert "init.ideate" in skipped

    def test_inactive_stages_not_skipped(self):
        stages = {
            "init": {"done": True},
            "arch.requirements": {"done": False},
            "impl.design": {"done": False},
        }
        skipped = _find_skipped_stages(stages, "init", "impl.design", "small", False, "feature")
        assert "arch.requirements" not in skipped


class TestCheckCompliance:
    def test_first_stage_compliant(self):
        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["ui_project"] = False
        result = check_compliance(state, "init")
        assert result.ok is True

    def test_inactive_stage_blocked(self):
        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["ui_project"] = False
        state["stages"]["init"]["done"] = True
        result = check_compliance(state, "arch.requirements")
        assert result.ok is False
        assert any("INACTIVE_STAGE" in v for v in result.violations)

    def test_stage_skip_detected(self):
        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["ui_project"] = False
        state["stages"]["init"]["done"] = True
        state["stages"]["init.ideate"]["done"] = False
        state["stages"]["init.refine"]["done"] = False
        result = check_compliance(state, "init.refine")
        assert any("STAGE_SKIP" in v for v in result.violations)

    def test_active_stage_for_complexity(self):
        state = make_initial_state({}, {})
        state["complexity"] = "medium"
        state["ui_project"] = False
        state["stages"]["init"]["done"] = True
        state["stages"]["init.ideate"]["done"] = True
        state["stages"]["init.refine"]["done"] = True
        result = check_compliance(state, "arch.requirements")
        assert result.ok is True


class TestExpectedNextStage:
    def test_no_last_done_returns_init(self):
        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["ui_project"] = False
        expected = _get_expected_next_stage(state, None, "small", False, "feature")
        assert expected == "init"

    def test_after_init_done(self):
        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["ui_project"] = False
        state["stages"]["init"]["done"] = True
        expected = _get_expected_next_stage(state, "init", "small", False, "feature")
        assert expected == "init.ideate"


class TestCheckComplianceFromFile:
    def test_load_from_file(self):
        import tempfile

        from eng_loop.tools.topology_compliance import check_compliance_from_files

        with tempfile.TemporaryDirectory() as tmp:
            state_file = f"{tmp}/state.json"
            state = make_initial_state({}, {})
            state["complexity"] = "small"
            state["ui_project"] = False
            with open(state_file, "w", encoding="utf-8") as f:
                json_str = (
                    '{"complexity": "small", "ui_project": false, "work_type": "feature", '
                    '"stages": {"init": {"done": false, "attempts": 0}}}'
                )
                f.write(json_str)
            result = check_compliance_from_files(state_file, "init")
        assert result.ok is True

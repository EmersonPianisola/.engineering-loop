from __future__ import annotations

from eng_loop.schemas import Lesson, RecoveryPlan
from eng_loop.tools.fix_applier import apply_recovery_plan


def _make_state(stage_id: str = "impl.code") -> dict:
    return {
        "current_stage": stage_id,
        "status": "blocked",
        "blocking_condition": "test error",
        "stages": {
            "impl.design": {"done": True, "attempts": 1, "status": ""},
            "impl.code": {"done": False, "attempts": 2, "status": ""},
            "verify": {"done": False, "attempts": 0, "status": ""},
            "qa.static": {"done": False, "attempts": 0, "status": ""},
        },
        "lessons": [],
        "fix_tasks": [],
        "handoffs": {},
        "recovery_attempts": 0,
        "recovery_history": [],
    }


class TestApplyRecoveryPlan:
    def test_resets_blocking_condition_and_status(self) -> None:
        state = _make_state()
        plan = RecoveryPlan(
            root_cause="test cause",
            error_category="logic",
            fix_actions=["fix1"],
            stages_to_rollback=["impl.code"],
            lessons=[],
            confidence=0.7,
            fix_prompt_injection="Try different approach",
        )
        result = apply_recovery_plan(state, plan)
        assert result["blocking_condition"] == ""
        assert result["status"] == "running"

    def test_selective_rollback_resets_specified_stages(self) -> None:
        state = _make_state()
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=["impl.code"],
            lessons=[],
            confidence=0.5,
        )
        result = apply_recovery_plan(state, plan)
        assert result["stages"]["impl.code"]["done"] is False
        assert result["stages"]["impl.code"]["attempts"] == 0
        # Other stages preserved
        assert result["stages"]["impl.design"]["done"] is True

    def test_no_rollback_when_empty_list(self) -> None:
        state = _make_state()
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="transient",
            fix_actions=["retry"],
            stages_to_rollback=[],
            lessons=[],
            confidence=0.9,
        )
        result = apply_recovery_plan(state, plan)
        assert result["stages"]["impl.code"]["attempts"] == 2

    def test_never_rollback_blocked_stages(self) -> None:
        state = _make_state()
        state["stages"]["impl.code"]["status"] = "blocked"
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=["impl.code"],
            lessons=[],
            confidence=0.5,
        )
        result = apply_recovery_plan(state, plan)
        assert result["stages"]["impl.code"]["status"] == "blocked"
        assert result["stages"]["impl.code"]["attempts"] == 2

    def test_never_rollback_waiting_for_input_stages(self) -> None:
        state = _make_state()
        state["stages"]["impl.code"]["status"] = "waiting_for_input"
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=["impl.code"],
            lessons=[],
            confidence=0.5,
        )
        result = apply_recovery_plan(state, plan)
        assert result["stages"]["impl.code"]["status"] == "waiting_for_input"

    def test_injects_lessons_into_state(self) -> None:
        state = _make_state()
        lessons = [
            Lesson(
                lesson_id="l1",
                category="logic",
                pattern="non-convergence",
                fix_strategy="Use TDD",
                context="agent stalled",
            )
        ]
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=[],
            lessons=lessons,
            confidence=0.5,
        )
        result = apply_recovery_plan(state, plan)
        assert len(result["lessons"]) == 1
        assert "logic" in result["lessons"][0]
        assert "non-convergence" in result["lessons"][0]

    def test_injects_fix_guidance_as_fix_task(self) -> None:
        state = _make_state()
        plan = RecoveryPlan(
            root_cause="root cause here",
            error_category="logic",
            fix_actions=["action1", "action2"],
            stages_to_rollback=[],
            lessons=[],
            confidence=0.7,
            fix_prompt_injection="Try X instead of Y",
        )
        result = apply_recovery_plan(state, plan)
        assert len(result["fix_tasks"]) == 1
        assert result["fix_tasks"][0]["source"] == "recovery-agent"
        assert "root cause here" in result["fix_tasks"][0]["gap"]

    def test_injects_fix_prompt_into_handoffs(self) -> None:
        state = _make_state()
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=[],
            lessons=[],
            confidence=0.5,
            fix_prompt_injection="Try different approach",
        )
        result = apply_recovery_plan(state, plan)
        assert "recovery_fix_prompt" in result["handoffs"]
        assert result["handoffs"]["recovery_fix_prompt"] == "Try different approach"

    def test_filters_fix_tasks_for_rolledback_stages(self) -> None:
        state = _make_state()
        state["fix_tasks"] = [
            {"source": "verify", "gap": "old gap"},
            {"source": "impl.code", "gap": "code gap"},
        ]
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=["impl.code"],
            lessons=[],
            confidence=0.5,
        )
        result = apply_recovery_plan(state, plan)
        sources = [ft["source"] for ft in result["fix_tasks"]]
        assert "verify" in sources
        assert "impl.code" not in sources

    def test_all_invalid_targets_fall_back_to_chain(self) -> None:
        # FASE 1.3: an all-invalid target list must not be a silent no-op.
        # It falls back to the standard impl.code -> current_stage chain
        # rollback (here current_stage="impl.code", so only impl.code resets).
        state = _make_state()
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=["nonexistent.stage"],
            lessons=[],
            confidence=0.5,
        )
        result = apply_recovery_plan(state, plan)
        assert result["stages"]["impl.code"]["attempts"] == 0
        # stage before the chain start untouched
        assert result["stages"]["impl.design"]["done"] is True

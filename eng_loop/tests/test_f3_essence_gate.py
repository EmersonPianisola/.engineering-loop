"""F3.4 — Essence gate robustness.

- Agent errors no longer silently PASS: after max_retries the stage blocks
  and the skip is recorded in state["essence"]["skipped_stages"].
- Auto-adjusted complexity reaches the Command update (the stale pre-gate
  snapshot used to revert the in-place mutation).
- auto_adjust_attempts persists across gate invocations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from eng_loop.state import init_stages


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills"


def _make_state(*, stage_id: str = "init", complexity: str = "small") -> dict[str, Any]:
    stages = init_stages()
    return {
        "stages": stages,
        "config": {
            "essence": {
                "enabled": True,
                "skill": "essence",
                "clarification_threshold": "medium",
                "auto_adjust_max": 3,
                "max_clarification_attempts": 3,
            },
            "agent": {"max_agent_iterations": 5},
            "max_essence_retries_per_stage": 5,
        },
        "paths": {
            "framework_skill_root": str(_skill_root()),
            "project_root": ".",
        },
        "work_item": "Test work item",
        "complexity": complexity,
        "ui_project": False,
        "decisions": [],
        "stage_artifacts": {},
        "essence": {
            "checked": False,
            "blocked_stage": None,
            "decision": None,
            "clarification_attempts": 0,
            "auto_adjust_attempts": 0,
            "pending_questions": [],
            "resolved_findings": [],
        },
        "essence_clarifying_questions": [],
    }


def _agent_result(data: dict[str, Any], error: str | None = None) -> MagicMock:
    m = MagicMock()
    m.error = error
    m.data = data
    return m


_CLEAN_DATA = {
    "lens_1_subjective_terms": [],
    "lens_2_hidden_assumptions": [],
    "lens_3_literal_traps": [],
    "lens_4_conflicts": [],
    "clean": True,
    "adjustments": [],
    "clarifying_questions": [],
    "summary": "All clear.",
}


# ── 1. Agent error → block (no silent PASS) ─────────────────────────


def test_agent_error_blocks_instead_of_silent_pass() -> None:
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()
    with patch("eng_loop.tools.essence_gate.run_agent", return_value=_agent_result({}, error="model timeout")):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.blocked is True
    assert result.passed is False
    assert "failed" in result.tension
    assert state["essence"]["skipped_stages"] == ["init"]


def test_agent_error_blocked_command_carry_essence_and_reason() -> None:
    from eng_loop.tools.essence_gate import essence_gate

    @essence_gate("impl.code")
    def handler(state):  # pragma: no cover - must not run
        raise AssertionError("handler must not run when the gate blocks")

    state = _make_state(stage_id="impl.code")
    with patch("eng_loop.tools.essence_gate.run_agent", return_value=_agent_result({}, error="boom")):
        cmd = handler(state)

    assert cmd.update["status"] == "blocked"
    assert "agent failed" in cmd.update["blocking_condition"]
    assert cmd.update["essence"]["skipped_stages"] == ["impl.code"]


def test_error_then_clean_passes_and_records_no_skip() -> None:
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()
    with patch(
        "eng_loop.tools.essence_gate.run_agent",
        side_effect=[_agent_result({}, error="flaky"), _agent_result(_CLEAN_DATA)],
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False
    assert state["essence"].get("skipped_stages", []) == []


# ── 2. Auto-adjust complexity reaches the Command update ────────────


def test_auto_adjusted_complexity_in_command_update() -> None:
    from eng_loop.tools.essence_gate import essence_gate

    @essence_gate("impl.code")
    def handler(state):  # pragma: no cover - gate returns waiting first
        raise AssertionError("handler must not run while the gate waits")

    state = _make_state(stage_id="impl.code", complexity="small")
    lens4 = _agent_result(
        {
            "lens_1_subjective_terms": [],
            "lens_2_hidden_assumptions": [],
            "lens_3_literal_traps": [],
            "lens_4_conflicts": [{"tension": "This is not a small task — scope is medium"}],
            "clean": False,
            "adjustments": [],
            "clarifying_questions": [],
            "summary": "scope mismatch",
        }
    )
    with (
        patch("eng_loop.tools.essence_gate.run_agent", side_effect=[lens4, lens4, lens4]),
        patch("eng_loop.tools.essence_gate.get_tension_memory") as mock_tm,
    ):
        mock_tm.return_value.get_resolution.return_value = None
        cmd = handler(state)

    # small → medium → large (two auto-adjusts), then the exhausted 3rd
    # attempt escalates to clarification with the ADJUSTED complexity.
    assert cmd.update["status"] == "waiting_for_input"
    assert cmd.update["complexity"] == "large"
    assert state["complexity"] == "large"


# ── 3. auto_adjust_attempts persists across invocations ─────────────


def test_auto_adjust_attempts_persist_across_invocations() -> None:
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(stage_id="verify")
    adjust = _agent_result(
        {
            "lens_1_subjective_terms": [],
            "lens_2_hidden_assumptions": [],
            "lens_3_literal_traps": [],
            "lens_4_conflicts": [],
            "clean": False,
            "adjustments": ["tighten scope"],
            "clarifying_questions": [],
            "summary": "adjustments available",
        }
    )

    # Invocation 1: 3 internal auto-adjusts, then exhaustion → waiting.
    with patch("eng_loop.tools.essence_gate.run_agent", return_value=adjust):
        result = run_essence_gate("verify", state, state["paths"], state["config"])
    assert result.waiting_for_input is True
    assert state["essence"]["auto_adjust_attempts"] == 3

    # Between invocations the stage is retried (a rollback resets the stage
    # dict, incl. essence_checked) — the essence counters survive in state.
    state["stages"]["verify"]["essence_checked"] = False

    # Invocation 2 (same stage): the counter must NOT restart at 0 — the gate
    # escalates after a single agent call, with no auto-adjust iterations.
    with patch("eng_loop.tools.essence_gate.run_agent", return_value=adjust) as mock_agent:
        result2 = run_essence_gate("verify", state, state["paths"], state["config"])
    assert result2.waiting_for_input is True
    assert state["essence"]["auto_adjust_attempts"] == 3
    assert mock_agent.call_count == 1

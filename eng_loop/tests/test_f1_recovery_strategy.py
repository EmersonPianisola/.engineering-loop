"""F1.4 — Category-directed recovery strategy in _recovery_loop (H1).

Before 1.4 every category followed the same path: full LLM cycles even
for non-retryable errors. Now:
- non-retryable → block immediately, no LLM call
- transient → plain retry without an LLM plan
- other categories → LLM plan flow (unchanged)
"""

from __future__ import annotations

from unittest.mock import patch

from eng_loop.cli import _recovery_loop
from eng_loop.schemas import RecoveryPlan

BASE_STATE = {
    "status": "blocked",
    "current_stage": "impl.code",
    "stages": {"impl.code": {"done": False, "status": "blocked"}},
    "recovery_history": [],
}

DONE_STATE = {"status": "done", "blocking_condition": ""}


def _run(state: dict, config: dict, tmp_path, invoke_result: dict, analyze_return: RecoveryPlan | None = None):
    with (
        patch("eng_loop.cli._invoke_graph", return_value=invoke_result) as mock_invoke,
        patch("eng_loop.tools.recovery_agent.analyze_and_propose", return_value=analyze_return) as mock_analyze,
    ):
        result = _recovery_loop(
            state,
            graph=object(),
            thread_config={},
            interrupt_nodes=[],
            paths={"artifact_root": str(tmp_path)},
            config=config,
            exec_state=None,
            normalizer=None,
            hud=None,
            tui_controller=True,
            active_nodes_for_progress=[],
            event_bus=None,
        )
    return result, mock_invoke, mock_analyze


class TestNonRetryable:
    def test_blocks_without_llm(self, tmp_path) -> None:
        state = {**BASE_STATE, "blocking_condition": "disk full: no space left on device"}
        result, mock_invoke, mock_analyze = _run(state, {"recovery": {"max_attempts": 3}}, tmp_path, DONE_STATE)

        mock_analyze.assert_not_called()
        mock_invoke.assert_not_called()
        assert result["status"] == "blocked"
        assert "infrastructure" in result["blocking_condition"]
        assert "disk full" in result["blocking_condition"]

    def test_original_state_not_mutated(self, tmp_path) -> None:
        state = {**BASE_STATE, "blocking_condition": "disk full"}
        result, _, _ = _run(state, {"recovery": {}}, tmp_path, DONE_STATE)
        assert state["blocking_condition"] == "disk full"
        assert result is not state


class TestTransient:
    def test_plain_retry_without_llm(self, tmp_path) -> None:
        state = {**BASE_STATE, "blocking_condition": "request timed out after 30s"}
        result, mock_invoke, mock_analyze = _run(state, {"recovery": {}}, tmp_path, DONE_STATE)

        mock_analyze.assert_not_called()
        mock_invoke.assert_called_once()
        passed = mock_invoke.call_args.args[0]
        assert passed["blocking_condition"] == ""
        assert passed["status"] == "running"
        assert passed["recovery_history"][0]["error_category"] == "transient"
        assert result is DONE_STATE

    def test_retries_until_exhausted(self, tmp_path) -> None:
        state = {**BASE_STATE, "blocking_condition": "connection timeout"}
        blocked_again = {
            "status": "blocked",
            "blocking_condition": "connection timeout",
            "current_stage": "impl.code",
        }
        result, mock_invoke, mock_analyze = _run(state, {"recovery": {"max_attempts": 2}}, tmp_path, blocked_again)

        mock_analyze.assert_not_called()
        assert mock_invoke.call_count == 2
        assert result["status"] == "blocked"


class TestLlmPath:
    def test_logic_error_uses_llm_plan(self, tmp_path) -> None:
        state = {
            **BASE_STATE,
            "status": "failed",
            "blocking_condition": "test failed: assertion error in module",
        }
        plan = RecoveryPlan(
            root_cause="broken test",
            error_category="logic",
            fix_actions=["fix the test"],
            stages_to_rollback=[],
            lessons=[],
            confidence=0.7,
        )
        result, mock_invoke, mock_analyze = _run(state, {"recovery": {}}, tmp_path, DONE_STATE, analyze_return=plan)

        mock_analyze.assert_called_once()
        passed = mock_invoke.call_args.args[0]
        assert passed["status"] == "running"
        assert passed["blocking_condition"] == ""
        assert result is DONE_STATE

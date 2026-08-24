"""F2.2 — H2: recovery budget gate.

recovery_attempts is cumulative (across attempts and sessions) and gates the
loop entry: once exhausted, the pipeline blocks WITHOUT calling the LLM.
"""

from __future__ import annotations

from unittest.mock import patch

from eng_loop.cli import _recovery_loop


def _run(state: dict, config: dict, tmp_path):
    with (
        patch("eng_loop.cli._invoke_graph") as mock_invoke,
        patch("eng_loop.tools.recovery_agent.analyze_and_propose") as mock_analyze,
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


class TestRecoveryBudget:
    def test_exhausted_budget_blocks_without_llm(self, tmp_path) -> None:
        state = {
            "status": "blocked",
            "blocking_condition": "connection timeout",
            "current_stage": "impl.code",
            "stages": {},
            "recovery_attempts": 3,
            "recovery_history": [],
        }
        result, mock_invoke, mock_analyze = _run(state, {"recovery": {"max_attempts": 3}}, tmp_path)

        mock_analyze.assert_not_called()
        mock_invoke.assert_not_called()
        assert result["status"] == "blocked"
        assert "budget exhausted" in result["blocking_condition"].lower()
        assert result is not state  # original state not mutated

    def test_budget_accumulates_across_attempts(self, tmp_path) -> None:
        state = {
            "status": "blocked",
            "blocking_condition": "request timed out",
            "current_stage": "impl.code",
            "stages": {},
            "recovery_attempts": 1,
            "recovery_history": [],
        }
        outcomes = iter(
            [
                {
                    "status": "blocked",
                    "blocking_condition": "request timed out",
                    "current_stage": "impl.code",
                    "recovery_attempts": 2,
                },
                {"status": "done", "blocking_condition": "", "recovery_attempts": 3},
            ]
        )
        with (
            patch("eng_loop.cli._invoke_graph", side_effect=lambda *a, **k: next(outcomes)),
            patch("eng_loop.tools.recovery_agent.analyze_and_propose") as mock_analyze,
        ):
            result = _recovery_loop(
                state,
                graph=object(),
                thread_config={},
                interrupt_nodes=[],
                paths={"artifact_root": str(tmp_path)},
                config={"recovery": {"max_attempts": 5}},
                exec_state=None,
                normalizer=None,
                hud=None,
                tui_controller=True,
                active_nodes_for_progress=[],
                event_bus=None,
            )

        assert result["status"] == "done"
        mock_analyze.assert_not_called()  # transient path
        assert result["recovery_attempts"] == 3  # 1 (prev) + 2 attempts

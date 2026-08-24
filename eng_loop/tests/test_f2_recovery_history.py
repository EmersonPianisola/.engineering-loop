"""F2.3 — M9 + stale state: recovery history & lesson state.

- recovery_history must not duplicate entries across recovery attempts.
  The loop re-invokes the graph with the FULL state; with an `add` reducer
  that duplicated ([e1, e1, e2]). The reducer is now overwrite, and the loop
  keeps passing the accumulated list (correct under both a warm checkpoint
  and a fresh one on resume).
- generate_lessons must use the POST-attempt state, not the pre-attempt one.
"""

from __future__ import annotations

import typing
from unittest.mock import patch

from eng_loop.cli import _recovery_loop
from eng_loop.schemas import RecoveryPlan
from eng_loop.state import PipelineState


def _hist_reducer():
    # state.py uses `from __future__ import annotations` — resolve the string
    resolved = typing.get_type_hints(PipelineState, include_extras=True)["recovery_history"]
    # Annotated[list[...], reducer] → (reducer,)
    return typing.get_args(resolved)[-1]


class TestRecoveryHistory:
    def test_reducer_is_not_append(self) -> None:
        # `operator.add` would duplicate entries when the loop re-injects the
        # full state on every recovery attempt
        from operator import add

        from eng_loop.state import _overwrite

        assert _hist_reducer() is _overwrite
        assert _hist_reducer() is not add

    def test_no_duplicates_across_attempts(self, tmp_path) -> None:
        # Emulate the graph's overwrite merge of recovery_history on each invoke
        seen_inputs: list[list] = []

        def fake_invoke(fixed_state, *args, **kwargs):
            seen_inputs.append(fixed_state.get("recovery_history", []))
            return {
                "status": "blocked",
                "blocking_condition": "request timed out",
                "current_stage": "impl.code",
                "recovery_history": list(fixed_state.get("recovery_history", [])),
            }

        state = {
            "status": "blocked",
            "blocking_condition": "request timed out",
            "current_stage": "impl.code",
            "stages": {},
            "recovery_history": [],
        }
        with (
            patch("eng_loop.cli._invoke_graph", side_effect=fake_invoke),
            patch("eng_loop.tools.recovery_agent.analyze_and_propose") as mock_analyze,
        ):
            result = _recovery_loop(
                state,
                graph=object(),
                thread_config={},
                interrupt_nodes=[],
                paths={"artifact_root": str(tmp_path)},
                config={"recovery": {"max_attempts": 2}},
                exec_state=None,
                normalizer=None,
                hud=None,
                tui_controller=True,
                active_nodes_for_progress=[],
                event_bus=None,
            )

        # Each invoke carries the accumulated history (overwrite reducer merges it 1:1)
        assert len(seen_inputs) == 2
        assert [e["attempt"] for e in seen_inputs[0]] == [1]
        assert [e["attempt"] for e in seen_inputs[1]] == [1, 2]

        # Final state: exactly 2 distinct entries — no [e1, e1, e2] duplication
        entries = result["recovery_history"]
        assert len(entries) == 2
        assert [e["attempt"] for e in entries] == [1, 2]

    def test_success_lesson_uses_post_attempt_state(self, tmp_path) -> None:
        from eng_loop.tools.lessons import load_lessons

        plan = RecoveryPlan(
            root_cause="cache stale",
            error_category="logic",
            fix_actions=["clear cache"],
            stages_to_rollback=[],
            lessons=[],  # forces the fallback lesson from state
            confidence=0.6,
        )

        # Attempt 1 fails; the POST-attempt state carries the NEW error text
        outcomes = iter(
            [
                {
                    "status": "blocked",
                    "blocking_condition": "post-attempt error: cache still stale",
                    "current_stage": "impl.code",
                    "recovery_attempts": 1,
                },
                {
                    "status": "done",
                    "blocking_condition": "",
                    "current_stage": "impl.code",
                    "recovery_attempts": 2,
                },
            ]
        )
        with (
            patch("eng_loop.cli._invoke_graph", side_effect=lambda *a, **k: next(outcomes)),
            patch("eng_loop.tools.recovery_agent.analyze_and_propose", return_value=plan),
        ):
            _recovery_loop(
                {
                    "status": "blocked",
                    "blocking_condition": "original error: cache stale",
                    "current_stage": "impl.code",
                    "stages": {},
                    "recovery_history": [],
                },
                graph=object(),
                thread_config={},
                interrupt_nodes=[],
                paths={"artifact_root": str(tmp_path)},
                config={"recovery": {"max_attempts": 2}},
                exec_state=None,
                normalizer=None,
                hud=None,
                tui_controller=True,
                active_nodes_for_progress=[],
                event_bus=None,
            )

        local = load_lessons(str(tmp_path))["local"]
        patterns = " | ".join(l.get("failure", "") for l in local.values())
        # The fallback lesson (from the failed attempt) must reflect the
        # post-attempt error, not the pre-attempt one
        assert "post-attempt error" in patterns

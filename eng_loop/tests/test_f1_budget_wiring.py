"""F1.5 — H11: context budget manager must be built from config.

Before the fix, no caller passed `budget_manager` to run_agent, so the
pre-call compaction check (`_check_context_budget`) never ran even when
`hardware.context_budget.enabled: true`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.tools import Tool

from eng_loop.tools import agent_runner
from eng_loop.tools.agent_runner import reset_lifecycle_manager, run_agent
from eng_loop.tools.context_budget import ContextBudgetManager

BUDGET_CONFIG = {
    "hardware": {
        "context_window": 200000,
        "context_budget": {
            "enabled": True,
            "safety_margin_tokens": 2048,
            "reserved_output": {"default": 4096},
        },
    }
}


class _FakeTokenCounter:
    def __init__(self, model_name, base_url=None):
        pass

    def estimate_messages_input(self, messages):
        return 100


@pytest.fixture(autouse=True)
def _fresh_lifecycle():
    reset_lifecycle_manager()
    yield
    reset_lifecycle_manager()


def make_final_answer_model() -> MagicMock:
    mock_with_tools = MagicMock(name="model_with_tools")
    mock_with_tools.stream.side_effect = [iter([AIMessageChunk(content='{"complete": true}')])]
    mock_model = MagicMock(name="model")
    mock_model.bind_tools.return_value = mock_with_tools
    return mock_model


class TestBudgetWiring:
    def test_enabled_config_builds_manager_and_runs_precheck(self) -> None:
        seen_managers: list = []
        real_check = agent_runner._check_context_budget

        def spy_check(bm, stage_id, messages, model):
            seen_managers.append(bm)
            return real_check(bm, stage_id, messages, model)

        tool = Tool(name="noop", description="d", func=lambda: "ok")
        with (
            patch.object(agent_runner, "_check_context_budget", side_effect=spy_check),
            patch("eng_loop.tools.token_counter.TokenCounter", _FakeTokenCounter),
        ):
            result = run_agent(
                model=make_final_answer_model(),
                tools=[tool],
                prompt="task",
                stage_id="impl.code",
                config=BUDGET_CONFIG,
            )

        assert result.error is None
        assert seen_managers, "pre-call budget check was never invoked"
        assert all(isinstance(m, ContextBudgetManager) for m in seen_managers)

    def test_disabled_config_skips_precheck(self) -> None:
        tool = Tool(name="noop", description="d", func=lambda: "ok")
        with (
            patch.object(agent_runner, "_check_context_budget") as mock_check,
            patch("eng_loop.tools.token_counter.TokenCounter", _FakeTokenCounter),
        ):
            result = run_agent(
                model=make_final_answer_model(),
                tools=[tool],
                prompt="task",
                stage_id="impl.code",
                config={"hardware": {"context_window": 200000, "context_budget": {"enabled": False}}},
            )

        assert result.error is None
        mock_check.assert_not_called()

    def test_explicit_budget_manager_wins(self) -> None:
        explicit = ContextBudgetManager(context_window=200000)
        tool = Tool(name="noop", description="d", func=lambda: "ok")
        with (
            patch.object(agent_runner, "_check_context_budget") as mock_check,
            patch("eng_loop.tools.token_counter.TokenCounter", _FakeTokenCounter),
        ):
            result = run_agent(
                model=make_final_answer_model(),
                tools=[tool],
                prompt="task",
                stage_id="impl.code",
                config=BUDGET_CONFIG,
                budget_manager=explicit,
            )

        assert result.error is None
        assert mock_check.call_args.args[0] is explicit

    def test_build_manager_matches_execution_state_source(self) -> None:
        """build_context_budget_manager is the single construction source."""
        from eng_loop.tools.context_budget import build_context_budget_manager
        from eng_loop.tools.execution_state import ExecutionState

        cfg = BUDGET_CONFIG["hardware"]["context_budget"]
        a = build_context_budget_manager(200000, cfg)
        b = ExecutionState._init_budget_manager(200000, cfg)
        assert a._reserved_output == b._reserved_output
        assert a._safety_margin == b._safety_margin
        assert a._context_window == b._context_window

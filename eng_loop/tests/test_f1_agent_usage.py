"""F1.5 — H10: usage_metadata must reach the lifecycle manager.

Before the fix, the final AIMessage was rebuilt from the merged chunk
without usage_metadata/response_metadata, and record_iteration was
hardcoded to 0 tokens — the lifecycle budget never saw real usage.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.tools import Tool

from eng_loop.tools.agent_lifecycle import AgentLifecycleManager
from eng_loop.tools.agent_runner import reset_lifecycle_manager, run_agent


@pytest.fixture(autouse=True)
def _fresh_lifecycle():
    reset_lifecycle_manager()
    yield
    reset_lifecycle_manager()


def make_model(chunks_per_iteration: list[list]) -> MagicMock:
    mock_with_tools = MagicMock(name="model_with_tools")
    mock_with_tools.stream.side_effect = [iter(chunks) for chunks in chunks_per_iteration]
    mock_model = MagicMock(name="model")
    mock_model.bind_tools.return_value = mock_with_tools
    return mock_model


class TestUsageWiring:
    def test_usage_metadata_reaches_lifecycle(self) -> None:
        lifecycle = AgentLifecycleManager({})
        recorded: list[tuple[int, int]] = []
        original = lifecycle.record_iteration

        def spy(stage_id, input_tokens, output_tokens, tool_call_name="", is_productive=False):
            recorded.append((input_tokens, output_tokens))
            return original(stage_id, input_tokens, output_tokens, tool_call_name, is_productive)

        lifecycle.record_iteration = spy
        tool = Tool(name="noop", description="d", func=lambda: "ok")
        chunk1 = AIMessageChunk(
            content="",
            tool_calls=[{"name": "noop", "args": {}, "id": "c1", "type": "tool_call"}],
            usage_metadata={"input_tokens": 1234, "output_tokens": 56, "total_tokens": 1290},
        )
        chunk2 = AIMessageChunk(content='{"complete": true}')
        model = make_model([[chunk1], [chunk2]])

        with patch("eng_loop.tools.agent_runner.get_lifecycle_manager", return_value=lifecycle):
            result = run_agent(
                model=model,
                tools=[tool],
                prompt="task",
                stage_id="impl.code",
                config={},
            )

        assert result.error is None
        assert recorded, "record_iteration was never called with usage"
        assert recorded[0] == (1234, 56)

    def test_usage_reported_once_per_response(self) -> None:
        """Two tool calls in one response → usage reported exactly once.

        The lifecycle check runs once per tool-calling iteration (after the
        tool loop); the _usage_reported_this_iter guard keeps this correct
        even if it is ever moved inside the per-tool-call loop.
        """
        lifecycle = AgentLifecycleManager({})
        recorded: list[tuple[int, int]] = []
        original = lifecycle.record_iteration

        def spy(stage_id, input_tokens, output_tokens, tool_call_name="", is_productive=False):
            recorded.append((input_tokens, output_tokens))
            return original(stage_id, input_tokens, output_tokens, tool_call_name, is_productive)

        lifecycle.record_iteration = spy
        tool = Tool(name="read", description="d", func=lambda file_path: f"content of {file_path}")
        chunk1 = AIMessageChunk(
            content="",
            tool_calls=[
                {"name": "read", "args": {"file_path": "a.txt"}, "id": "c1", "type": "tool_call"},
                {"name": "read", "args": {"file_path": "b.txt"}, "id": "c2", "type": "tool_call"},
            ],
            usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
        )
        chunk2 = AIMessageChunk(content='{"complete": true}')
        model = make_model([[chunk1], [chunk2]])

        with patch("eng_loop.tools.agent_runner.get_lifecycle_manager", return_value=lifecycle):
            result = run_agent(
                model=model,
                tools=[tool],
                prompt="task",
                stage_id="impl.code",
                config={},
            )

        assert result.error is None
        # One report for the whole response (both tool calls share it)
        assert recorded == [(100, 10)]

    def test_no_usage_metadata_keeps_zeros(self) -> None:
        lifecycle = AgentLifecycleManager({})
        recorded: list[tuple[int, int]] = []
        original = lifecycle.record_iteration

        def spy(stage_id, input_tokens, output_tokens, tool_call_name="", is_productive=False):
            recorded.append((input_tokens, output_tokens))
            return original(stage_id, input_tokens, output_tokens, tool_call_name, is_productive)

        lifecycle.record_iteration = spy
        tool = Tool(name="noop", description="d", func=lambda: "ok")
        chunk1 = AIMessageChunk(content="", tool_calls=[{"name": "noop", "args": {}, "id": "c1", "type": "tool_call"}])
        chunk2 = AIMessageChunk(content='{"complete": true}')
        model = make_model([[chunk1], [chunk2]])

        with patch("eng_loop.tools.agent_runner.get_lifecycle_manager", return_value=lifecycle):
            result = run_agent(
                model=model,
                tools=[tool],
                prompt="task",
                stage_id="impl.code",
                config={},
            )

        assert result.error is None
        assert recorded == [(0, 0)]

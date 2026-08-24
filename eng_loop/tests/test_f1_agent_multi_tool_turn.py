"""F1.5 — H9: one AIMessage per LLM response, not one per tool call.

Before the fix, `messages.append(response)` sat inside the per-tool-call
loop, so a response with N tool calls produced N copies of the AIMessage
interleaved with the ToolMessages — an invalid AIM/TM ordering and
duplicated context.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.tools import Tool

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


class TestMultiToolTurn:
    def test_single_aimessage_for_multiple_tool_calls(self) -> None:
        tool = Tool(name="read", description="d", func=lambda file_path: f"content of {file_path}")
        chunk1 = AIMessageChunk(
            content="",
            tool_calls=[
                {"name": "read", "args": {"file_path": "a.txt"}, "id": "call_1", "type": "tool_call"},
                {"name": "read", "args": {"file_path": "b.txt"}, "id": "call_2", "type": "tool_call"},
            ],
        )
        chunk2 = AIMessageChunk(content='{"complete": true}')
        model = make_model([[chunk1], [chunk2]])

        result = run_agent(
            model=model,
            tools=[tool],
            prompt="read two files",
            stage_id="impl.code",
            config={},
        )

        assert result.error is None
        conv = result.conversation
        # The tool-call AIMessage appears ONCE (before the fix: once per tool
        # call → 2 copies interleaved with the ToolMessages).
        ai_messages = [m for m in conv if isinstance(m, AIMessage)]
        assert len(ai_messages) == 1
        assert len(ai_messages[0].tool_calls) == 2

        ai_idx = conv.index(ai_messages[0])
        after = conv[ai_idx + 1 :]
        # Two ToolMessages, in call order, no AIMessage between them
        assert len(after) == 2
        assert all(isinstance(m, ToolMessage) for m in after)
        assert after[0].tool_call_id == "call_1"
        assert after[1].tool_call_id == "call_2"
        assert after[0].content == "content of a.txt"
        assert after[1].content == "content of b.txt"

        # Conversation starts with the single prompt HumanMessage
        assert isinstance(conv[0], HumanMessage)
        assert result.tool_calls_made == 2

    def test_single_tool_call_still_valid(self) -> None:
        tool = Tool(name="noop", description="d", func=lambda: "ok")
        chunk1 = AIMessageChunk(
            content="",
            tool_calls=[{"name": "noop", "args": {}, "id": "call_1", "type": "tool_call"}],
        )
        chunk2 = AIMessageChunk(content='{"complete": true}')
        model = make_model([[chunk1], [chunk2]])

        result = run_agent(
            model=model,
            tools=[tool],
            prompt="noop",
            stage_id="impl.code",
            config={},
        )

        assert result.error is None
        conv = result.conversation
        ai_messages = [m for m in conv if isinstance(m, AIMessage)]
        assert len(ai_messages) == 1
        tool_msgs = [m for m in conv if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "ok"

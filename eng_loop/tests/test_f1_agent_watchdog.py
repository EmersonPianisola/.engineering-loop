"""F1.5 — H12: stalled stream must raise a real TimeoutError.

Before the fix, the hard watchdog was a daemon thread that `raise`d inside
itself (no effect) and set a flag that was only checked when a chunk
arrived — a stream that stopped producing chunks hung forever.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.tools import Tool

from eng_loop.tools.agent_runner import reset_lifecycle_manager, run_agent


@pytest.fixture(autouse=True)
def _fresh_lifecycle():
    reset_lifecycle_manager()
    yield
    reset_lifecycle_manager()


def make_model(stream_fn) -> MagicMock:
    mock_with_tools = MagicMock(name="model_with_tools")
    # Callable side_effect → invoked on every stream() call (fresh generator)
    mock_with_tools.stream.side_effect = stream_fn
    mock_model = MagicMock(name="model")
    mock_model.bind_tools.return_value = mock_with_tools
    return mock_model


class TestWatchdog:
    def test_stalled_stream_times_out(self) -> None:
        def stalled_stream(messages):
            yield AIMessageChunk(content="partial")
            time.sleep(300)  # never produces another chunk

        model = make_model(stalled_stream)
        tool = Tool(name="noop", description="d", func=lambda: "ok")

        start = time.monotonic()
        result = run_agent(
            model=model,
            tools=[tool],
            prompt="task",
            stage_id="impl.code",
            config={"hardware": {"stage_timeout_seconds": 1}},
        )
        elapsed = time.monotonic() - start

        assert result.error is not None
        assert "hard timeout" in result.error
        # Must fail fast at the deadline, not hang on the stalled stream
        assert elapsed < 10

    def test_fast_stream_completes_before_deadline(self) -> None:
        def fast_stream(messages):
            yield AIMessageChunk(content='{"complete": true}')

        model = make_model(fast_stream)
        tool = Tool(name="noop", description="d", func=lambda: "ok")

        result = run_agent(
            model=model,
            tools=[tool],
            prompt="task",
            stage_id="impl.code",
            config={"hardware": {"stage_timeout_seconds": 30}},
        )

        assert result.error is None
        assert result.data.get("complete") is True

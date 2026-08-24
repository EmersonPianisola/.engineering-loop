"""F3.1 — H13: live streaming.

_stream_with_interrupts must yield events as the graph produces them (no
list() buffering) so the HUD updates live.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from eng_loop.cli import _stream_with_interrupts


def _make_graph(events: list[dict]):
    produced: list[int] = []

    def fake_stream(initial_input, config=None, stream_mode=None):
        for i, ev in enumerate(events):
            produced.append(i)
            yield ev

    graph = MagicMock()
    graph.stream.side_effect = fake_stream
    # No interrupt: next is empty when the stream ends
    graph.get_state.return_value = MagicMock(next=())
    return graph, produced


class TestLiveStream:
    def test_events_yielded_incrementally(self, tmp_path) -> None:
        graph, produced = _make_graph(
            [
                {"current_stage": "init", "status": "running"},
                {"current_stage": "impl.code", "status": "running"},
                {"current_stage": "verify", "status": "running"},
                {"current_stage": "", "status": "done"},
            ]
        )

        gen = _stream_with_interrupts(
            graph,
            {},
            {},
            [],
            {"artifact_root": str(tmp_path)},
            {},
            exec_state=None,
            normalizer=None,
        )

        first = next(gen)
        assert first["current_stage"] == "init"
        # The first event was yielded BEFORE the rest was produced — with the
        # old list() buffering, all events would already be in `produced`.
        assert len(produced) == 1

        rest = list(gen)
        assert [e["current_stage"] for e in rest] == ["impl.code", "verify", ""]
        assert len(produced) == 4

    def test_all_events_delivered_in_order(self, tmp_path) -> None:
        graph, produced = _make_graph(
            [
                {"current_stage": "a", "status": "running"},
                {"current_stage": "b", "status": "done"},
            ]
        )

        events = list(
            _stream_with_interrupts(
                graph,
                {},
                {},
                [],
                {"artifact_root": str(tmp_path)},
                {},
                exec_state=None,
                normalizer=None,
            )
        )

        assert [e["current_stage"] for e in events] == ["a", "b"]
        assert produced == [0, 1]

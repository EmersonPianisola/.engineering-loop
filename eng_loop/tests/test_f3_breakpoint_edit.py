"""F3.2 — H14: breakpoint edit must reach the checkpoint.

Before the fix, `edit_state_in_editor` saved to disk but the resume used the
untouched checkpoint — the edit had no effect. Now `graph.update_state`
applies it (via reducers) before `Command(resume=True)`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from eng_loop.cli import _stream_with_interrupts


class TestBreakpointEdit:
    def test_edit_applied_to_checkpoint_before_resume(self, tmp_path) -> None:
        edited_state = {
            "work_item": {"title": "edited work item"},
            "current_stage": "impl.code",
            "stages": {},
            "status": "running",
        }

        # First stream stops at the breakpoint (one event, then interrupt)
        stream_calls: list = []

        def fake_stream(initial_input, config=None, stream_mode=None):
            stream_calls.append(initial_input)
            if len(stream_calls) == 1:
                yield {"current_stage": "impl.code", "status": "running"}
            else:
                yield {"current_stage": "verify", "status": "done"}

        graph = MagicMock()
        graph.stream.side_effect = fake_stream
        # First get_state: interrupted at impl-code. After the resume, the
        # run completes (next empty) — otherwise the mock would interrupt
        # forever.
        graph.get_state.side_effect = [
            MagicMock(next=("impl-code",), values=edited_state),
            MagicMock(next=()),
        ]

        paths = {"artifact_root": str(tmp_path), "state_file": str(tmp_path / "state.json")}

        with (
            patch("eng_loop.cli.ui.show_breakpoint_menu", return_value="edit") as mock_menu,
            patch(
                "eng_loop.tools.interactive.edit_state_in_editor",
                return_value=edited_state,
            ) as mock_edit,
        ):
            events = list(
                _stream_with_interrupts(
                    graph,
                    {"work_item": {"title": "original"}, "stages": {}, "status": "running"},
                    {"configurable": {"thread_id": "t"}},
                    ["impl-code"],
                    paths,
                    {},
                    exec_state=None,
                    normalizer=None,
                )
            )

        mock_menu.assert_called_once()
        mock_edit.assert_called_once()
        # The edit was applied to the checkpoint (the actual fix)
        graph.update_state.assert_called_once()
        applied = graph.update_state.call_args.args[1]
        assert applied["work_item"]["title"] == "edited work item"
        # And the resume followed
        assert len(events) == 2
        assert events[1]["current_stage"] == "verify"

    def test_no_edit_no_update_state(self, tmp_path) -> None:
        def fake_stream(initial_input, config=None, stream_mode=None):
            yield {"current_stage": "init", "status": "running"}

        graph = MagicMock()
        graph.stream.side_effect = fake_stream
        graph.get_state.return_value = MagicMock(next=())

        with patch("eng_loop.cli.ui.show_breakpoint_menu", return_value="resume") as mock_menu:
            list(
                _stream_with_interrupts(
                    graph,
                    {"stages": {}, "status": "running"},
                    {},
                    [],
                    {"artifact_root": str(tmp_path), "state_file": str(tmp_path / "state.json")},
                    {},
                    exec_state=None,
                    normalizer=None,
                )
            )

        mock_menu.assert_not_called()
        graph.update_state.assert_not_called()

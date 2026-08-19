from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from eng_loop.tools.progress import (
    StageSpinner,
    UIManager,
    _get_active_spinner,
    _stage_ctx,
    log_artifact,
    log_blocked,
    log_complexity,
    log_decision,
    log_iteration,
    log_model_done,
    log_model_invoke,
    log_stage_complete,
    log_stage_done,
    log_stage_enter,
    log_stage_fail,
    log_stage_retry,
    log_stage_skip,
    log_stall_warning,
    stage_context,
    trace_node,
    tracker,
    ui,
)

# ============================================================
# StageSpinner
# ============================================================


class TestStageSpinner:
    def test_constructor_defaults(self):
        mock_console = MagicMock()
        spinner = StageSpinner("test.stage", console=mock_console)
        assert spinner.stage_id == "test.stage"
        assert spinner.tool_count == 0
        assert spinner.console is mock_console
        assert spinner.start_time > 0
        assert spinner._status is None

    def test_constructor_default_console(self):
        spinner = StageSpinner("test.stage")
        assert spinner.stage_id == "test.stage"
        assert spinner.tool_count == 0
        assert spinner.start_time > 0

    def test_start_creates_status(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        mock_console.status.assert_called_once()
        mock_status.start.assert_called_once()
        assert spinner._status is mock_status

    def test_stop_stops_status(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.stop()
        mock_status.stop.assert_called_once()
        assert spinner._status is None

    def test_stop_twice_safe(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.stop()
        spinner.stop()
        assert mock_status.stop.call_count == 1

    def test_update_increments_tool_count(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.update("read", "file.txt")
        spinner.update("write", "file2.txt")
        assert spinner.tool_count == 2

    def test_update_status_format(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.update("read", "file.txt")
        mock_status.update.assert_called_once()
        call_args = mock_status.update.call_args[0][0]
        assert "test.stage" in call_args
        assert "R" in call_args
        assert "read" in call_args
        assert "file.txt" in call_args
        assert "1 tools" in call_args

    def test_update_no_target(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.update("bash")
        call_args = mock_status.update.call_args[0][0]
        assert "$" in call_args
        assert "bash" in call_args

    def test_icons_mapping(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        icons_expected = {
            "read": "R",
            "write": "W",
            "edit": "E",
            "bash": "$",
            "glob": "G",
            "grep": "S",
        }
        for action_type, expected_icon in icons_expected.items():
            spinner.stop()
            spinner._status = mock_status
            mock_status.reset_mock()
            spinner.update(action_type)
            call_args = mock_status.update.call_args[0][0]
            assert expected_icon in call_args

    def test_unknown_action_icon(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.update("unknown_action")
        call_args = mock_status.update.call_args[0][0]
        assert "?" in call_args

    def test_think_truncates_text(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        long_text = "a" * 80
        spinner.think(long_text)
        call_args = mock_status.update.call_args[0][0]
        assert "…" in call_args

    def test_think_short_text_no_truncation(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.think("short text")
        call_args = mock_status.update.call_args[0][0]
        assert "short text" in call_args
        assert "…" not in call_args

    def test_think_exactly_60_chars(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        exact_text = "a" * 60
        spinner.think(exact_text)
        call_args = mock_status.update.call_args[0][0]
        assert "…" not in call_args

    def test_idle(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        spinner = StageSpinner("test.stage", console=mock_console)
        spinner.start()
        spinner.idle()
        call_args = mock_status.update.call_args[0][0]
        assert "waiting" in call_args


# ============================================================
# stage_context
# ============================================================


class TestStageContext:
    def _clear_ctx(self):
        _stage_ctx.active = False
        _stage_ctx.spinner = None

    def test_enter_starts_spinner(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            with stage_context("test.stage") as ctx:
                assert ctx.spinner is not None
                mock_status.start.assert_called_once()
                assert _stage_ctx.active is True

    def test_enter_sets_thread_local(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            with stage_context("test.stage"):
                assert _stage_ctx.active is True
                assert _stage_ctx.spinner is not None

    def test_exit_stops_spinner(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            with stage_context("test.stage"):
                pass
            mock_status.stop.assert_called_once()
            assert _stage_ctx.active is False

    def test_exit_does_not_suppress_exceptions(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            with pytest.raises(ValueError), stage_context("test.stage"):
                raise ValueError("test")
            assert _stage_ctx.active is False

    def test_ctx_spinner_accessible(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            with stage_context("test.stage") as ctx:
                assert isinstance(ctx.spinner, StageSpinner)

    def test_exit_returns_false(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            ctx = stage_context("test.stage")
            ctx.__enter__()
            result = ctx.__exit__(ValueError, ValueError("test"), None)
            assert result is False


class TestGetActiveSpinner:
    def _clear_ctx(self):
        _stage_ctx.active = False
        _stage_ctx.spinner = None

    def test_returns_none_outside_context(self):
        self._clear_ctx()
        assert _get_active_spinner() is None

    def test_returns_spinner_inside_context(self):
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            with stage_context("test.stage"):
                spinner = _get_active_spinner()
                assert spinner is not None
                assert isinstance(spinner, StageSpinner)


# ============================================================
# UIManager
# ============================================================


class TestUIManager:
    def test_constructor(self):
        mgr = UIManager()
        assert mgr._live is None
        assert mgr._stage_times == {}
        assert mgr.console is not None

    def test_set_hud(self):
        mgr = UIManager()
        mock_hud = MagicMock()
        mgr.set_hud(mock_hud)
        assert mgr._hud is mock_hud

    def test_set_normalizer(self):
        mgr = UIManager()
        mock_normalizer = MagicMock()
        mgr.set_normalizer(mock_normalizer)
        assert mgr._normalizer is mock_normalizer

    def test_is_hud_active_false_by_default(self):
        mgr = UIManager()
        assert mgr.is_hud_active() is False

    def test_is_hud_active_true_when_set(self):
        mgr = UIManager()
        mgr.set_hud(MagicMock())
        assert mgr.is_hud_active() is True

    def test_hud_log_when_active(self):
        mgr = UIManager()
        mock_hud = MagicMock()
        mgr.set_hud(mock_hud)
        mgr.hud_log("INFO", "test message")
        mock_hud.log.assert_called_once_with("INFO", "test message")

    def test_hud_log_noop_when_inactive(self):
        mgr = UIManager()
        mgr.hud_log("INFO", "test message")

    def test_render_topology(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_topology(
                work_item="Add feature X",
                active_nodes=["init", "impl.code", "verify"],
                complexity="medium",
                total_available=10,
                work_type="feature",
                ui_project=False,
            )
            assert mock_print.call_count == 2

    def test_render_topology_bugfix(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_topology(
                work_item="Fix bug Y",
                active_nodes=["init", "impl.code"],
                complexity="small",
                work_type="bugfix",
                ui_project=True,
            )
            assert mock_print.call_count == 2

    def test_render_topology_documentation(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_topology(
                work_item="Update docs",
                active_nodes=["init", "impl.code"],
                complexity="small",
                work_type="documentation",
                ui_project=False,
            )
            assert mock_print.call_count == 2

    def test_render_topology_operational(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_topology(
                work_item="Run ops",
                active_nodes=["init", "verify"],
                complexity="small",
                work_type="operational",
                ui_project=True,
            )
            assert mock_print.call_count == 2

    def test_render_progress_bar(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_progress_bar(
                active_stages=["init", "impl.code", "verify"],
                done_stages={"init"},
                current_stage="impl.code",
                status="running",
            )
            mock_print.assert_called_once()
            call_args = mock_print.call_args[0][0]
            assert "1/3" in call_args

    def test_render_progress_bar_done_status(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_progress_bar(
                active_stages=["init", "impl.code"],
                done_stages={"init", "impl.code"},
                current_stage="impl.code",
                status="done",
            )
            call_args = mock_print.call_args[0][0]
            assert "2/2" in call_args

    def test_render_progress_bar_blocked_status(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_progress_bar(
                active_stages=["init", "impl.code"],
                done_stages={"init"},
                current_stage="impl.code",
                status="blocked",
            )
            call_args = mock_print.call_args[0][0]
            assert "1/2" in call_args

    def test_render_progress_bar_percentage(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_progress_bar(
                active_stages=["a", "b", "c", "d", "e"],
                done_stages={"a", "b"},
                current_stage="c",
                status="running",
            )
            call_args = mock_print.call_args[0][0]
            assert "40%" in call_args

    def test_render_evidence_gate_pass(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_evidence_gate(
                node="impl.code",
                passed=True,
                criteria=[("Test coverage", ">80%", True), ("Lint", "clean", True)],
            )
            assert mock_print.call_count == 1

    def test_render_evidence_gate_fail(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_evidence_gate(
                node="impl.code",
                passed=False,
                criteria=[("Test coverage", "65%", False), ("Lint", "clean", True)],
            )
            assert mock_print.call_count == 1

    def test_render_rollback_without_code(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_rollback("syntax error in main.py")
            assert mock_print.call_count == 1

    def test_render_rollback_with_code(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            mgr.render_rollback("syntax error", "def broken(\n    pass")
            assert mock_print.call_count == 2

    def test_render_result_done(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            tracker._stage_durations = {"init": [1.0]}
            mgr.render_result(
                status="done",
                blocking_condition="",
                iterations=1,
                decisions=["Use approach A"],
                stages={"init": {"done": True, "attempts": 1}},
            )
            assert mock_print.call_count >= 2

    def test_render_result_blocked(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            tracker._stage_durations = {"impl.code": [2.0, 3.0]}
            mgr.render_result(
                status="blocked",
                blocking_condition="evidence gate failed",
                iterations=2,
                decisions=[],
                stages={
                    "init": {"done": True, "attempts": 1},
                    "impl.code": {"done": False, "attempts": 2},
                },
            )
            assert mock_print.call_count >= 2

    def test_render_result_halted(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            tracker._stage_durations = {}
            mgr.render_result(
                status="halted",
                blocking_condition="user abort",
                iterations=1,
                decisions=[],
                stages={"init": {"done": False, "attempts": 1}},
            )
            assert mock_print.call_count >= 2

    def test_render_result_with_timing_table(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print") as mock_print:
            tracker._stage_durations = {"init": [1.0], "impl.code": [5.0]}
            mgr.render_result(
                status="done",
                blocking_condition="",
                iterations=1,
                decisions=[],
                stages={
                    "init": {"done": True, "attempts": 1},
                    "impl.code": {"done": True, "attempts": 1},
                },
            )
            assert mock_print.call_count >= 3

    def test_show_breakpoint_menu_continue(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print"), patch("eng_loop.tools.progress.input", return_value="c"):
            result = mgr.show_breakpoint_menu(
                "impl.code",
                {
                    "iteration": 2,
                    "stages": {"impl.code": {"attempts": 3}},
                    "status": "running",
                },
            )
            assert result == "continue"

    def test_show_breakpoint_menu_edit(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print"), patch("eng_loop.tools.progress.input", return_value="e"):
            result = mgr.show_breakpoint_menu(
                "impl.code",
                {
                    "iteration": 1,
                    "stages": {},
                    "status": "running",
                },
            )
            assert result == "edit"

    def test_show_breakpoint_menu_abort(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print"), patch("eng_loop.tools.progress.input", return_value="a"):
            result = mgr.show_breakpoint_menu(
                "impl.code",
                {
                    "iteration": 1,
                    "stages": {},
                    "status": "running",
                },
            )
            assert result == "abort"

    def test_show_breakpoint_menu_eof(self):
        mgr = UIManager()
        with patch.object(mgr.console, "print"), patch("eng_loop.tools.progress.input", side_effect=EOFError):
            result = mgr.show_breakpoint_menu(
                "impl.code",
                {
                    "iteration": 1,
                    "stages": {},
                    "status": "running",
                },
            )
            assert result == "abort"

    def test_show_breakpoint_menu_invalid_then_continue(self):
        mgr = UIManager()
        with (
            patch.object(mgr.console, "print"),
            patch("builtins.print"),
            patch("eng_loop.tools.progress.input", side_effect=["x", "c"]),
        ):
            result = mgr.show_breakpoint_menu(
                "impl.code",
                {
                    "iteration": 1,
                    "stages": {},
                    "status": "running",
                },
            )
            assert result == "continue"

    def test_start_stop_live(self):
        mgr = UIManager()
        mock_live = MagicMock()
        with (
            patch.object(mgr, "_build_dashboard", return_value=MagicMock()),
            patch("eng_loop.tools.progress.Live", return_value=mock_live),
        ):
            mgr.start_live()
            assert mgr._live is mock_live
            mock_live.start.assert_called_once()
            mgr.stop_live()
            mock_live.stop.assert_called_once()
            assert mgr._live is None

    def test_update_dashboard(self):
        mgr = UIManager()
        mock_live = MagicMock()
        mock_panel = MagicMock()
        with (
            patch.object(mgr, "_build_dashboard", return_value=mock_panel),
            patch("eng_loop.tools.progress.Live", return_value=mock_live),
        ):
            mgr.start_live()
            mgr.update_dashboard("impl.code", 1, 2, "writing file", 5.0)
            mock_live.update.assert_called_once()

    def test_update_dashboard_no_live(self):
        mgr = UIManager()
        mgr.update_dashboard("impl.code", 1, 2, "writing", 5.0)


# ============================================================
# Logging Functions (non-HUD mode)
# ============================================================


class TestLoggingFunctions:
    def _reset_ui(self):
        ui._hud = None
        ui._normalizer = None
        import eng_loop.tools.progress as prog

        prog._iter_count = 0
        prog._iter_line = ""
        prog._iter_stage = ""
        prog._rendered_panels.clear()
        prog._live_indicator = None
        prog._live_done_count = 0

    def test_log_stage_enter(self):
        self._reset_ui()
        # First stage entry (iteration 0) prints the entry message
        with patch("eng_loop.tools.progress._iter_count", 0), patch.object(ui.console, "print") as mock_print:
            log_stage_enter("impl.code", 0)
            mock_print.assert_called_once()
            assert "impl.code" in mock_print.call_args[0][0]

    def test_log_stage_enter_subsequent_is_silent(self):
        self._reset_ui()
        # Subsequent entries are silent — spinner handles visual feedback
        with patch("eng_loop.tools.progress._iter_count", 5), patch.object(ui.console, "print") as mock_print:
            log_stage_enter("impl.code", 1)
            mock_print.assert_not_called()

    def test_log_model_invoke(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_model_invoke("impl.code")
            mock_print.assert_called_once()
            assert "impl.code" in mock_print.call_args[0][0]

    def test_log_model_done(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_model_done("impl.code", 2.5)
            mock_print.assert_called_once()
            assert "impl.code" in mock_print.call_args[0][0]

    def test_log_stage_done(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stage_done("impl.code", "feature implemented")
            assert mock_print.call_count == 2

    def test_log_stage_done_no_result(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stage_done("impl.code")
            mock_print.assert_called_once()

    def test_log_stage_done_long_result_truncated(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            long_result = "x" * 200
            log_stage_done("impl.code", long_result)
            assert mock_print.call_count == 2
            second_call = mock_print.call_args_list[1][0][0]
            assert "..." in second_call

    def test_log_stage_complete(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stage_complete("impl.code", 5.0, 10, "done", 1)
            mock_print.assert_called_once()

    def test_log_stage_complete_minimal(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stage_complete("impl.code", 3.0, 5)
            mock_print.assert_called_once()

    def test_log_stage_skip(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stage_skip("verify")
            mock_print.assert_called_once()
            assert "skip" in mock_print.call_args[0][0]
            assert "verify" in mock_print.call_args[0][0]

    def test_log_stage_fail(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stage_fail("impl.code", "test failed")
            mock_print.assert_called_once()
            # Now outputs a Panel — verify it's a Panel with correct properties
            from rich.panel import Panel

            panel = mock_print.call_args[0][0]
            assert isinstance(panel, Panel)
            # Check border style
            assert panel.style == "red" or panel.border_style == "red"

    def test_log_stage_retry(self):
        self._reset_ui()
        # log_stage_retry is now silent — retries are collapsed into completion panel
        with patch.object(ui.console, "print") as mock_print:
            log_stage_retry("impl.code", 2)
            mock_print.assert_not_called()

    def test_log_artifact(self):
        self._reset_ui()
        with patch.object(ui.console, "print"):
            log_artifact("impl.code", "/path/to/file.py")

    def test_log_complexity(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_complexity("medium", True)
            mock_print.assert_called_once()
            assert "medium" in mock_print.call_args[0][0]

    def test_log_blocked(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_blocked("evidence gate failed")
            mock_print.assert_called_once()
            from rich.panel import Panel

            panel = mock_print.call_args[0][0]
            assert isinstance(panel, Panel)
            assert panel.border_style == "red"

    def test_log_decision(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_decision("Use approach A")
            mock_print.assert_called_once()
            assert "decision" in mock_print.call_args[0][0]
            assert "Use approach A" in mock_print.call_args[0][0]

    def test_log_iteration(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            # First iteration prints separator + counter (2 calls)
            # + possibly 1 from clear_live_indicator if _live_indicator was active
            log_iteration(1, "impl.code")
            assert mock_print.call_count >= 2

    def test_log_iteration_inplace(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            # First iteration
            log_iteration(1, "impl.code")
            first_count = mock_print.call_count
            # Second iteration updates in-place (still uses print but with \r)
            log_iteration(2, "impl.code")
            assert mock_print.call_count > first_count

    def test_log_stall_warning(self):
        self._reset_ui()
        with patch.object(ui.console, "print") as mock_print:
            log_stall_warning("impl.code", "no progress for 30s")
            mock_print.assert_called_once()
            from rich.panel import Panel

            panel = mock_print.call_args[0][0]
            assert isinstance(panel, Panel)
            assert panel.border_style == "yellow"


# ============================================================
# trace_node Decorator
# ============================================================


class TestTraceNode:
    def _reset_ui(self):
        ui._hud = None
        ui._normalizer = None

    def test_trace_node_success(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status

        @trace_node("test.stage")
        def my_fn(state):
            return "result"

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            result = my_fn({"iteration": 1})
            assert result == "result"
            mock_console.status.assert_called_once()
            mock_status.start.assert_called_once()
            mock_status.stop.assert_called_once()

    def test_trace_node_logs_enter(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status

        @trace_node("test.stage")
        def my_fn(state):
            return "ok"

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            my_fn({"iteration": 3})
            # Completion panel has stage ID in title
            print_args = [c[0][0] for c in mock_console.print.call_args_list]
            from rich.panel import Panel

            panels = [p for p in print_args if isinstance(p, Panel)]
            titles = [p.title for p in panels]
            completed = any("TEST.STAGE" in t for t in titles)
            assert completed

    def test_trace_node_records_timing(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        tracker._stage_durations = {}

        @trace_node("timed.stage")
        def my_fn(state):
            time.sleep(0.01)
            return "ok"

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            my_fn({"iteration": 1})
            assert "timed.stage" in tracker._stage_durations
            assert len(tracker._stage_durations["timed.stage"]) > 0

    def test_trace_node_exception_reraises(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status

        @trace_node("fail.stage")
        def my_fn(state):
            raise RuntimeError("boom")

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            with pytest.raises(RuntimeError, match="boom"):
                my_fn({"iteration": 1})

    def test_trace_node_exception_logs_fail(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status

        @trace_node("fail.stage")
        def my_fn(state):
            raise RuntimeError("boom")

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            with pytest.raises(RuntimeError):
                my_fn({"iteration": 1})
            # Fail panel has stage ID in title
            print_args = [c[0][0] for c in mock_console.print.call_args_list]
            from rich.panel import Panel

            panels = [p for p in print_args if isinstance(p, Panel)]
            titles = [p.title for p in panels]
            fail_logged = any("FAIL.STAGE" in t for t in titles)
            assert fail_logged

    def test_trace_node_exception_records_timing(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status
        tracker._stage_durations = {}

        @trace_node("fail.stage")
        def my_fn(state):
            time.sleep(0.01)
            raise RuntimeError("boom")

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            with pytest.raises(RuntimeError):
                my_fn({"iteration": 1})
            assert "fail.stage" in tracker._stage_durations

    def test_trace_node_hud_active_skips_spinner(self):
        self._reset_ui()
        mock_console = MagicMock()

        @trace_node("hud.stage")
        def my_fn(state):
            return "ok"

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = True
            result = my_fn({"iteration": 1})
            assert result == "ok"
            mock_console.status.assert_not_called()

    def test_trace_node_preserves_function_metadata(self):
        self._reset_ui()

        @trace_node("meta.stage")
        def named_fn(state):
            return "ok"

        assert named_fn.__name__ == "named_fn"

    def test_trace_node_passes_args_kwargs(self):
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status

        @trace_node("args.stage")
        def my_fn(state, extra=None, flag=False):
            return (extra, flag)

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            result = my_fn({"iteration": 1}, extra="hello", flag=True)
            assert result == ("hello", True)

    def test_trace_node_skip_renders_cached_panel(self):
        """When handler calls log_stage_skip, trace_node renders cached panel."""
        self._reset_ui()
        mock_console = MagicMock()
        mock_status = MagicMock()
        mock_console.status.return_value = mock_status

        @trace_node("skip.stage")
        def my_fn(state):
            log_stage_skip("skip.stage", "already done")
            return "skipped"

        with patch("eng_loop.tools.progress.ui") as mock_ui:
            mock_ui.console = mock_console
            mock_ui.is_hud_active.return_value = False
            result = my_fn({"iteration": 1})
            assert result == "skipped"
            # Should render a Panel (cached), not a Table-based completion panel
            panel_calls = [c[0][0] for c in mock_console.print.call_args_list if type(c[0][0]).__name__ == "Panel"]
            assert len(panel_calls) >= 1
            # The panel title should contain the cached marker
            panel = panel_calls[0]
            assert "\u21bb" in str(panel.title) or "SKIP.STAGE" in str(panel.title)

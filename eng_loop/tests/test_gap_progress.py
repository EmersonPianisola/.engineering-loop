from __future__ import annotations

"""FASE 5E — UIManager, progress rendering, HUD lifecycle gap tests."""

from unittest.mock import MagicMock, patch

from eng_loop.tools.progress import (
    StageSpinner,
    UIManager,
    console,
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
    ui,
)


class TestUIManagerRendering:
    def test_render_topology(self):
        m = UIManager()
        m.console = console
        m.render_topology("Test", ["init", "impl-code"], "small", 26, "feature", False)

    def test_render_progress_bar(self):
        m = UIManager()
        m.console = console
        m.render_progress_bar(["init", "impl-code"], {"init"}, "impl-code", "running")

    def test_render_result_done(self):
        m = UIManager()
        m.console = console
        m.render_result("done", "", 5, ["d1"], {"init": {"done": True, "attempts": 1}})

    def test_render_result_blocked(self):
        m = UIManager()
        m.console = console
        m.render_result(
            "blocked",
            "max attempts",
            10,
            [],
            {"init": {"done": True, "attempts": 1}, "impl.code": {"done": False, "attempts": 3}},
        )

    def test_render_evidence_gate_pass(self):
        m = UIManager()
        m.console = console
        m.render_evidence_gate("verify", True, [("c1", "r1", True)])

    def test_render_evidence_gate_fail(self):
        m = UIManager()
        m.console = console
        m.render_evidence_gate("verify", False, [("c1", "r1", False)])

    def test_render_rollback(self):
        m = UIManager()
        m.console = console
        m.render_rollback("test failure", "def f(): pass")


class TestStageSpinnerGap:
    def test_update(self):
        sp = StageSpinner("t", console=console)
        sp._status = MagicMock()
        sp.update("read", "/f.txt")
        assert sp.tool_count == 1
        sp._status.update.assert_called()

    def test_think(self):
        sp = StageSpinner("t", console=console)
        sp._status = MagicMock()
        sp.think("Analyzing...")
        sp._status.update.assert_called()

    def test_idle(self):
        sp = StageSpinner("t", console=console)
        sp._status = MagicMock()
        sp.idle()
        sp._status.update.assert_called()


class TestStageContextGap:
    def test_context_manager(self):
        with stage_context("t") as ctx:
            assert ctx.stage_id == "t"
        assert ctx.spinner._status is None


class TestTraceNodeGap:
    def test_decorator(self):
        @trace_node("t")
        def h(s):
            return {"r": "ok"}

        with patch("eng_loop.tools.progress.log_stage_enter"), patch("eng_loop.tools.progress.log_stage_complete"):
            assert h({"iteration": 1}) == {"r": "ok"}

    def test_exception(self):
        @trace_node("t")
        def h(s):
            raise ValueError("err")

        with patch("eng_loop.tools.progress.log_stage_enter"), patch("eng_loop.tools.progress.log_stage_fail") as mf:
            try:
                h({})
            except ValueError:
                pass
        mf.assert_called()


class TestProgressLoggingGap:
    def test_log_stage_enter(self):
        log_stage_enter("init", 1)

    def test_log_stage_done(self):
        log_stage_done("init", "validated")

    def test_log_stage_skip(self):
        log_stage_skip("init.bdd")

    def test_log_stage_fail(self):
        log_stage_fail("verify", "FAIL")

    def test_log_stage_retry(self):
        log_stage_retry("impl.code", 2)

    def test_log_artifact(self):
        log_artifact("impl.code", "/f.txt")

    def test_log_complexity(self):
        log_complexity("medium", False)

    def test_log_blocked(self):
        log_blocked("reason")

    def test_log_decision(self):
        log_decision("Use REST")

    def test_log_iteration(self):
        log_iteration(3, "impl-code")

    def test_log_model_invoke(self):
        log_model_invoke("init")

    def test_log_model_done(self):
        log_model_done("init", 5.2)

    def test_log_stage_complete(self):
        log_stage_complete("init", 5.0, 3, "validated")

    def test_log_stall_warning(self):
        log_stall_warning("impl.code", "repeat 3x")


class TestHUDLifecycleGap:
    def test_with_hud(self):
        mh = MagicMock()
        ui._hud = mh
        log_stage_enter("init", 1)
        mh.set_current_stage.assert_called_with("init")

    def test_without_hud(self):
        ui._hud = None
        log_stage_enter("init", 1)

    def test_done_with_hud(self):
        mh = MagicMock()
        ui._hud = mh
        log_stage_done("init", "ok")
        mh.log.assert_called()

    def test_fail_with_hud(self):
        mh = MagicMock()
        mn = MagicMock()
        ui._hud = mh
        ui._normalizer = mn
        log_stage_fail("verify", "FAIL")
        mh.log.assert_called()

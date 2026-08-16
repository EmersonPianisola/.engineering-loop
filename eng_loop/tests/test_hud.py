from __future__ import annotations

"""Tests for HUD rendering, ActionLog, and HUD helper functions."""

from eng_loop.tools.hud import (
    CLASS_ICONS,
    PHASE_COLORS,
    PHASE_LABELS,
    PHASE_ORDER,
    STAGE_CLASSES,
    ActionLog,
    HUDRenderer,
    _draw_bar,
    _format_duration,
    _get_phase,
    _node_to_stage,
    _stage_to_node,
)


class TestActionLog:
    def test_append_and_render(self):
        log = ActionLog(max_lines=5)
        log.append("INFO", "Test message")
        panel = log.render()
        assert panel is not None

    def test_max_lines_enforced(self):
        log = ActionLog(max_lines=3)
        for i in range(10):
            log.append("INFO", f"Message {i}")
        assert len(log.lines) == 3
        entries = list(log.lines)
        assert "Message 7" in entries[0]
        assert "Message 9" in entries[2]

    def test_log_levels(self):
        log = ActionLog()
        log.append("DEBUG", "debug msg")
        log.append("WARN", "warn msg")
        log.append("ERROR", "error msg")
        log.append("SYS", "sys msg")
        log.append("STALL", "stall msg")
        assert len(log.lines) == 5

    def test_thread_safety(self):
        import threading

        log = ActionLog(max_lines=100)

        def append_many(prefix):
            for i in range(50):
                log.append("INFO", f"{prefix}-{i}")

        threads = [threading.Thread(target=append_many, args=(f"t{j}",)) for j in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(log.lines) == 100


class TestStageMappings:
    def test_all_stages_have_class(self):
        from eng_loop.state import STAGE_ORDER

        for stage_id in STAGE_ORDER:
            assert stage_id in STAGE_CLASSES, f"Missing class for {stage_id}"

    def test_all_classes_have_icons(self):
        for cls_name, _ in STAGE_CLASSES.values():
            assert cls_name in CLASS_ICONS, f"Missing icon for class {cls_name}"

    def test_phase_order_complete(self):
        assert PHASE_ORDER == ["init", "design", "arch", "impl", "verify", "qa", "deploy", "doc", "post"]

    def test_phase_labels(self):
        assert PHASE_LABELS["init"] == "INIT"
        assert PHASE_LABELS["impl"] == "IMPL"
        assert PHASE_LABELS["qa"] == "QA"

    def test_phase_colors(self):
        for phase in PHASE_ORDER:
            assert phase in PHASE_COLORS


class TestHelperFunctions:
    def test_stage_to_node(self):
        assert _stage_to_node("impl.code") == "impl-code"
        assert _stage_to_node("design.user-research") == "design-user-research"
        assert _stage_to_node("init") == "init"

    def test_node_to_stage(self):
        assert _node_to_stage("impl-code") == "impl.code"
        assert _node_to_stage("design-user-research") == "design.user-research"

    def test_get_phase(self):
        assert _get_phase("init") == "init"
        assert _get_phase("impl.code") == "impl"
        assert _get_phase("design.user-research") == "design"
        assert _get_phase("qa.security") == "qa"
        assert _get_phase("post") == "post"

    def test_draw_bar_full(self):
        bar = _draw_bar(10, 10, 10, "green")
        assert "10/10" in bar

    def test_draw_bar_empty(self):
        bar = _draw_bar(0, 10, 10, "red")
        assert "0/10" in bar

    def test_draw_bar_zero_max(self):
        bar = _draw_bar(5, 0, 10, "red")
        assert "5/1" in bar

    def test_format_duration_seconds(self):
        assert _format_duration(30) == "30s"
        assert _format_duration(0) == "0s"

    def test_format_duration_minutes(self):
        assert _format_duration(125) == "2m 5s"

    def test_format_duration_hours(self):
        assert _format_duration(3661) == "1h 1m 1s"


class TestHUDRenderer:
    def test_renderer_creation(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        assert renderer is not None
        assert renderer.action_log is not None

    def test_log_message(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        renderer.log("INFO", "test message")
        assert len(renderer.action_log.lines) == 1

    def test_set_current_stage(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        renderer.set_current_stage("impl.code")
        assert renderer._current_stage == "impl.code"

    def test_clear_current_stage(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        renderer.set_current_stage("impl.code")
        renderer.clear_current_stage()
        assert renderer._current_stage == ""

    def test_role_lookup(self):
        assert HUDRenderer._get_role("impl.code") == "WARRIOR"
        assert HUDRenderer._get_role("init") == "MAGE"
        assert HUDRenderer._get_role("verify") == "INSPECTOR"
        assert HUDRenderer._get_role("qa.security") == "GUARD"
        assert HUDRenderer._get_role("post") == "HERO"

    def test_color_lookup(self):
        assert HUDRenderer._get_color("impl.code") == "green"
        assert HUDRenderer._get_color("init") == "blue"
        assert HUDRenderer._get_color("verify") == "yellow"

    def test_quest_status_style(self):
        renderer = HUDRenderer.__new__(HUDRenderer)
        assert "RUNNING" in renderer._get_quest_status_style("running")
        assert "COMPLETED" in renderer._get_quest_status_style("completed")
        assert "FAILED" in renderer._get_quest_status_style("failed")

    def test_node_status_mark_completed(self):
        renderer = HUDRenderer.__new__(HUDRenderer)
        mark = renderer._node_status_mark("completed", "impl-code")
        assert "\u2713" in mark or "W" in mark

    def test_node_status_mark_active(self):
        renderer = HUDRenderer.__new__(HUDRenderer)
        mark = renderer._node_status_mark("active", "impl-code")
        assert ">" in mark

    def test_node_status_mark_failed(self):
        renderer = HUDRenderer.__new__(HUDRenderer)
        mark = renderer._node_status_mark("failed", "impl-code")
        assert "!" in mark

    def test_hp_bar(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        bar = renderer._hp_bar(3, 5)
        assert "%" in bar

    def test_format_time(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        assert renderer._format_time(30) == "30s"
        assert renderer._format_time(125) == "2m 5s"

    def test_class_for_stage(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        cls_name, color = renderer._class_for_stage("impl.code")
        assert cls_name == "WARRIOR"
        assert color == "green"

    def test_class_for_unknown_stage(self):
        from rich.console import Console

        console = Console(width=80, force_terminal=True)
        renderer = HUDRenderer(console=console)
        cls_name, _color = renderer._class_for_stage("unknown.stage")
        assert cls_name == "NPC"

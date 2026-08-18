from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from eng_loop.tools.cli_renderer import (
    _format_duration,
    _node_color,
    _node_symbol,
    ConsoleRenderer,
)
from eng_loop.tools.cli_viewmodel import (
    DiagnosticEntry,
    EssenceGateInfo,
    EssenceQuestion,
    ExecutionViewModel,
    GraphNodeInfo,
    NodeVisualStatus,
    PipelineMetrics,
    PipelineStatus,
    ProgressInfo,
    ResumeInfo,
)


def make_console():
    from rich.console import Console
    return Console(force_terminal=True, width=80)


def make_vm(**overrides):
    defaults = {
        "pipeline_status": PipelineStatus.RUNNING,
        "work_item": "Test work item",
        "graph_id": "g-1",
        "metrics": PipelineMetrics(
            total_nodes=5,
            completed_nodes=2,
            running_nodes=1,
            pending_nodes=2,
            total_executions=3,
            total_attempts=4,
            retries=1,
        ),
        "progress": ProgressInfo(current=2, total=5),
        "total_elapsed_ms": 125000,
    }
    defaults.update(overrides)
    return ExecutionViewModel(**defaults)


class TestSymbolMapping:
    """PRD §23: Consistent visual symbols."""

    def test_pending(self):
        assert _node_symbol("pending") == "\u25cb"

    def test_running(self):
        assert _node_symbol("running") == "\u25cf"

    def test_success(self):
        assert _node_symbol("success") == "\u2713"

    def test_warning(self):
        assert _node_symbol("warning") == "\u26a0"

    def test_failed(self):
        assert _node_symbol("failed") == "\u2717"

    def test_paused(self):
        assert _node_symbol("paused") == "\u23f8"

    def test_cancelled(self):
        assert _node_symbol("cancelled") == "\u2298"

    def test_unknown(self):
        assert _node_symbol("unknown") == "?"


class TestFormatDuration:
    def test_seconds(self):
        assert _format_duration(45000) == "00:45"

    def test_minutes(self):
        assert _format_duration(125000) == "02:05"

    def test_hours(self):
        assert _format_duration(3661000) == "01:01:01"

    def test_zero(self):
        assert _format_duration(0) == "00:00"

    def test_negative(self):
        assert _format_duration(-100) == "00:00"


class TestConsoleRendererTopology:
    def test_render_topology(self):
        console = make_console()
        renderer = ConsoleRenderer(console)

        nodes = {
            "init": GraphNodeInfo(
                id="init", phase="INIT", visual_status=NodeVisualStatus.SUCCESS
            ),
            "impl.code": GraphNodeInfo(
                id="impl.code", phase="IMPL", visual_status=NodeVisualStatus.RUNNING
            ),
            "post": GraphNodeInfo(
                id="post", phase="POST", visual_status=NodeVisualStatus.PENDING
            ),
        }
        vm = make_vm(
            nodes=nodes,
            phases={"INIT": ["init"], "IMPL": ["impl.code"], "POST": ["post"]},
            metrics=PipelineMetrics(total_nodes=3),
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_topology(vm)
            assert mock_print.call_count == 1


class TestConsoleRendererFinalPanels:
    def test_render_completed(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            pipeline_status=PipelineStatus.COMPLETED,
            metrics=PipelineMetrics(
                total_nodes=5,
                total_executions=7,
                total_attempts=11,
                completed_nodes=5,
            ),
            progress=ProgressInfo(current=5, total=5),
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_completed(vm)
            assert mock_print.call_count == 1
            # Verify it's a Panel with "SUCCESS"
            panel = mock_print.call_args[0][0]
            assert "SUCCESS" in str(panel.renderable)

    def test_render_failed(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            pipeline_status=PipelineStatus.FAILED,
            current_node_id="impl.code",
            metrics=PipelineMetrics(total_attempts=2),
            diagnostics=[DiagnosticEntry(severity="ERROR", message="validation failed")],
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_failed(vm)
            assert mock_print.call_count == 1

    def test_render_waiting_for_input(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
            essence_gate=EssenceGateInfo(
                stage="post",
                questions=[
                    EssenceQuestion(id="q1", severity="high", question="What type?"),
                ],
            ),
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_waiting_for_input(vm)
            assert mock_print.call_count == 1
            panel = mock_print.call_args[0][0]
            content = str(panel.renderable)
            assert "WAITING_FOR_INPUT" in content
            # Must NOT contain "Complete"
            assert "Complete" not in content


class TestConsoleRendererEssenceQuestions:
    def test_render_questions(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            essence_gate=EssenceGateInfo(
                stage="post",
                questions=[
                    EssenceQuestion(
                        id="q1",
                        severity="high",
                        question="What type of cake?",
                        options=["vanilla", "chocolate", "carrot"],
                    ),
                    EssenceQuestion(
                        id="q2",
                        severity="medium",
                        question="Any dietary restrictions?",
                    ),
                ],
            ),
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_essence_questions(vm)
            # Header panel + 2 question panels
            assert mock_print.call_count >= 3

    def test_no_questions_no_render(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(essence_gate=None)

        with patch.object(console, "print") as mock_print:
            renderer.render_essence_questions(vm)
            assert mock_print.call_count == 0


class TestConsoleRendererResume:
    def test_render_resume(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            resume_info=ResumeInfo(
                clarifications_applied=3,
                checkpoint_stage="post",
                invalidated_stages=["post"],
                preserved_stages=["init", "impl.code"],
            ),
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_resume(vm)
            assert mock_print.call_count == 1

    def test_no_resume_info_no_render(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(resume_info=None)

        with patch.object(console, "print") as mock_print:
            renderer.render_resume(vm)
            assert mock_print.call_count == 0


class TestConsoleRendererTiming:
    def test_render_timing(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            history=[
                GraphNodeInfo(
                    id="init",
                    total_duration_ms=6000,
                    executions=[
                        type("NodeExecution", (), {
                            "attempts": [
                                type("AttemptRecord", (), {
                                    "attempt_num": 1, "duration_ms": 3000, "result": "retry"
                                })(),
                                type("AttemptRecord", (), {
                                    "attempt_num": 2, "duration_ms": 3000, "result": "success"
                                })(),
                            ]
                        })(),
                    ],
                ),
            ],
            nodes={"init": GraphNodeInfo(id="init", total_duration_ms=6000)},
            total_elapsed_ms=6000,
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_timing(vm)
            assert mock_print.call_count == 1


class TestConsoleRendererDiagnostics:
    def test_render_diagnostics(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            diagnostics=[
                DiagnosticEntry(severity="WARN", message="Fallback used", node_id="init"),
                DiagnosticEntry(severity="ERROR", message="File missing", node_id="impl.code"),
            ],
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_diagnostics(vm)
            assert mock_print.call_count == 2

    def test_no_diagnostics_no_render(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(diagnostics=[])

        with patch.object(console, "print") as mock_print:
            renderer.render_diagnostics(vm)
            assert mock_print.call_count == 0


class TestConsoleRendererArchitectDiagnostic:
    def test_optional_file_warning(self):
        console = make_console()
        renderer = ConsoleRenderer(console)

        with patch.object(console, "print") as mock_print:
            renderer.render_architect_diagnostic(
                node_id="dynamic.architect",
                severity="WARN",
                message="dynamic-architect.md not found",
                is_required=False,
            )
            assert mock_print.call_count == 1
            panel = mock_print.call_args[0][0]
            assert "fallback" in str(panel.renderable).lower()

    def test_required_file_error(self):
        console = make_console()
        renderer = ConsoleRenderer(console)

        with patch.object(console, "print") as mock_print:
            renderer.render_architect_diagnostic(
                node_id="dynamic.architect",
                severity="FATAL",
                message="Required stage missing",
                is_required=True,
            )
            assert mock_print.call_count == 1
            panel = mock_print.call_args[0][0]
            assert "aborted" in str(panel.renderable).lower()


class TestConsoleRendererFinal:
    def test_render_final_completed(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            pipeline_status=PipelineStatus.COMPLETED,
            metrics=PipelineMetrics(
                total_nodes=5, completed_nodes=5,
                total_executions=5, total_attempts=5,
            ),
            nodes={"init": GraphNodeInfo(id="init", total_duration_ms=1000)},
            history=[GraphNodeInfo(id="init", total_duration_ms=1000)],
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_final(vm)
            # render_completed + render_timing
            assert mock_print.call_count >= 2

    def test_render_final_failed(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            pipeline_status=PipelineStatus.FAILED,
            diagnostics=[DiagnosticEntry(severity="FATAL", message="error")],
            nodes={"init": GraphNodeInfo(id="init", total_duration_ms=1000)},
            history=[GraphNodeInfo(id="init", total_duration_ms=1000)],
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_final(vm)
            assert mock_print.call_count >= 2

    def test_render_final_waiting(self):
        console = make_console()
        renderer = ConsoleRenderer(console)
        vm = make_vm(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
            essence_gate=EssenceGateInfo(
                stage="post",
                questions=[EssenceQuestion(id="q1", severity="high", question="What?")],
            ),
        )

        with patch.object(console, "print") as mock_print:
            renderer.render_final(vm)
            # render_waiting + render_questions + render_timing
            assert mock_print.call_count >= 3

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from eng_loop.tools.cli_events import PipelineEvent
    from eng_loop.tools.cli_viewmodel import ExecutionViewModel
    from eng_loop.tools.event_bus import EventBus


class LegacyRenderer:
    """Adapter that consumes ExecutionViewModel and delegates to progress.py.

    This allows the legacy log-based output to be driven by the new event
    model rather than being coupled to the engine directly. Temporary during
    transition.
    """

    def __init__(
        self,
        console: Console,
        event_bus: EventBus | None = None,
    ) -> None:
        self.console = console
        self.event_bus = event_bus
        self._rendered_nodes: set[str] = set()

    def on_event(self, event: PipelineEvent) -> None:
        """Handle events by delegating to progress.py functions."""
        from eng_loop.tools.progress import (
            log_stage_complete,
            log_stage_enter,
            log_stage_fail,
            log_stage_skip,
            tracker,
        )

        et = event.event_type

        if et == "node.started":
            log_stage_enter(event.node_id, iteration=event.attempt)

        elif et == "node.completed":
            duration_ms = event.metadata.get("duration_ms", 0)
            tool_count = event.metadata.get("tool_count", 0)
            log_stage_complete(
                event.node_id,
                duration=duration_ms / 1000.0,
                tool_calls=tool_count,
            )
            self._rendered_nodes.add(event.node_id)

        elif et == "node.failed":
            error = event.metadata.get("error", event.message)
            log_stage_fail(event.node_id, error)

        elif et == "node.skipped":
            reason = event.metadata.get("reason", "")
            log_stage_skip(event.node_id, reason)

        elif et == "pipeline.completed":
            tracker.stop_loop()

    def render_final(self, vm: ExecutionViewModel) -> None:
        """Render final result using the legacy UIManager.render_result()."""
        from eng_loop.tools.progress import ui

        stages = {}
        for node in vm.nodes.values():
            stage_data = {
                "done": node.visual_status.value == "success",
                "attempts": sum(len(e.attempts) for e in node.executions),
            }
            if node.error_message:
                stage_data["error"] = node.error_message
            stages[node.id] = stage_data

        status_map = {
            "completed": "done",
            "failed": "failed",
            "cancelled": "halted",
            "waiting_for_input": "waiting_for_input",
        }

        status = status_map.get(vm.pipeline_status.value, "running")
        blocking = ""
        if vm.pipeline_status.value == "waiting_for_input":
            blocking = "essence_clarification_needed"
        elif vm.pipeline_status.value == "failed":
            for d in vm.diagnostics:
                if d.severity in ("ERROR", "FATAL"):
                    blocking = d.message
                    break

        active_nodes = list(vm.nodes.keys())

        ui.render_result(
            status=status,
            blocking_condition=blocking,
            iterations=vm.metrics.total_executions,
            decisions=[],
            stages=stages,
            active_nodes=active_nodes,
        )

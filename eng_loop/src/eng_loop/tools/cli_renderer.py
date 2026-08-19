from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress as RichProgress
from rich.table import Table
from rich.tree import Tree

from eng_loop.tools.cli_viewmodel import PipelineStatus

if TYPE_CHECKING:
    from eng_loop.tools.cli_events import PipelineEvent
    from eng_loop.tools.cli_viewmodel import ContextBudgetInfo, ExecutionViewModel
    from eng_loop.tools.event_bus import EventBus


# ─── Symbol mapping (renderer decides visual representation) ────────

_SYMBOL_MAP: dict[str, str] = {
    "pending": "\u25cb",  # ○
    "running": "\u25cf",  # ●
    "success": "\u2713",  # ✓
    "warning": "\u26a0",  # ⚠
    "failed": "\u2717",  # ✗
    "paused": "\u23f8",  # ⏸
    "cancelled": "\u2298",  # ⊘
}

_COLOR_MAP: dict[str, str] = {
    "pending": "dim white",
    "running": "bold cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "failed": "bold red",
    "paused": "bold yellow",
    "cancelled": "dim red",
}

_PHASE_COLORS: dict[str, str] = {
    "INIT": "blue",
    "DESIGN": "cyan",
    "ARCH": "magenta",
    "IMPL": "green",
    "VERIFY": "yellow",
    "QA": "red",
    "DEPLOY": "bright_blue",
    "DOC": "bright_cyan",
    "POST": "white",
}

_DIAGNOSTIC_COLORS: dict[str, str] = {
    "INFO": "blue",
    "WARN": "yellow",
    "ERROR": "red",
    "FATAL": "bold red",
}

_PRESSURE_COLORS: dict[str, str] = {
    "safe": "green",
    "watch": "yellow",
    "pressure": "orange3",
    "exhausted": "bold red",
}

_PRESSURE_SYMBOLS: dict[str, str] = {
    "safe": "",
    "watch": "",
    "pressure": "\u26a0 ",  # ⚠
    "exhausted": "\u2717 ",  # ✗
}


def _format_duration(ms: int) -> str:
    """Format milliseconds as HH:MM:SS or MM:SS."""
    if ms < 0:
        return "00:00"
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _node_symbol(status: str) -> str:
    """Get the display symbol for a node status."""
    return _SYMBOL_MAP.get(status, "?")


def _node_color(status: str) -> str:
    """Get the Rich color for a node status."""
    return _COLOR_MAP.get(status, "white")


def _format_tokens(tokens: int) -> str:
    """Format token count with K/M suffix."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.1f}k"
    return str(tokens)


def _context_bar(used: int, total: int, width: int = 16) -> str:
    """Render a context usage bar."""
    if total <= 0:
        return "\u2591" * width
    filled = int(width * used / total)
    filled = min(filled, width)
    return "\u2588" * filled + "\u2591" * (width - filled)


class ConsoleRenderer:
    """Consumes ExecutionViewModel, produces terminal output.

    Presentation-only. Contains Rich formatting, ANSI codes, layout.
    The ViewModel it receives is presentation-agnostic.
    """

    def __init__(
        self,
        console: Console,
        event_bus: EventBus | None = None,
    ) -> None:
        self.console = console
        self.event_bus = event_bus
        self._live_progress: RichProgress | None = None
        self._progress_task: int | None = None

    # ─── Event handler (for live updates) ─────────────────────────

    def on_event(self, event: PipelineEvent) -> None:
        """Called by EventBus for each event. Used for live updates."""
        # Override in subclasses or use render_live() directly

    # ─── Topology View (PRD §7, §8) ────────────────────────────────

    def render_topology(self, vm: ExecutionViewModel) -> None:
        """Render persistent graph topology view grouped by phase."""
        phases = vm.phases
        nodes = vm.nodes

        phase_order = [
            "INIT",
            "DESIGN",
            "ARCH",
            "IMPL",
            "VERIFY",
            "QA",
            "DEPLOY",
            "DOC",
            "POST",
        ]

        # Sort phases: known phases first in order, then unknown
        sorted_phases = []
        for p in phase_order:
            if p in phases:
                sorted_phases.append(p)
        for p in phases:
            if p not in phase_order:
                sorted_phases.append(p)

        tree = Tree(f"[bold blue]Graph Topology[/bold blue][dim] ({vm.metrics.total_nodes} nodes)[/dim]")

        for phase in sorted_phases:
            color = _PHASE_COLORS.get(phase, "white")
            branch = tree.add(f"[bold {color}]{phase}[/bold {color}]")

            for node_id in phases.get(phase, []):
                node = nodes.get(node_id)
                if not node:
                    branch.add(f"[dim]{node_id}[/dim]")
                    continue

                symbol = _node_symbol(node.visual_status.value)
                color_str = _node_color(node.visual_status.value)
                label = f"[{color_str}]{symbol} {node_id}[/{color_str}]"

                if node.is_container and node.children:
                    child_branch = branch.add(label)
                    for child_id in node.children:
                        child = nodes.get(child_id)
                        if child:
                            c_symbol = _node_symbol(child.visual_status.value)
                            c_color = _node_color(child.visual_status.value)
                            child_branch.add(f"[{c_color}]{c_symbol} {child_id}[/{c_color}]")
                else:
                    # Show retry count
                    attempts = sum(len(e.attempts) for e in node.executions)
                    if attempts > 1:
                        label += f" [dim]x{attempts}[/dim]"
                    branch.add(label)

        self.console.print(
            Panel(
                tree,
                title="GRAPH TOPOLOGY",
                subtitle=vm.work_item or "",
                border_style="blue",
            )
        )

    # ─── Live Execution Panel (PRD §9) ─────────────────────────────

    def render_live(self, vm: ExecutionViewModel) -> None:
        """Render the single dominant execution area with progress bar."""
        m = vm.metrics
        progress = vm.progress

        # Build progress bar string
        bar_width = 20
        if progress.total > 0:
            filled = int(bar_width * progress.current / progress.total)
        else:
            filled = 0
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        progress_str = f"{progress.current}/{progress.total}"

        # Current stage info
        current_line = ""
        if vm.current_node_id:
            symbol = _node_symbol("running")
            current_line = f"{symbol} [bold yellow]{vm.current_node_id}[/bold yellow]"
        elif vm.pipeline_status.value == "planning":
            current_line = "[dim]Planning topology...[/dim]"
        elif vm.pipeline_status.value == "waiting_for_input":
            current_line = "[bold yellow]Waiting for input[/bold yellow]"

        elapsed = _format_duration(vm.total_elapsed_ms)
        attempt_info = f"  attempt {vm.current_attempt}" if vm.current_attempt > 1 else ""

        lines = [
            "[bold]CURRENT STAGE[/bold]",
            "",
            f"  {current_line}",
            "",
            f"  [dim]Elapsed[/dim]    [{elapsed}]{attempt_info}",
            f"  [dim]Tools[/dim]      [{vm.current_tool_count}]",
        ]

        # Context budget line
        budget_line = self._render_context_budget_compact(vm.context_budget)
        if budget_line:
            lines.append("")
            lines.append(f"  {budget_line}")

        lines.extend(
            [
                "",
                "  [bold]Progress[/bold]",
                f"  [{bar}]  {progress_str}",
            ]
        )

        self.console.print("\n".join(lines))

    def _render_context_budget_compact(self, budget: ContextBudgetInfo | None) -> str:
        """Render compact context budget line for live display."""
        if not budget or budget.context_window <= 0:
            return ""

        pressure = budget.pressure or "safe"
        color = _PRESSURE_COLORS.get(pressure, "white")
        symbol = _PRESSURE_SYMBOLS.get(pressure, "")
        pct = budget.usage_percentage
        bar = _context_bar(budget.used_tokens, budget.context_window)

        used_str = _format_tokens(budget.used_tokens)
        total_str = _format_tokens(budget.context_window)
        safe_str = _format_tokens(max(budget.safe_remaining, 0))

        line = (
            f"[{color}]{symbol}Context[/]  "
            f"{used_str} / {total_str}  "
            f"[{color}]{bar}[/{color}]  "
            f"[{color}]{pct:.1f}%[/{color}]  "
            f"[bold]{pressure.upper()}[/]"
        )

        if pressure in ("pressure", "exhausted"):
            line += f"\n  Safe remaining: {safe_str}"
            if pressure == "pressure":
                line += "  [orange3]Compaction recommended[/]"

        return line

    def render_context_exhaustion(self, vm: ExecutionViewModel) -> None:
        """Render context budget exhaustion panel with action options."""
        budget = vm.context_budget
        if not budget or budget.pressure != "exhausted":
            return

        used_str = _format_tokens(budget.used_tokens)
        total_str = _format_tokens(budget.context_window)

        content = (
            f"[bold red]{used_str} / {total_str} tokens[/bold red]\n\n"
            f"Next call may exceed context window.\n"
            f"Execution paused to prevent context overflow.\n\n"
            f"[bold]Action:[/bold]\n"
            f"[1] Compact context\n"
            f"[2] Reduce output budget\n"
            f"[3] Retry with summarized history\n"
            f"[4] Abort"
        )

        self.console.print(
            Panel(
                content,
                title="[bold red]\u2717 CONTEXT BUDGET EXHAUSTED[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )

    # ─── Execution History (PRD §10) ───────────────────────────────

    def render_history(self, vm: ExecutionViewModel) -> None:
        """Render completed nodes in stable history."""
        if not vm.history:
            return

        rows = []
        for node in vm.history:
            symbol = _node_symbol(node.visual_status.value)
            color = _node_color(node.visual_status.value)
            duration = _format_duration(node.total_duration_ms)

            # Count total attempts across executions
            total_attempts = sum(len(e.attempts) for e in node.executions)
            retry_suffix = f" [dim]x{total_attempts}[/dim]" if total_attempts > 1 else ""

            rows.append(f"[{color}]{symbol} {node.id:<20}[/]{duration}{retry_suffix}")

        # Also show pending/running nodes
        for node_id, node in vm.nodes.items():
            if node.visual_status.value in ("running", "pending"):
                symbol = _node_symbol(node.visual_status.value)
                color = _node_color(node.visual_status.value)
                rows.append(f"[{color}]{symbol} {node.id:<20}[/]")

        self.console.print("[bold]EXECUTION HISTORY[/bold]")
        for row in rows:
            self.console.print(f"  {row}")

    # ─── Retry Detail (PRD §11) ────────────────────────────────────

    def render_retry_detail(self, vm: ExecutionViewModel, node_id: str) -> None:
        """Render detailed retry information for a specific node."""
        node = vm.nodes.get(node_id)
        if not node:
            return

        lines = [f"[bold]{node.id}[/bold]"]

        for exec_record in node.executions:
            for attempt in exec_record.attempts:
                duration = _format_duration(attempt.duration_ms)
                result = attempt.result.upper()
                lines.append(f"  attempt #{attempt.attempt_num}\n    duration {duration}\n    result   {result}")

        self.console.print("\n".join(lines))

    # ─── Final Result Panels (PRD §19) ─────────────────────────────

    def render_completed(self, vm: ExecutionViewModel) -> None:
        """Render the final success panel."""
        m = vm.metrics
        elapsed = _format_duration(vm.total_elapsed_ms)

        content = (
            f"[bold]Status[/bold]   [bold green]SUCCESS[/bold green]\n"
            f"[bold]Graph[/bold]    {m.total_nodes} nodes\n"
            f"[bold]Executions[/bold] {m.total_executions}\n"
            f"[bold]Attempts[/bold] {m.total_attempts}\n"
            f"[bold]Duration[/bold] {elapsed}"
        )

        self.console.print(
            Panel(
                content,
                title="[bold]Engineering Loop Complete[/bold]",
                border_style="green",
                padding=(1, 2),
            )
        )

    def render_failed(self, vm: ExecutionViewModel) -> None:
        """Render the failure panel."""
        m = vm.metrics
        stage = vm.current_node_id or ""

        # Find the failed node's error
        reason = ""
        for node in vm.nodes.values():
            if node.visual_status.value == "failed" and node.error_message:
                reason = node.error_message
                break
        if not reason and vm.diagnostics:
            for d in reversed(vm.diagnostics):
                if d.severity in ("ERROR", "FATAL"):
                    reason = d.message
                    break

        content = (
            f"[bold]Status[/bold]   [bold red]FAILED[/bold red]\n"
            f"[bold]Stage[/bold]    {stage or 'unknown'}\n"
            f"[bold]Attempts[/bold] {m.total_attempts}\n"
        )
        if reason:
            content += f"[bold]Reason[/bold]   {reason}\n"

        self.console.print(
            Panel(
                content,
                title="[bold]Engineering Loop Failed[/bold]",
                border_style="red",
                padding=(1, 2),
            )
        )

    def render_waiting_for_input(self, vm: ExecutionViewModel) -> None:
        """Render the paused/waiting panel.

        NEVER shows 'Engineering Loop Complete' before gate resolution.
        """
        gate = vm.essence_gate
        if not gate:
            return

        content = (
            f"[bold]Status[/bold]   [bold yellow]WAITING_FOR_INPUT[/bold yellow]\n"
            f"[bold]Stage[/bold]    {gate.stage}\n"
            f"[bold]Reason[/bold]   essence_clarification_needed\n"
            f"[bold]Questions[/bold]  {len(gate.questions)}"
        )

        self.console.print(
            Panel(
                content,
                title="[bold]Engineering Loop Paused[/bold]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    def render_cancelled(self, vm: ExecutionViewModel) -> None:
        """Render the cancelled panel."""
        content = "[bold]Status[/bold]   [bold]CANCELLED[/bold]"

        self.console.print(
            Panel(
                content,
                title="[bold]Engineering Loop Cancelled[/bold]",
                border_style="yellow",
                padding=(1, 2),
            )
        )

    # ─── Essence Gate Questions (PRD §13, §15) ────────────────────

    def render_essence_questions(self, vm: ExecutionViewModel) -> None:
        """Render Essence Gate questions for user interaction."""
        gate = vm.essence_gate
        if not gate or not gate.questions:
            return

        self.console.print()
        self.console.print(
            Panel(
                "[bold]Pipeline Paused[/bold]\n\n"
                f"[bold]Reason:[/bold] essence_clarification_needed\n"
                f"[bold]Stage:[/bold] {gate.stage}\n"
                f"[bold]Questions:[/bold] {len(gate.questions)}",
                title="[bold yellow]ESSENCE GATE[/bold yellow]",
                border_style="yellow",
            )
        )

        for i, q in enumerate(gate.questions, 1):
            severity_color = {
                "high": "red",
                "medium": "yellow",
                "low": "green",
            }.get(q.severity, "white")

            header = (
                f"[bold {severity_color}]Q{i}/{len(gate.questions)} \u2022 {q.severity.upper()}[/bold {severity_color}]"
            )

            question_text = f"\n{q.question}"

            finding_context = ""
            if q.finding_summary:
                finding_context = f"\n[dim]Finding: {q.finding_summary}[/dim]"

            options_text = ""
            if q.options:
                options_lines = []
                for j, opt in enumerate(q.options, 1):
                    options_lines.append(f"  [{j}] {opt}")
                options_text = "\n" + "\n".join(options_lines)
            else:
                options_text = "\n  [dim]Type your answer:[/dim]"

            self.console.print(
                Panel(
                    header + question_text + finding_context + options_text,
                    border_style=severity_color,
                    padding=(0, 1),
                )
            )

    # ─── Resumption Panel (PRD §17) ────────────────────────────────

    def render_resume(self, vm: ExecutionViewModel) -> None:
        """Render the resumption panel after Essence Gate clarification."""
        info = vm.resume_info
        if not info:
            return

        lines = [
            f"[bold]Clarifications applied:[/bold] {info.clarifications_applied}",
            "",
            f"[bold]Checkpoint:[/bold] {info.checkpoint_stage}",
        ]

        if info.invalidated_stages:
            lines.append("[bold]Invalidated stages:[/bold]")
            for s in info.invalidated_stages:
                lines.append(f"  \u2022 {s}")

        if info.preserved_stages:
            lines.append("[bold]Preserved stages:[/bold]")
            for s in info.preserved_stages:
                lines.append(f"  \u2022 {s}")

        lines.append("")
        lines.append("[green]Continuing...[/green]")

        self.console.print(
            Panel(
                "\n".join(lines),
                title="[bold green]RESUMING[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )

    # ─── Stage Timing Table (PRD §20) ──────────────────────────────

    def render_timing(self, vm: ExecutionViewModel) -> None:
        """Render the stage timing diagnostic table."""
        if not vm.nodes:
            return

        table = Table(
            title="[bold]Stage Timing[/bold]",
            border_style="blue",
            show_header=True,
        )
        table.add_column("Stage", style="bold cyan", no_wrap=True)
        table.add_column("Total", style="cyan", justify="right")
        table.add_column("Attempts", justify="center")

        for node in vm.history:
            total_attempts = sum(len(e.attempts) for e in node.executions)
            table.add_row(
                node.id,
                _format_duration(node.total_duration_ms),
                str(total_attempts),
            )

        # Total row
        total_ms = sum(n.total_duration_ms for n in vm.nodes.values())
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold cyan]{_format_duration(vm.total_elapsed_ms)}[/bold cyan]",
            "",
        )

        self.console.print(table)

    # ─── Event Stream (PRD §21) ────────────────────────────────────

    def render_events(
        self,
        events: list[PipelineEvent],
        max_events: int = 20,
    ) -> None:
        """Render the optional event stream."""
        if not events:
            return

        shown = events[-max_events:]
        lines = ["[bold]EVENTS[/bold]"]

        for event in shown:
            ts = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
            lines.append(f"  {ts}  {event.event_type}")

        self.console.print("\n".join(lines))

    # ─── Diagnostics (PRD §12) ─────────────────────────────────────

    def render_diagnostics(self, vm: ExecutionViewModel) -> None:
        """Render diagnostic messages with severity."""
        if not vm.diagnostics:
            return

        for diag in vm.diagnostics:
            color = _DIAGNOSTIC_COLORS.get(diag.severity, "white")
            severity_symbol = {
                "INFO": "[blue]i[/blue]",
                "WARN": f"[{color}]\u26a0[/{color}]",
                "ERROR": f"[{color}]\u2717[/{color}]",
                "FATAL": f"[{color}]\u2717[/{color}]",
            }.get(diag.severity, "?")

            node_info = f" [{diag.node_id}]" if diag.node_id else ""

            self.console.print(f"  {severity_symbol} [{color}]{diag.severity}[/{color}]{node_info} {diag.message}")

    # ─── Architect Diagnostics (PRD §12) ───────────────────────────

    def render_architect_diagnostic(
        self,
        node_id: str,
        severity: str,
        message: str,
        is_required: bool = False,
    ) -> None:
        """Render architect infrastructure messages with severity.

        For optional files (fallback available): WARN level.
        For required files (no fallback): ERROR/FATAL level.
        """
        color = _DIAGNOSTIC_COLORS.get(severity, "white")
        symbol = _node_symbol("warning") if severity == "WARN" else _node_symbol("failed")

        if is_required:
            self.console.print(
                Panel(
                    f"[bold red]Required stage definition missing:[/bold red]\n"
                    f"{message}\n\n"
                    f"[bold]Execution aborted.[/bold]",
                    title=f"[bold red]{symbol} {node_id}[/bold red]",
                    border_style="red",
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[yellow]Stage definition not found:[/yellow]\n{message}\n\n[dim]Using fallback definition.[/dim]",
                    title=f"[bold yellow]{symbol} {node_id}[/bold yellow]",
                    border_style="yellow",
                )
            )

    # ─── Final composite rendering ─────────────────────────────────

    def render_final(self, vm: ExecutionViewModel) -> None:
        """Render the appropriate final panel based on pipeline status."""
        status = vm.pipeline_status

        if status == PipelineStatus.COMPLETED:
            self.render_completed(vm)
        elif status == PipelineStatus.FAILED:
            self.render_failed(vm)
        elif status == PipelineStatus.WAITING_FOR_INPUT:
            self.render_waiting_for_input(vm)
            self.render_essence_questions(vm)
        elif status == PipelineStatus.CANCELLED:
            self.render_cancelled(vm)

        # Always show timing table after status
        self.render_timing(vm)

    # ─── Planning indicator (PRD §6) ───────────────────────────────

    def render_planning(self, vm: ExecutionViewModel) -> None:
        """Render the planning phase indicator.

        The Dynamic Architect is visually treated as a planning step,
        not a graph node produced by the graph itself.
        """
        node_id = vm.planning_node_id or "dynamic.architect"
        symbol = _node_symbol(vm.planning_status.value)

        self.console.print(
            Panel(
                f"{symbol} [bold]{node_id}[/bold]\n[dim]Proposing graph topology...[/dim]",
                title="[bold]PLANNING[/bold]",
                border_style="cyan",
            )
        )

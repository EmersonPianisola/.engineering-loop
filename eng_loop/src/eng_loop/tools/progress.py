from __future__ import annotations

import sys
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from rich.live import Live
from rich.syntax import Syntax
from rich.rule import Rule

from eng_loop.tools.timing import TimingTracker, format_time

if TYPE_CHECKING:
    from rich.status import Status as RichStatus


# ─── Console singleton ───────────────────────────────────────────────
# Force UTF-8 on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elif hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True, soft_wrap=False)
tracker = TimingTracker()


# ─── UIManager ────────────────────────────────────────────────────────
class UIManager:
    """Centralized terminal UI controller. All rendering flows through here."""

    def __init__(self) -> None:
        self.console = console
        self._live: Live | None = None
        self._stage_times: dict[str, float] = {}

    # ── Topology Tree ──────────────────────────────────────────────
    def render_topology(
        self,
        work_item: str,
        active_nodes: list[str],
        complexity: str,
        total_available: int = 0,
        work_type: str = "feature",
        ui_project: bool = False,
    ) -> None:
        """Render execution plan as a rich tree grouped by phase.

        Header shows structured classification (work_type, complexity, scope)
        instead of the raw work item prompt.
        """
        work_type_labels = {
            "feature": "[green]FEATURE[/green] — Full loop (design → impl → verify → QA → deploy)",
            "bugfix": "[yellow]BUGFIX[/yellow] — Skips design, keeps implementation + verification",
            "operational": "[cyan]OPERATIONAL[/cyan] — Runs existing code, skips impl/design/arch",
        }
        strategy_line = work_type_labels.get(work_type, f"[white]{work_type}[/white]")

        complexity_colors = {
            "small": "green",
            "medium": "yellow",
            "large": "red",
            "complex": "bold red",
        }
        comp_color = complexity_colors.get(complexity, "white")

        bypassed = []
        if work_type == "operational":
            bypassed.append("Design/Arch/Impl")
        elif work_type == "bugfix":
            bypassed.append("Design stages")
        if not ui_project:
            bypassed.append("E2E/Smoke")

        bypass_line = ""
        if bypassed:
            bypass_line = f" [dim](bypassing {', '.join(bypassed)})[/dim]"

        classification = (
            f"[bold]Strategy:[/bold] {strategy_line}\n"
            f"[bold]Complexity:[/bold] [{comp_color}]{complexity}[/]{bypass_line}\n"
            f"[bold]UI Project:[/bold] {'[green]yes[/green]' if ui_project else '[dim]no[/dim]'}"
        )

        phases = [
            ("INIT", "blue", []),
            ("DESIGN", "cyan", []),
            ("ARCH", "magenta", []),
            ("IMPL", "green", []),
            ("VERIFY", "yellow", []),
            ("QA", "red", []),
            ("DEPLOY", "bright_blue", []),
            ("DOC", "bright_cyan", []),
            ("POST", "white", []),
        ]

        phase_map = {p[0]: p[2] for p in phases}
        for node in active_nodes:
            prefix = node.split(".")[0].upper()
            if prefix in phase_map:
                phase_map[prefix].append(node)

        tree = Tree(f"[bold blue]Execution Plan[/bold blue][dim] ({len(active_nodes)} nodes)[/dim]")

        for name, color, nodes in phases:
            if not nodes:
                continue
            branch = tree.add(f"[bold {color}]{name}[/bold {color}]")
            for n in nodes:
                branch.add(f"[dim]⚙[/dim] {n}")

        header = f"[bold]{len(active_nodes)}[/bold]{f' / {total_available}' if total_available else ''} active"
        subtitle = f"[dim]{work_item}[/dim]"
        self.console.print(
            Panel(tree, title="Graph Topology", subtitle=subtitle, border_style="blue")
        )
        self.console.print(Panel(classification, border_style="blue", padding=(0, 1)))

    # ── Stage Progress Bar ─────────────────────────────────────────
    def render_progress_bar(
        self,
        active_stages: list[str],
        done_stages: set[str],
        current_stage: str,
        status: str = "running",
    ) -> None:
        """Render a compact progress bar with stage status."""
        total = len(active_stages)
        done = len(done_stages)
        pct = int(100 * done / max(total, 1))

        # Build a text-based progress bar using block characters
        bar_width = 30
        filled = int(bar_width * done / max(total, 1))
        bar = "█" * filled + "░" * (bar_width - filled)

        status_icon = {
            "running": "[green]▶[/]",
            "done": "[bold green]✓[/]",
            "blocked": "[bold red]✗[/]",
            "halted": "[bold red]⏸[/]",
        }.get(status, "[yellow]?[/]")

        elapsed_str = tracker.get_loop_elapsed_formatted()
        self.console.print(
            f"{status_icon} [dim]{bar}[/dim] "
            f"[cyan]{done}/{total}[/cyan] "
            f"[bold yellow]{current_stage}[/bold yellow] "
            f"[dim]{pct}% [{elapsed_str}][/dim]"
        )

    # ── Evidence Gate Table ────────────────────────────────────────
    def render_evidence_gate(
        self,
        node: str,
        passed: bool,
        criteria: list[tuple[str, str, bool]],
    ) -> None:
        """Render evidence gate results as a validation matrix."""
        table = Table(
            title=f"Evidence Gate: {node}",
            border_style="green" if passed else "red",
            show_header=True,
        )
        table.add_column("Criterion", style="cyan")
        table.add_column("Result", style="white")
        table.add_column("Status", justify="center", style="bold")

        for criterion, result, ok in criteria:
            status = "[bold green]PASS[/]" if ok else "[bold red]FAIL[/]"
            table.add_row(criterion, result[:60], status)

        icon = "[bold green]✓[/]" if passed else "[bold red]✗[/]"
        self.console.print(
            Panel(
                table,
                title=f"{icon} Quality Verdict",
                border_style="green" if passed else "red",
            )
        )

    # ── Rollback Alert ─────────────────────────────────────────────
    def render_rollback(
        self,
        error_summary: str,
        code_snippet: str | None = None,
    ) -> None:
        """Render a rollback/intercept alert with optional code highlight."""
        self.console.print(
            Panel(
                f"[bold red]Execution intercepted.[/bold red]\n"
                f"[yellow]Context cleaned, rollback applied.[/yellow]\n"
                f"[dim]Signal: {error_summary}[/dim]",
                title="[bold red]⚠ Rollback[/bold red]",
                border_style="red",
            )
        )
        if code_snippet:
            self.console.print(
                Panel(
                    Syntax(code_snippet, "python", theme="monokai", line_numbers=True),
                    title="Failure Context",
                    border_style="red",
                )
            )

    # ── Loop Result Summary ────────────────────────────────────────
    def render_result(
        self,
        status: str,
        blocking_condition: str,
        iterations: int,
        decisions: list[str],
        stages: dict[str, dict],
    ) -> None:
        """Render final loop result as a summary panel."""
        status_style = {
            "done": "[bold green]DONE[/]",
            "blocked": "[bold red]BLOCKED[/]",
            "halted": "[bold yellow]HALTED[/]",
        }.get(status, f"[white]{status}[/]")

        lines = [
            f"[bold]Status:[/bold] {status_style}",
            f"[bold]Iterations:[/bold] {iterations}",
            f"[bold]Stages:[/bold] "
            f"[green]{sum(1 for s in stages.values() if s.get('done'))}[/green]"
            f"/{len(stages)} complete",
            f"[bold]Total Time:[/bold] [cyan]{tracker.get_loop_elapsed_formatted()}[/cyan]",
        ]
        if blocking_condition:
            lines.append(f"[bold red]Blocking:[/bold red] {blocking_condition}")
        if decisions:
            lines.append(f"[bold]Decisions:[/bold] {len(decisions)}")
            for d in decisions:
                lines.append(f"  \u2022 {d}")

        self.console.print(
            Rule("[bold]Engineering Loop Complete[/bold]", style="blue")
        )
        self.console.print(
            Panel("\n".join(lines), border_style="blue")
        )

        # Timing table
        timing_rows = tracker.get_summary()
        if timing_rows:
            table = Table(box=None, padding=(0, 1), show_header=True)
            table.add_column("Stage", style="bold cyan", no_wrap=True)
            table.add_column("Duration", style="cyan", justify="right")
            table.add_column("Attempts", justify="center")

            for row in timing_rows:
                table.add_row(
                    row["stage_id"],
                    row["total"],
                    str(row["attempts"]),
                )

            # Total row
            table.add_row("", "[bold cyan]" + format_time(tracker.get_total_seconds()) + "[/bold cyan]", "")

            self.console.print(
                Panel(table, title="[bold]Stage Timing[/bold]", border_style="blue")
            )

    # ── Live Dashboard ─────────────────────────────────────────────
    def start_live(self, refresh_per_second: float = 2) -> None:
        """Start a Live display context for real-time updates."""
        self._live = Live(
            self._build_dashboard("init", 0, 0, "initializing..."),
            refresh_per_second=refresh_per_second,
            console=self.console,
            screen=False,
        )
        self._live.start()

    def update_dashboard(
        self,
        stage: str,
        iteration: int,
        attempts: int,
        action: str = "",
        elapsed: float = 0,
    ) -> None:
        """Update the live dashboard with current state."""
        if self._live:
            self._live.update(
                self._build_dashboard(stage, iteration, attempts, action, elapsed)
            )

    def stop_live(self) -> None:
        """Stop the Live display."""
        if self._live:
            self._live.stop()
            self._live = None

    def _build_dashboard(
        self,
        stage: str,
        iteration: int,
        attempts: int,
        action: str,
        elapsed: float,
    ) -> Panel:
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("Key", style="bold green", width=18)
        table.add_column("Value", style="white")

        table.add_row("Stage", f"[bold yellow]{stage}[/bold yellow]")
        table.add_row("Iteration", f"{iteration}")
        table.add_row("Attempt", f"{attempts}")
        table.add_row("Elapsed", f"{elapsed:.0f}s")
        table.add_row("Action", f"[dim italic]{action}[/dim italic]")

        return Panel(
            table,
            title="[bold]Engineering Loop[/bold]",
            border_style="green",
            padding=(0, 1),
        )

    # ── Breakpoint Menu ──────────────────────────────────────────
    def show_breakpoint_menu(self, node_id: str, state: dict) -> str:
        """Render breakpoint panel and wait for user input.

        Returns: 'continue', 'edit', or 'abort'
        """
        iteration = state.get("iteration", 0)
        stages = state.get("stages", {})
        stage_data = stages.get(node_id, {})
        attempts = stage_data.get("attempts", 0)
        status = state.get("status", "running")

        body_lines = [
            f"[bold]Iteration:[/bold] {iteration}",
            f"[bold]Attempts:[/bold] {attempts}",
            f"[bold]Status:[/bold] {status}",
            "",
            "[bold yellow]Press a key:[/bold yellow]",
            "  [C]ontinue — resume graph execution",
            "  [E]dit State — open editor with state slice",
            "  [A]bort — halt the loop",
        ]

        self.console.print()
        self.console.print(
            Panel(
                "\n".join(body_lines),
                title=f"[bold red]BREAKPOINT[/bold red] {node_id}",
                border_style="red",
                padding=(1, 2),
            )
        )

        while True:
            try:
                choice = input("[C]/[E]/[A]: ").strip().lower()
                if choice in ("c", "continue"):
                    return "continue"
                if choice in ("e", "edit"):
                    return "edit"
                if choice in ("a", "abort", "q", "quit"):
                    return "abort"
                print("  [yellow]Invalid. Press C, E, or A.[/yellow]")
            except (EOFError, KeyboardInterrupt):
                return "abort"


# ─── Stage Spinner (in-place progress, no scroll pollution) ──────────
class StageSpinner:
    """In-place spinner that replaces append-only tool output during agent execution.

    Uses rich.console.status to show a single updating line with the current
    action, tool count, and elapsed time. When stopped, the line disappears
    and is replaced by the handoff panel.
    """

    ICONS = {
        "read": "R",
        "write": "W",
        "edit": "E",
        "bash": "$",
        "glob": "G",
        "grep": "S",
        "search": "S",
    }

    def __init__(self, stage_id: str, console: Console | None = None) -> None:
        self.stage_id = stage_id
        self.console = console or ui.console
        self.tool_count = 0
        self.start_time = time.monotonic()
        self._status: RichStatus | None = None

    def start(self) -> None:
        self._status = self.console.status(
            f"[bold cyan]{self.stage_id}[/bold cyan] initializing...",
            spinner="dots",
        )
        self._status.start()

    def stop(self) -> None:
        if self._status:
            self._status.stop()
            self._status = None

    def update(self, action_type: str, target: str = "") -> None:
        self.tool_count += 1
        elapsed = time.monotonic() - self.start_time
        icon = self.ICONS.get(action_type, "?")
        target_str = f" {target}" if target else ""
        if self._status:
            self._status.update(
                f"[bold cyan]{self.stage_id}[/bold cyan] "
                f"[cyan]{icon}[/cyan] {action_type}{target_str} "
                f"[dim]({self.tool_count} tools, {elapsed:.0f}s)[/dim]"
            )

    def think(self, text: str) -> None:
        elapsed = time.monotonic() - self.start_time
        truncated = text[:60]
        if len(text) > 60:
            truncated += "…"
        if self._status:
            self._status.update(
                f"[bold cyan]{self.stage_id}[/bold cyan] "
                f"[dim]🧠 {truncated}[/dim] "
                f"[dim]({elapsed:.0f}s)[/dim]"
            )

    def idle(self) -> None:
        elapsed = time.monotonic() - self.start_time
        if self._status:
            self._status.update(
                f"[bold cyan]{self.stage_id}[/bold cyan] "
                f"[dim]waiting… ({elapsed:.0f}s)[/dim]"
            )


# ─── Thread-local stage context ──────────────────────────────────────
# Allows trace_node to activate a spinner that run_agent() picks up
# automatically without modifying node caller signatures.
import threading

_stage_ctx: threading.local = threading.local()


class stage_context:
    """Context manager that activates a StageSpinner for the current thread.

    Usage in trace_node:
        with stage_context(stage_id) as ctx:
            result = fn(state)
            ctx.spinner.stop()
            log_stage_complete(...)

    run_agent() checks _stage_ctx.active and uses spinner.update as progress_cb.
    """

    def __init__(self, stage_id: str) -> None:
        self.stage_id = stage_id
        self.spinner = StageSpinner(stage_id)

    def __enter__(self) -> stage_context:
        self.spinner.start()
        _stage_ctx.active = True  # type: ignore[attr-defined]
        _stage_ctx.spinner = self.spinner  # type: ignore[attr-defined]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.spinner.stop()
        _stage_ctx.active = False  # type: ignore[attr-defined]
        _stage_ctx.spinner = None  # type: ignore[attr-defined]
        return False


def _get_active_spinner() -> StageSpinner | None:
    """Get the active spinner for the current thread, if any."""
    if getattr(_stage_ctx, "active", False):
        return _stage_ctx.spinner  # type: ignore[attr-defined]
    return None


# ─── Global instance ─────────────────────────────────────────────────
ui = UIManager()


# ─── Backward-compatible function API ────────────────────────────────
# These functions delegate to the UIManager but preserve the existing
# calling convention so no other file needs to change.


def log_stage_enter(stage_id: str, iteration: int = 0) -> None:
    ui.console.print(
        f"[dim][iter {iteration}][/dim] [bold cyan]>> {stage_id}[/bold cyan]"
    )


def log_model_invoke(stage_id: str) -> None:
    ui.console.print(f"[dim]  [/dim][yellow]model →[/] {stage_id} [dim]...[/dim]")


def log_model_done(stage_id: str, elapsed: float) -> None:
    ui.console.print(f"[dim]  [/dim][green]model ←[/] {stage_id} [dim]({format_time(elapsed)})[/dim]")


def log_stage_done(stage_id: str, result: str = "") -> None:
    ui.console.print(f"[dim]  [/dim][bold green]done   [/][bold]{stage_id}[/bold]")
    if result:
        truncated = result[:120]
        if len(result) > 120:
            truncated += "..."
        ui.console.print(f"         [dim]{truncated}[/dim]")


def log_stage_complete(
    stage_id: str,
    duration: float,
    tool_calls: int,
    summary: str = "",
    iterations: int = 0,
) -> None:
    """Render a structured handoff panel for a completed stage.

    Replaces the plain 'done stage_id' line with a green panel showing
    duration, tool count, iterations, and result summary.
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="bold dim", width=10)
    table.add_column("Value", style="white")

    table.add_row("Duration", f"[cyan]{format_time(duration)}[/cyan]")
    table.add_row("Tools", f"[cyan]{tool_calls}[/cyan] calls")
    if iterations:
        table.add_row("Iterations", f"[cyan]{iterations}[/cyan]")
    if summary:
        truncated = summary[:100]
        if len(summary) > 100:
            truncated += "\u2026"
        table.add_row("Result", f"[green]{truncated}[/green]")

    ui.console.print(
        Panel(table, title=f"[bold green]\u2713 {stage_id.upper()}[/bold green]", border_style="green")
    )


def log_stage_skip(stage_id: str) -> None:
    ui.console.print(f"[dim]  skip   {stage_id} (already done)[/dim]")


def log_stage_fail(stage_id: str, reason: str) -> None:
    ui.console.print(f"[dim]  [/dim][bold red]fail   [/][bold red]{stage_id}[/]: {reason}")


def log_stage_retry(stage_id: str, attempt: int) -> None:
    ui.console.print(
        f"[dim]  [/dim][yellow]retry  [/][yellow]{stage_id}[/] [dim](attempt {attempt})[/dim]"
    )


def log_artifact(stage_id: str, path: str) -> None:
    ui.console.print(f"  [dim]file   {path}[/dim]")


def log_complexity(complexity: str, ui_project: bool) -> None:
    complexity_colors = {
        "small": "green",
        "medium": "yellow",
        "large": "red",
        "complex": "bold red",
    }
    color = complexity_colors.get(complexity, "white")
    ui_project_str = "true" if ui_project else "false"
    ui.console.print(
        f"  [bold cyan]complexity=[/bold cyan][{color}]{complexity}[/]  "
        f"ui_project=[bold]{ui_project_str}[/bold]"
    )


def log_blocked(reason: str) -> None:
    ui.console.print(f"  [bold red]blocked:[/bold red] {reason}")


def log_decision(text: str) -> None:
    ui.console.print(f"  [bold magenta]decision:[/bold magenta] {text}")


def log_iteration(iteration: int, current_stage: str) -> None:
    ui.console.print()
    ui.console.print(
        Rule(f"[iter {iteration}] stage={current_stage}", style="cyan", align="left")
    )


def log_stall_warning(stage_id: str, report_msg: str) -> None:
    ui.console.print(
        f"  [yellow]stall  {stage_id}: {report_msg}[/yellow]"
    )


def trace_node(stage_id: str):
    """Decorator that logs stage entry, activates spinner, times execution, and renders handoff panel."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(state: dict[str, Any], *args, **kwargs):
            iteration = state.get("iteration", 0)
            log_stage_enter(stage_id, iteration)
            t0 = time.monotonic()
            try:
                with stage_context(stage_id) as ctx:
                    result = fn(state, *args, **kwargs)
                elapsed = time.monotonic() - t0
                tracker.record_stage(stage_id, elapsed)
                log_stage_complete(
                    stage_id,
                    duration=elapsed,
                    tool_calls=ctx.spinner.tool_count,
                )
                return result
            except Exception as e:
                elapsed = time.monotonic() - t0
                tracker.record_stage(stage_id, elapsed)
                log_stage_fail(stage_id, f"{e} ({elapsed:.1f}s)")
                raise
        return wrapper
    return decorator


__all__ = [
    "ui",
    "UIManager",
    "StageSpinner",
    "stage_context",
    "_get_active_spinner",
    "console",
    "tracker",
    "format_time",
    "log_stage_enter",
    "log_model_invoke",
    "log_model_done",
    "log_stage_done",
    "log_stage_complete",
    "log_stage_skip",
    "log_stage_fail",
    "log_stage_retry",
    "log_artifact",
    "log_complexity",
    "log_blocked",
    "log_decision",
    "log_iteration",
    "log_stall_warning",
    "trace_node",
]

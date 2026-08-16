from __future__ import annotations

import sys
import time
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

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
_null_console = Console(quiet=True)
tracker = TimingTracker()


# ─── UIManager ────────────────────────────────────────────────────────
class UIManager:
    """Centralized terminal UI controller. All rendering flows through here."""

    def __init__(self) -> None:
        self.console = console
        self._live: Live | None = None
        self._stage_times: dict[str, float] = {}
        self._hud = None
        self._normalizer = None
        self._tui_active = False

    def set_hud(self, hud):
        self._hud = hud

    def set_normalizer(self, normalizer):
        self._normalizer = normalizer

    def set_tui_active(self, active: bool) -> None:
        """Mark TUI mode as active/inactive. Suppresses all console output."""
        self._tui_active = active
        if active:
            self.console = _null_console
        else:
            self.console = console

    def is_hud_active(self) -> bool:
        return self._hud is not None or self._tui_active

    def hud_log(self, level, message):
        if self._hud:
            self._hud.log(level, message)

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
            "documentation": "[magenta]DOCUMENTATION[/magenta] — Init → impl.code → post (no design/verify/deploy)",
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
        if work_type == "documentation":
            bypassed.append("Design/Arch/Verify/Deploy")
        elif work_type == "operational":
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

        f"[bold]{len(active_nodes)}[/bold]{f' / {total_available}' if total_available else ''} active"
        subtitle = f"[dim]{work_item}[/dim]"
        self.console.print(Panel(tree, title="Graph Topology", subtitle=subtitle, border_style="blue"))
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
        *,
        task_outcome: str | None = None,
        artifact_evidence: dict[str, Any] | None = None,
        work_item: Any = None,
        active_nodes: list[str] | None = None,
        topology_fidelity: dict[str, Any] | None = None,
    ) -> None:
        """Render final loop result as an evidence-based summary panel."""
        outcome = task_outcome or status
        status_style = {
            "done": "[bold green]DONE[/]",
            "failed": "[bold red]FAILED[/]",
            "partial": "[bold red]PARTIAL[/]",
            "done_with_warnings": "[bold yellow]DONE (with warnings)[/]",
            "blocked": "[bold red]BLOCKED[/]",
            "halted": "[bold yellow]HALTED[/]",
        }.get(outcome, f"[white]{outcome}[/]")

        # Count only active stages, not all 26
        if active_nodes:
            active_set = set(active_nodes)
            active_done = sum(1 for s in active_set if stages.get(s, {}).get("done"))
            active_total = len(active_set)
        else:
            active_done = sum(1 for s in stages.values() if s.get("done") and s.get("attempts", 0) > 0)
            active_total = sum(1 for s in stages.values() if s.get("attempts", 0) > 0 or s.get("done"))
            if active_total == 0:
                active_done = sum(1 for s in stages.values() if s.get("done"))
                active_total = len(stages)

        lines = [
            f"[bold]Status:[/bold] {status_style}",
            f"[bold]Iterations:[/bold] {iterations}",
            (
                f"[bold]Active Stages:[/bold] "
                f"[green]{active_done}[/green]"
                f"/{active_total} complete"
            ),
            f"[bold]Total Time:[/bold] [cyan]{tracker.get_loop_elapsed_formatted()}[/cyan]",
        ]

        # Artifact evidence section
        if artifact_evidence:
            lines.append("")
            lines.append("[bold]Artifact Delivery:[/bold]")
            for artifact_path, evidence in artifact_evidence.items():
                exists = evidence.get("exists", False)
                icon = "[green]\u2713[/]" if exists else "[red]\u2717[/]"
                lines.append(f"  {icon} {artifact_path}")

        # Acceptance criteria check
        if isinstance(work_item, dict):
            ac = work_item.get("acceptance_criteria", [])
            if ac:
                lines.append("")
                lines.append(f"[bold]Acceptance Criteria:[/bold] {len(ac)} defined")

        # Post stage failure details
        post_stage = stages.get("post", {})
        if post_stage.get("done") and "failed" in str(post_stage.get("output", "")).lower():
            lines.append("")
            lines.append("[bold red]Post Stage Failed:[/bold red]")
            output_str = str(post_stage.get("output", ""))
            if "summary" in output_str:
                import json as _json
                try:
                    parsed = _json.loads(output_str)
                    summary = parsed.get("summary", output_str[:200])
                except Exception:
                    summary = output_str[:200]
            else:
                summary = output_str[:200]
            lines.append(f"  {summary}")

        # Show troubled stages for any non-clean outcome
        if outcome not in ("done",):
            troubled = [
                sid
                for sid, s in stages.items()
                if s.get("attempts", 0) > 0 and (not s.get("done") or s.get("attempts", 0) >= 2)
            ]
            if troubled:
                lines.append("")
                lines.append("[bold red]Troubled Stages:[/bold red]")
                for sid in troubled:
                    s = stages[sid]
                    done_str = "[green]done[/]" if s.get("done") else "[red]not done[/]"
                    lines.append(f"  \u2022 [bold]{sid}[/bold]: {s.get('attempts', 0)} attempts, {done_str}")

        if blocking_condition:
            lines.append(f"[bold red]Blocking:[/bold red] {blocking_condition}")

        # Topology fidelity warning
        if topology_fidelity and topology_fidelity.get("integrity") == "warning":
            lines.append("")
            lines.append("[bold yellow]Topology Fidelity Warning:[/bold yellow]")
            dropped = topology_fidelity.get("dropped", [])
            added = topology_fidelity.get("added", [])
            if dropped:
                lines.append(f"  Stages dropped during compilation: {', '.join(dropped)}")
            if added:
                lines.append(f"  Stages added during compilation: {', '.join(added)}")

        if decisions:
            lines.append(f"[bold]Decisions:[/bold] {len(decisions)}")
            for d in decisions:
                lines.append(f"  \u2022 {d}")

        panel_title = {
            "done": "[bold]Engineering Loop Complete[/bold]",
            "failed": "[bold red]Engineering Loop FAILED[/bold red]",
            "partial": "[bold red]Engineering Loop PARTIAL[/bold red]",
            "done_with_warnings": "[bold yellow]Engineering Loop Complete (Warnings)[/bold yellow]",
            "blocked": "[bold red]Engineering Loop BLOCKED[/bold red]",
            "halted": "[bold yellow]Engineering Loop HALTED[/bold yellow]",
        }.get(outcome, "[bold]Engineering Loop Complete[/bold]")

        panel_style = {
            "done": "green",
            "failed": "red",
            "partial": "red",
            "done_with_warnings": "yellow",
            "blocked": "red",
            "halted": "yellow",
        }.get(outcome, "blue")

        self.console.print(Rule(panel_title, style=panel_style))
        self.console.print(Panel("\n".join(lines), border_style=panel_style))

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

            self.console.print(Panel(table, title="[bold]Stage Timing[/bold]", border_style="blue"))

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
            self._live.update(self._build_dashboard(stage, iteration, attempts, action, elapsed))

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
        # Push tool action to HUD for casting bar visibility
        if ui.is_hud_active() and ui._normalizer:
            ui._normalizer.agent_action(
                self.stage_id,
                action_type,
                f"{action_type}{target_str}".strip(),
            )

    def think(self, text: str) -> None:
        elapsed = time.monotonic() - self.start_time
        truncated = text[:60]
        if len(text) > 60:
            truncated += "…"
        if self._status:
            self._status.update(
                f"[bold cyan]{self.stage_id}[/bold cyan] [dim]🧠 {truncated}[/dim] [dim]({elapsed:.0f}s)[/dim]"
            )
        # Push thinking text to HUD for real-time visibility
        if ui.is_hud_active() and ui._normalizer:
            ui._normalizer.token_streamed(self.stage_id, text, is_thought=True)

    def idle(self) -> None:
        elapsed = time.monotonic() - self.start_time
        if self._status:
            self._status.update(f"[bold cyan]{self.stage_id}[/bold cyan] [dim]waiting… ({elapsed:.0f}s)[/dim]")


# ─── Thread-local stage context ──────────────────────────────────────
# Allows trace_node to activate a spinner that run_agent() picks up
# automatically without modifying node caller signatures.
import threading

from typing_extensions import Self

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

    def __enter__(self) -> Self:
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


def store_stage_prompt(stage_id: str, prompt: str) -> None:
    """Store the input prompt for a stage (for Node Inspector X-Ray)."""
    if ui._normalizer:
        ui._normalizer.store_input_prompt(stage_id, prompt)


def log_stage_enter(stage_id: str, iteration: int = 0) -> None:
    if ui.is_hud_active():
        ui._hud.set_current_stage(stage_id)
        ui.hud_log("INFO", f"[iter {iteration}] >> {stage_id}")
        if ui._normalizer:
            ui._normalizer.node_entered(stage_id)
            ui._hud.update()
        elif hasattr(ui._hud, "normalizer") and ui._hud.normalizer:
            ui._hud.normalizer.node_entered(stage_id)
            ui._hud.update()
    else:
        ui.console.print(f"[dim][iter {iteration}][/dim] [bold cyan]>> {stage_id}[/bold cyan]")


def log_model_invoke(stage_id: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("DEBUG", f"model -> {stage_id}...")
    else:
        ui.console.print(f"[dim]  [/dim][yellow]model →[/] {stage_id} [dim]...[/dim]")


def log_model_done(stage_id: str, elapsed: float) -> None:
    if ui.is_hud_active():
        ui.hud_log("DEBUG", f"model <- {stage_id} ({format_time(elapsed)})")
    else:
        ui.console.print(f"[dim]  [/dim][green]model ←[/] {stage_id} [dim]({format_time(elapsed)})[/dim]")


def log_stage_done(stage_id: str, result: str = "") -> None:
    if ui.is_hud_active():
        ui.hud_log("INFO", f"done {stage_id}")
    else:
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
    output_data: dict | None = None,
) -> None:
    if ui.is_hud_active():
        ui.hud_log("INFO", f"done {stage_id} ({tool_calls} tools, {duration:.0f}s)")
        ui._hud.clear_current_stage()
        normalizer = ui._normalizer
        if not normalizer and ui._hud:
            normalizer = getattr(ui._hud, "normalizer", None)
        if normalizer:
            from eng_loop.tools.execution_state import NodeStatus

            normalizer.node_completed(stage_id, NodeStatus.COMPLETED)
            if summary:
                normalizer.store_output_result(stage_id, summary[:8000], output_data)
            ui._hud.update()
    else:
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
    if ui.is_hud_active():
        ui.hud_log("INFO", f"skip {stage_id} (already done)")
    else:
        ui.console.print(f"[dim]  skip   {stage_id} (already done)[/dim]")


def log_stage_fail(stage_id: str, reason: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("ERROR", f"{stage_id}: {reason}")
        normalizer = ui._normalizer
        if not normalizer and ui._hud:
            normalizer = getattr(ui._hud, "normalizer", None)
        if normalizer:
            from eng_loop.tools.execution_state import NodeStatus

            normalizer.node_completed(stage_id, NodeStatus.FAILED)
            ui._hud.update()
    else:
        ui.console.print(f"[dim]  [/dim][bold red]fail   [/][bold red]{stage_id}[/]: {reason}")


def log_stage_retry(stage_id: str, attempt: int) -> None:
    if ui.is_hud_active():
        ui.hud_log("WARN", f"retry {stage_id} (attempt {attempt})")
    else:
        ui.console.print(f"[dim]  [/dim][yellow]retry  [/][yellow]{stage_id}[/] [dim](attempt {attempt})[/dim]")


def log_artifact(stage_id: str, path: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("DEBUG", f"file {path}")


def log_complexity(complexity: str, ui_project: bool) -> None:
    if ui.is_hud_active():
        ui.hud_log("SYS", f"complexity={complexity} ui_project={ui_project}")
    else:
        complexity_colors = {
            "small": "green",
            "medium": "yellow",
            "large": "red",
            "complex": "bold red",
        }
        color = complexity_colors.get(complexity, "white")
        ui_project_str = "true" if ui_project else "false"
        ui.console.print(
            f"  [bold cyan]complexity=[/bold cyan][{color}]{complexity}[/]  ui_project=[bold]{ui_project_str}[/bold]"
        )


def log_blocked(reason: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("ERROR", f"blocked: {reason}")
    else:
        ui.console.print(f"  [bold red]blocked:[/bold red] {reason}")


def log_decision(text: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("SYS", f"decision: {text}")
    else:
        ui.console.print(f"  [bold magenta]decision:[/bold magenta] {text}")


def log_iteration(iteration: int, current_stage: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("SYS", f"Iteration {iteration}: {current_stage}")
    else:
        ui.console.print()
        ui.console.print(Rule(f"[iter {iteration}] stage={current_stage}", style="cyan", align="left"))


def log_stall_warning(stage_id: str, report_msg: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("STALL", f"{stage_id}: {report_msg}")
    else:
        ui.console.print(f"  [yellow]stall  {stage_id}: {report_msg}[/yellow]")


def trace_node(stage_id: str):
    """Decorator that logs stage entry, activates spinner, times execution, and renders handoff panel."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(state: dict[str, Any], *args, **kwargs):
            iteration = state.get("iteration", 0)
            log_stage_enter(stage_id, iteration)
            t0 = time.monotonic()
            try:
                if ui.is_hud_active():
                    result = fn(state, *args, **kwargs)
                    tool_count = 0
                else:
                    with stage_context(stage_id) as ctx:
                        result = fn(state, *args, **kwargs)
                        tool_count = ctx.spinner.tool_count
                elapsed = time.monotonic() - t0
                tracker.record_stage(stage_id, elapsed)
                log_stage_complete(
                    stage_id,
                    duration=elapsed,
                    tool_calls=tool_count,
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
    "StageSpinner",
    "UIManager",
    "_get_active_spinner",
    "console",
    "format_time",
    "log_artifact",
    "log_blocked",
    "log_complexity",
    "log_decision",
    "log_iteration",
    "log_model_done",
    "log_model_invoke",
    "log_stage_complete",
    "log_stage_done",
    "log_stage_enter",
    "log_stage_fail",
    "log_stage_retry",
    "log_stage_skip",
    "log_stall_warning",
    "stage_context",
    "store_stage_prompt",
    "trace_node",
    "tracker",
    "ui",
]

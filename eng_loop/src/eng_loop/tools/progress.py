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

from eng_loop.tools.timing import TimingTracker, format_time, token_tracker

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


# ─── Shared progress bar builder ─────────────────────────────────────
# Unified algorithm for all progress bars. Guarantees delimiters [█░] are
# always present and percentage is accurate.
def _stage_display_id(stage_id: str) -> str:
    """Format stage ID for display.

    Standard: lowercase with dot separator (e.g., 'init.ideate').
    Uppercase is reserved for panel titles only.
    """
    return stage_id.replace("-", ".").lower()


def _stage_title_id(stage_id: str) -> str:
    """Format stage ID for panel titles.

    Standard: uppercase with dot separator (e.g., 'INIT.IDEATE').
    """
    return stage_id.replace("-", ".").upper()


def _build_progress_bar(done: int, total: int, width: int = 20) -> tuple[str, str]:
    """Build a progress bar string and progress text.

    Returns (bar_str, progress_text). Always includes [ ] delimiters.
    When done > total (dynamic nodes), shows count instead of percentage.
    """
    if done > total:
        bar = "\u2588" * width
        return f"[{bar}]", f"{done} stages"

    pct = int(100 * done / max(total, 1))
    filled = int(width * done / max(total, 1))
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    return f"[{bar}]", f"{done}/{total} ({pct}%)"


# ─── Live Stage Indicator ────────────────────────────────────────────
# In-place updating line that persists during execution. Shows current
# stage, elapsed time, done count, and a compact topology mini-map.
# Updates via \r so it occupies a single terminal line.


class LiveStageIndicator:
    """In-place progress indicator that updates between stage transitions.

    Unlike the StageSpinner (which runs during agent execution), this
    indicator provides a persistent view of overall progress that survives
    across stages. Uses \r for in-place updates.
    """

    def __init__(self, stage_ids: list[str]) -> None:
        self.stage_ids = [s.replace("-", ".") for s in stage_ids]
        self.done_stages: set[str] = set()
        self.current_stage: str = ""
        self._started = time.monotonic()
        self._rendered = False

    def _mini_map(self) -> str:
        """Build compact topology status: 'init(init,init-ideate,init-refine,impl-code,post)'."""
        parts = []
        for sid in self.stage_ids:
            short = sid.split(".")[-1] if "." in sid else sid
            if sid in self.done_stages:
                parts.append(f"[32m\u2713{short}[0m]")
            elif sid == self.current_stage:
                parts.append(f"[1;36m>{short}[0m]")
            else:
                parts.append(f"[37;2m {short} [0m]")
        return "".join(parts)

    def render(self, finalize: bool = False) -> None:
        """Update the indicator line in-place.

        When done > total (dynamic nodes), shows count instead of
        percentage to avoid displaying 120%.
        """
        if not self.stage_ids:
            return
        # Refresh done count from tracker for accuracy
        self.done_stages = set(tracker.get_stage_ids())
        total = len(self.stage_ids)
        done = len(self.done_stages)
        elapsed = tracker.get_loop_elapsed_formatted()

        current_display = self.current_stage.replace(".", "-") if self.current_stage else "..."
        bar_str, progress = _build_progress_bar(done, total, 20)

        line = f"\r{bar_str} {progress} [bold yellow]{current_display}[/] [dim][{elapsed}][/]"

        if finalize:
            ui.console.print(line)
        else:
            ui.console.print(line, end="\r")
        self._rendered = True

    def clear(self) -> None:
        """Clear the indicator line."""
        if self._rendered:
            try:
                sys.stdout.write("\r" + " " * 120 + "\r")
                sys.stdout.flush()
            except (OSError, ValueError):
                pass


_live_indicator: LiveStageIndicator | None = None
_live_done_count: int = 0


def init_live_indicator(stage_ids: list[str]) -> None:
    """Initialize the live stage indicator with the list of active stages."""
    global _live_indicator, _live_done_count
    _live_done_count = 0
    _live_indicator = LiveStageIndicator(stage_ids)


def update_live_indicator(current_stage: str, done_stages: set[str] | None = None) -> None:
    """Update the live indicator with current stage and done set."""
    if _live_indicator:
        _live_indicator.current_stage = current_stage.replace("-", ".")
        _live_indicator.render()


def finalize_live_indicator() -> None:
    """Finalize the live indicator with a newline."""
    if _live_indicator:
        _live_indicator.render(finalize=True)


def clear_live_indicator() -> None:
    """Clear the live indicator line."""
    if _live_indicator:
        _live_indicator.clear()


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
        self._event_bus = None
        self._renderer_mode = "console"  # "console" | "legacy"

    def set_event_bus(self, event_bus) -> None:
        """Set the event bus for CLI v2 event emission."""
        self._event_bus = event_bus

    def set_renderer_mode(self, mode: str) -> None:
        """Set the renderer mode: 'console' (new) or 'legacy'."""
        self._renderer_mode = mode

    def is_legacy_mode(self) -> bool:
        """Check if legacy renderer is active."""
        return self._renderer_mode == "legacy"

    def _emit_event(self, event) -> None:
        """Emit an event through the event bus if available."""
        if self._event_bus:
            self._event_bus.emit(event)

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

        Strategy label is derived from actual active nodes so the visual
        representation matches the conceptual promise.
        """
        # Determine which lifecycle phases are actually present
        active_prefixes = set()
        for node in active_nodes:
            prefix = node.split(".")[0].upper()
            active_prefixes.add(prefix)

        # Build strategy description from actual phases, not work_type assumption
        lifecycle_phases = ["INIT", "DESIGN", "ARCH", "IMPL", "VERIFY", "QA", "DEPLOY", "DOC", "POST"]
        present_phases = [p for p in lifecycle_phases if p in active_prefixes]

        # Map phase presence to human-readable lifecycle
        has_design = "DESIGN" in active_prefixes or "ARCH" in active_prefixes
        has_impl = "IMPL" in active_prefixes
        has_verify = "VERIFY" in active_prefixes or "QA" in active_prefixes
        has_deploy = "DEPLOY" in active_prefixes

        if has_design and has_impl and has_verify and has_deploy:
            lifecycle_desc = "design → impl → verify → QA → deploy"
        elif has_design and has_impl and has_verify:
            lifecycle_desc = "design → impl → verify"
        elif has_design and has_impl:
            lifecycle_desc = "design → impl"
        elif has_impl and has_verify:
            lifecycle_desc = "impl → verify"
        elif has_impl:
            lifecycle_desc = "impl"
        else:
            lifecycle_desc = "init only"

        # Add init/post bookends
        if "INIT" in active_prefixes:
            lifecycle_desc = f"init → {lifecycle_desc}"
        if "POST" in active_prefixes:
            lifecycle_desc = f"{lifecycle_desc} → post"

        work_type_colors = {
            "feature": "green",
            "bugfix": "yellow",
            "operational": "cyan",
            "documentation": "magenta",
        }
        type_color = work_type_colors.get(work_type, "white")
        strategy_line = f"[{type_color}]{work_type.upper()}[/] — {lifecycle_desc}"

        complexity_colors = {
            "small": "green",
            "medium": "yellow",
            "large": "red",
            "complex": "bold red",
        }
        comp_color = complexity_colors.get(complexity, "white")

        # Compute bypassed phases from what's missing
        all_lifecycle = {"DESIGN", "ARCH", "VERIFY", "QA", "DEPLOY"}
        missing = all_lifecycle - active_prefixes
        bypass_labels = []
        if missing & {"DESIGN", "ARCH"}:
            bypass_labels.append("Design/Arch")
        if missing & {"VERIFY", "QA"}:
            bypass_labels.append("Verify/QA")
        if "DEPLOY" in missing:
            bypass_labels.append("Deploy")
        if "IMPL" not in active_prefixes:
            bypass_labels.append("Impl")
        if not ui_project:
            bypass_labels.append("E2E/Smoke")

        bypass_line = ""
        if bypass_labels:
            bypass_line = f" [dim](bypassing {', '.join(bypass_labels)})[/dim]"

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
        """Render a compact progress bar with stage status.

        Uses the shared _build_progress_bar algorithm for consistency.
        """
        total = len(active_stages)
        done = len(done_stages)

        status_icon = {
            "running": "[green]▶[/]",
            "done": "[bold green]✓[/]",
            "blocked": "[bold red]✗[/]",
            "halted": "[bold red]⏸[/]",
        }.get(status, "[yellow]?[/]")

        elapsed_str = tracker.get_loop_elapsed_formatted()
        bar_str, progress = _build_progress_bar(done, total, 30)

        self.console.print(
            f"{status_icon} [dim]{bar_str}[/dim] "
            f"[cyan]{progress}[/cyan] "
            f"[bold yellow]{current_stage}[/bold yellow] "
            f"[dim][{elapsed_str}][/dim]"
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

    # ── Unified Status Icon ────────────────────────────────────────
    @staticmethod
    def get_stage_icon(stage_data: dict[str, Any]) -> str:
        """Determine the visual icon for a stage based on its state.

        Invariant: done=True always yields a positive icon (green check).
        This prevents the contradiction where a completed stage shows
        a blocked/error icon in the summary tree.
        """
        is_done = stage_data.get("done", False)
        is_cached = stage_data.get("cached", False)
        attempts = stage_data.get("attempts", 0)

        if is_done:
            return "[green]\u2713[/green]"
        if is_cached:
            return "[cyan]\u21bb[/cyan]"
        if attempts > 0:
            return "[red]\u2717[/red]"
        return "[dim]\u26d4[/dim]"

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
        """Render final loop result with three-layer visual hierarchy.

        Layer 1: Work item and outcome (what was requested, did it succeed?)
        Layer 2: Pipeline graph (where each stage stands)
        Layer 3: Execution details (timing, metrics, contract violations)
        """
        outcome = task_outcome or status
        panel_style = {
            "done": "green",
            "failed": "red",
            "partial": "red",
            "done_with_warnings": "yellow",
            "blocked": "red",
            "halted": "yellow",
        }.get(outcome, "blue")

        # ── Layer 1: Work Item + Outcome ──────────────────────────
        outcome_icons = {
            "done": "[bold green]\u2713 COMPLETED[/bold green]",
            "failed": "[bold red]\u2717 FAILED[/bold red]",
            "partial": "[bold red]\u2717 PARTIAL[/bold red]",
            "done_with_warnings": "[bold yellow]\u2713 COMPLETED (warnings)[/bold yellow]",
            "blocked": "[bold red]\u26a0 BLOCKED[/bold red]",
            "halted": "[bold yellow]\u23f8 HALTED[/bold yellow]",
        }
        outcome_display = outcome_icons.get(outcome, f"[white]{outcome}[/]")

        # Extract work item description
        if isinstance(work_item, dict):
            work_desc = work_item.get("description", work_item.get("prompt", str(work_item)))
        elif isinstance(work_item, str):
            work_desc = work_item
        else:
            work_desc = ""

        # Build reason for failure/block
        failure_reason = ""
        if blocking_condition:
            failure_reason = f"\n[dim]Reason:[/dim] {blocking_condition}"
        elif outcome in ("failed", "blocked", "partial"):
            # Find the first failed stage for context
            for node_id in active_nodes or []:
                stage_data = stages.get(node_id, {})
                if not stage_data.get("done") and stage_data.get("attempts", 0) > 0:
                    failure_reason = f"\n[dim]Stopped at:[/dim] [bold]{node_id}[/bold]"
                    break

        layer1_lines = [outcome_display]
        if work_desc:
            layer1_lines.insert(0, f"[bold]Work Item:[/bold] {work_desc}")
        if failure_reason:
            layer1_lines.append(failure_reason)

        # ── Layer 2: Pipeline Graph ───────────────────────────────
        # Group nodes by phase, show status for each
        phase_order = ["INIT", "DESIGN", "ARCH", "IMPL", "VERIFY", "QA", "DEPLOY", "DOC", "POST"]
        phase_colors = {
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

        phase_nodes = {p: [] for p in phase_order}
        if active_nodes:
            for node in active_nodes:
                prefix = node.split(".")[0].upper()
                if prefix in phase_nodes:
                    phase_nodes[prefix].append(node)

        # Build visual graph: Phase boxes with status indicators
        graph_rows = []
        for phase in phase_order:
            nodes = phase_nodes.get(phase, [])
            if not nodes:
                continue

            color = phase_colors.get(phase, "white")
            node_statuses = []
            for node in nodes:
                short = node.split(".")[-1] if "." in node else node
                stage_data = stages.get(node, {})
                icon = self.get_stage_icon(stage_data)
                node_statuses.append(f"{icon} {short}")

            nodes_str = "\n  ".join(node_statuses)
            graph_rows.append(f"[bold {color}]{phase}[/bold {color}]\n  {nodes_str}")

        graph_display = "\n\n".join(graph_rows) if graph_rows else "[dim]No stages executed[/dim]"

        # ── Layer 3: Execution Details ────────────────────────────
        detail_lines = []

        # Artifact evidence
        if artifact_evidence:
            detail_lines.append("[bold]Artifact Delivery:[/bold]")
            for artifact_path, evidence in artifact_evidence.items():
                exists = evidence.get("exists", False)
                icon = "[green]\u2713[/]" if exists else "[red]\u2717[/]"
                detail_lines.append(f"  {icon} {artifact_path}")

        # Contract violations and troubled stages
        troubled = [
            sid
            for sid, s in stages.items()
            if s.get("attempts", 0) > 0 and (not s.get("done") or s.get("attempts", 0) >= 2)
        ]
        if troubled:
            detail_lines.append("")
            detail_lines.append("[bold red]\u26a0 Troubled Stages:[/bold red]")
            for sid in troubled:
                s = stages[sid]
                done_str = "[green]done[/]" if s.get("done") else "[red]not done[/]"
                detail_lines.append(f"  \u2022 [bold]{sid}[/bold]: {s.get('attempts', 0)} attempts, {done_str}")

        # Post stage failure
        post_stage = stages.get("post", {})
        if post_stage.get("done") and "failed" in str(post_stage.get("output", "")).lower():
            detail_lines.append("")
            detail_lines.append("[bold red]Post Stage Failed:[/bold red]")
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
            detail_lines.append(f"  {summary}")

        # Topology fidelity
        if topology_fidelity and topology_fidelity.get("integrity") == "warning":
            detail_lines.append("")
            detail_lines.append("[bold yellow]Topology Fidelity Warning:[/bold yellow]")
            dropped = topology_fidelity.get("dropped", [])
            added = topology_fidelity.get("added", [])
            if dropped:
                detail_lines.append(f"  Stages dropped: {', '.join(dropped)}")
            if added:
                detail_lines.append(f"  Stages added: {', '.join(added)}")

        # Decisions
        if decisions:
            detail_lines.append(f"[bold]Decisions:[/bold] {len(decisions)}")
            for d in decisions:
                detail_lines.append(f"  \u2022 {d}")

        # Acceptance criteria
        if isinstance(work_item, dict):
            ac = work_item.get("acceptance_criteria", [])
            if ac:
                detail_lines.append(f"[bold]Acceptance Criteria:[/bold] {len(ac)} defined")

        # Telemetry summary
        elapsed = tracker.get_loop_elapsed_formatted()
        telemetry = f"[dim]{elapsed} \u2022 {iterations} iterations[/dim]"

        # ── Render Layers ─────────────────────────────────────────
        rule_title = {
            "done": "[bold]Engineering Loop Complete[/bold]",
            "failed": "[bold red]Engineering Loop FAILED[/bold red]",
            "partial": "[bold red]Engineering Loop PARTIAL[/bold red]",
            "done_with_warnings": "[bold yellow]Engineering Loop Complete (Warnings)[/bold yellow]",
            "blocked": "[bold red]Engineering Loop BLOCKED[/bold red]",
            "halted": "[bold yellow]Engineering Loop HALTED[/bold yellow]",
        }.get(outcome, "[bold]Engineering Loop Complete[/bold]")

        self.console.print(Rule(rule_title, style=panel_style))

        # Layer 1: Work item outcome
        self.console.print(
            Panel(
                "\n".join(layer1_lines),
                title="[bold]Result[/bold]",
                border_style=panel_style,
            )
        )

        # Layer 2: Pipeline graph
        self.console.print(
            Panel(
                graph_display,
                title="[bold]Pipeline[/bold]",
                border_style="blue",
            )
        )

        # Layer 3: Execution details (only if there's content)
        if detail_lines:
            self.console.print(
                Panel(
                    "\n".join(detail_lines) + f"\n\n{telemetry}",
                    title="[bold]Details[/bold]",
                    border_style="blue",
                )
            )
        else:
            self.console.print(f"  {telemetry}")

        # Timing table
        timing_rows = tracker.get_summary()
        if timing_rows:
            table = Table(box=None, padding=(0, 1), show_header=True)
            table.add_column("Stage", style="bold cyan", no_wrap=True)
            table.add_column("Total", style="cyan", justify="right")
            table.add_column("Attempts", justify="center")
            table.add_column("Tokens", style="yellow", justify="right")
            table.add_column("Per Attempt", style="dim", justify="right")

            for row in timing_rows:
                durations = row.get("durations", [])
                per_attempt = ", ".join(format_time(d) for d in durations) if durations else ""
                stage_id = row["stage_id"]
                tok = token_tracker.get_stage_total(stage_id)
                tok_str = token_tracker._format_tokens(tok) if tok else ""
                table.add_row(
                    stage_id,
                    row["total"],
                    str(row["attempts"]),
                    tok_str,
                    per_attempt,
                )

            # Total row
            total_str = format_time(tracker.get_total_seconds())
            loop_elapsed = tracker.get_loop_elapsed_formatted()
            total_tok = token_tracker.get_total_all()
            total_tok_str = token_tracker._format_tokens(total_tok) if total_tok else ""
            table.add_row(
                "[bold]Total[/bold]",
                f"[bold cyan]{total_str}[/bold cyan] [dim](wall: {loop_elapsed})[/dim]",
                "",
                f"[bold yellow]{total_tok_str}[/bold yellow]" if total_tok_str else "",
                "",
            )

            self.console.print(Panel(table, title="[bold]Stage Timing[/bold]", border_style="blue"))

            # Token summary
            total_all = token_tracker.get_total_all()
            if total_all:
                tok_table = Table(show_header=False, box=None, padding=(0, 1))
                tok_table.add_column("Metric", style="bold dim", width=16)
                tok_table.add_column("Value", style="white")
                tok_table.add_row(
                    "Input",
                    f"[yellow]{token_tracker._format_tokens(token_tracker.get_total_input())}[/yellow]",
                )
                tok_table.add_row(
                    "Output",
                    f"[yellow]{token_tracker._format_tokens(token_tracker.get_total_output())}[/yellow]",
                )
                tok_table.add_row(
                    "Cached",
                    f"[green]{token_tracker._format_tokens(token_tracker.get_total_cached())}[/green]",
                )
                tok_table.add_row(
                    "[bold]Total[/bold]",
                    f"[bold yellow]{token_tracker._format_tokens(total_all)}[/bold yellow]",
                )
                self.console.print(Panel(tok_table, title="[bold]Token Usage[/bold]", border_style="yellow"))

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
    Also carries iteration/summary from inner run_agent calls so trace_node
    can render a single enriched panel instead of duplicating output.
    Tracks skip state so trace_node can render the correct panel.
    """

    def __init__(self, stage_id: str) -> None:
        self.stage_id = stage_id
        self.spinner = StageSpinner(stage_id)
        self.iterations: int = 0
        self.summary: str = ""
        self.skipped: bool = False

    def __enter__(self) -> Self:
        self.spinner.start()
        self.skipped = False
        _stage_ctx.active = True  # type: ignore[attr-defined]
        _stage_ctx.spinner = self.spinner  # type: ignore[attr-defined]
        _set_active_stage_ctx(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.spinner.stop()
        _stage_ctx.active = False  # type: ignore[attr-defined]
        _stage_ctx.spinner = None  # type: ignore[attr-defined]
        _set_active_stage_ctx(None)
        return False


def _get_active_spinner() -> StageSpinner | None:
    """Get the active spinner for the current thread, if any."""
    if getattr(_stage_ctx, "active", False):
        return _stage_ctx.spinner  # type: ignore[attr-defined]
    return None


def _get_active_stage_ctx() -> stage_context | None:
    """Get the active stage context for the current thread, if any.

    Used by run_agent to store iteration/summary so trace_node can render
    a single enriched panel.
    """
    if getattr(_stage_ctx, "active", False):
        return getattr(_stage_ctx, "_ctx", None)  # type: ignore[attr-defined]
    return None


def _set_active_stage_ctx(ctx: stage_context | None) -> None:
    """Set the active stage context reference."""
    _stage_ctx._ctx = ctx  # type: ignore[attr-defined]


# ─── Panel deduplication state ───────────────────────────────────────
# Tracks the last rendered panel per stage to prevent duplicate output
# when stages retry. Collapses repeated executions into attempt count.
_rendered_panels: dict[str, int] = {}  # stage_id -> last attempt count


def _clear_line_above() -> None:
    """Clear the line above the cursor (for in-place panel update)."""
    try:
        sys.stdout.write("\033[F\033[K")
        sys.stdout.flush()
    except (OSError, ValueError):
        pass


def _reset_rendered_panels() -> None:
    """Clear deduplication state between pipeline runs."""
    _rendered_panels.clear()


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
    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import node_started

        ui._event_bus.emit(
            node_started(
                graph_id="",
                node_id=stage_id,
                attempt=iteration + 1,
            )
        )

    if ui.is_hud_active():
        ui._hud.set_current_stage(stage_id)
        ui.hud_log("INFO", f"[iter {iteration}] >> {stage_id}")
        if ui._normalizer:
            ui._normalizer.node_entered(stage_id)
            ui._hud.update()
        elif hasattr(ui._hud, "normalizer") and ui._hud.normalizer:
            ui._hud.normalizer.node_entered(stage_id)
            ui._hud.update()
    elif ui._event_bus is None or ui.is_legacy_mode():
        # No event bus (original mode) or legacy renderer: print entry
        if _live_indicator:
            _live_indicator.current_stage = stage_id.replace("-", ".")
            _live_indicator.render()
        if iteration == 0 and not _iter_count:
            ui.console.print(f"[bold cyan]>> {stage_id}[/bold cyan]")
    # New console mode with event bus: silent entry (spinner handles visual feedback)


def log_model_invoke(stage_id: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("DEBUG", f"model -> {stage_id}...")
    elif not _get_active_spinner():
        # Silent when spinner is active — it provides the visual feedback
        ui.console.print(f"[dim]  [/dim][yellow]model →[/] {stage_id} [dim]...[/dim]")


def log_model_done(stage_id: str, elapsed: float) -> None:
    if ui.is_hud_active():
        ui.hud_log("DEBUG", f"model <- {stage_id} ({format_time(elapsed)})")
    elif not _get_active_spinner():
        # Silent when spinner is active — the completion panel follows
        ui.console.print(f"[dim]  [/dim][green]model ←[/] {stage_id} [dim]({format_time(elapsed)})[/dim]")


def log_stage_done(stage_id: str, result: str = "") -> None:
    if ui.is_hud_active():
        ui.hud_log("INFO", f"done {stage_id}")
    elif _get_active_spinner():
        # trace_node decorator will render the completion panel — skip duplicate
        pass
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
    global _live_done_count
    _live_done_count += 1

    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import node_completed

        ui._event_bus.emit(
            node_completed(
                graph_id="",
                node_id=stage_id,
                duration_ms=int(duration * 1000),
                tool_count=tool_calls,
            )
        )

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
    elif ui._event_bus is None or ui.is_legacy_mode():
        finalize_iteration_line()
        finalize_live_indicator()
        # Deduplication: collapse retries into attempt count
        attempts = tracker.get_stage_attempts(stage_id)
        prev = _rendered_panels.get(stage_id)
        if prev is not None and prev == attempts:
            # Exact duplicate — skip entirely
            return
        _rendered_panels[stage_id] = attempts

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="bold dim", width=10)
        table.add_column("Value", style="white")
        table.add_row("Duration", f"[cyan]{format_time(duration)}[/cyan]")
        table.add_row("Tools", f"[cyan]{tool_calls}[/cyan] calls")
        if iterations:
            table.add_row("Iterations", f"[cyan]{iterations}[/cyan]")
        if attempts > 1:
            table.add_row("Attempts", f"[yellow]{attempts}[/yellow]")
        if summary:
            truncated = summary[:100]
            if len(summary) > 100:
                truncated += "\u2026"
            table.add_row("Result", f"[green]{truncated}[/green]")

        title = f"[bold green]\u2713 {stage_id.upper()}[/bold green]"
        if attempts > 1:
            title += f" [dim]({attempts}x)[/dim]"
        ui.console.print(Panel(table, title=title, border_style="green"))
    else:
        # Console mode with event bus: render compact completion panel
        finalize_iteration_line()
        finalize_live_indicator()
        attempts = tracker.get_stage_attempts(stage_id)
        prev = _rendered_panels.get(stage_id)
        if prev is not None and prev == attempts:
            return
        _rendered_panels[stage_id] = attempts

        tok = token_tracker.get_stage_total(stage_id)
        tok_str = f" [yellow]{token_tracker._format_tokens(tok)} tokens[/yellow]" if tok else ""
        iter_str = f", [cyan]{iterations} iter[/cyan]" if iterations else ""
        att_str = f" [yellow]({attempts}x)[/yellow]" if attempts > 1 else ""
        summary_str = ""
        if summary:
            truncated = summary[:100]
            if len(summary) > 100:
                truncated += "\u2026"
            summary_str = f"\n[dim]{truncated}[/dim]"

        ui.console.print(
            Panel(
                f"[dim]Duration[/dim] [cyan]{format_time(duration)}[/cyan]\n"
                f"[dim]Tools[/dim] [cyan]{tool_calls}[/cyan] calls{iter_str}{tok_str}{summary_str}",
                title=f"[bold green]\u2713 {stage_id.upper()}[/bold green]{att_str}",
                border_style="green",
            )
        )


def log_stage_skip(stage_id: str, reason: str = "") -> None:
    """Log a stage that was deliberately not executed.

    Use for stages intentionally bypassed by routing decisions.
    Visual: dim, no execution panel follows.
    Sets thread-local skip flag so trace_node renders a skip panel.
    """
    # Signal trace_node that this stage was skipped
    active_ctx = _get_active_stage_ctx()
    if active_ctx:
        active_ctx.skipped = True

    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import node_skipped

        ui._event_bus.emit(
            node_skipped(
                graph_id="",
                node_id=stage_id,
                reason=reason,
            )
        )

    reason_text = f" — {reason}" if reason else ""
    if ui.is_hud_active():
        ui.hud_log("INFO", f"skip {stage_id}{reason_text}")
    elif ui._event_bus is None or ui.is_legacy_mode():
        finalize_iteration_line()
        finalize_live_indicator()
        ui.console.print(f"[dim]  — skip   {stage_id}{reason_text}[/dim]")
    else:
        # Console mode with event bus: render skip line
        finalize_iteration_line()
        finalize_live_indicator()
        ui.console.print(f"[dim]  — skip   {stage_id}{reason_text}[/dim]")


def log_stage_cached(stage_id: str, source: str = "") -> None:
    """Log a stage whose result was recovered from cache.

    Use for stages already computed in a prior iteration or run.
    Visual: cyan, distinct from skip and completed.
    """
    source_text = f" ({source})" if source else ""
    if ui.is_hud_active():
        ui.hud_log("INFO", f"cached {stage_id}{source_text}")
        normalizer = ui._normalizer
        if not normalizer and ui._hud:
            normalizer = getattr(ui._hud, "normalizer", None)
        if normalizer:
            from eng_loop.tools.execution_state import NodeStatus

            normalizer.node_completed(stage_id, NodeStatus.COMPLETED)
            ui._hud.update()
    else:
        finalize_iteration_line()
        finalize_live_indicator()
        ui.console.print(
            Panel(
                f"[dim]Duration[/dim] [cyan]0s[/cyan]\n[dim]Source[/dim] [cyan]cache{source_text}[/cyan]",
                title=f"[bold cyan]\u21bb {stage_id.upper()}[/bold cyan]",
                border_style="cyan",
            )
        )


def log_stage_fail(stage_id: str, reason: str) -> None:
    # Emit event for CLI v2
    if ui._event_bus:
        from eng_loop.tools.cli_events import node_failed

        ui._event_bus.emit(
            node_failed(
                graph_id="",
                node_id=stage_id,
                error=reason,
            )
        )

    if ui.is_hud_active():
        ui.hud_log("ERROR", f"{stage_id}: {reason}")
        normalizer = ui._normalizer
        if not normalizer and ui._hud:
            normalizer = getattr(ui._hud, "normalizer", None)
        if normalizer:
            from eng_loop.tools.execution_state import NodeStatus

            normalizer.node_completed(stage_id, NodeStatus.FAILED)
            ui._hud.update()
    elif ui._event_bus is None or ui.is_legacy_mode():
        finalize_iteration_line()
        finalize_live_indicator()
        ui.console.print(
            Panel(
                f"[bold red]Execution failed.[/bold red]\n[dim]{reason}[/dim]",
                title=f"[bold red]\u2717 {stage_id.upper()}[/bold red]",
                border_style="red",
            )
        )
    else:
        # Console mode with event bus: render failure panel
        finalize_iteration_line()
        finalize_live_indicator()
        ui.console.print(
            Panel(
                f"[bold red]Execution failed.[/bold red]\n[dim]{reason}[/dim]",
                title=f"[bold red]\u2717 {stage_id.upper()}[/bold red]",
                border_style="red",
            )
        )


def log_stage_retry(stage_id: str, attempt: int) -> None:
    if ui.is_hud_active():
        ui.hud_log("WARN", f"retry {stage_id} (attempt {attempt})")
    else:
        # Silent: the completion panel will show total attempts
        # This prevents duplicate panels for each retry
        pass


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
        finalize_iteration_line()
        ui.console.print(
            Panel(
                f"[bold red]Execution blocked.[/bold red]\n[dim]{reason}[/dim]",
                title="[bold red]\u26a0 BLOCKED[/bold red]",
                border_style="red",
            )
        )


def log_decision(text: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("SYS", f"decision: {text}")
    else:
        ui.console.print(f"  [bold magenta]decision:[/bold magenta] {text}")


# ── Iteration state for in-place updates ──────────────────────────────
_iter_line: str = ""
_iter_count: int = 0
_iter_stage: str = ""


def log_iteration(iteration: int, current_stage: str) -> None:
    """Log iteration count in-place. Max 2 physical lines regardless of iteration count.

    First call prints the separator line. Subsequent calls update the counter
    on the same line using carriage return.
    """
    global _iter_line, _iter_count, _iter_stage

    if ui.is_hud_active():
        ui.hud_log("SYS", f"Iteration {iteration}: {current_stage}")
        return

    if _iter_count == 0:
        # First iteration: print separator + counter
        clear_live_indicator()
        ui.console.print()
        ui.console.print("[dim]━" * 38 + "[/dim]")
        _iter_count = iteration
        _iter_stage = current_stage
        _iter_line = f"  [bold cyan]iter {_iter_count}[/bold cyan]  [bold yellow]{_iter_stage}[/bold yellow]"
        ui.console.print(_iter_line, end="\r")
    elif current_stage != _iter_stage:
        # Stage changed: update in-place
        _iter_count = iteration
        _iter_stage = current_stage
        new_line = f"  [bold cyan]iter {_iter_count}[/bold cyan]  [bold yellow]{_iter_stage}[/bold yellow]"
        ui.console.print("\r" + " " * 120 + "\r")
        ui.console.print(new_line, end="\r")
        _iter_line = new_line
    else:
        # Same stage, just increment counter in-place
        _iter_count = iteration
        new_line = f"  [bold cyan]iter {_iter_count}[/bold cyan]  [bold yellow]{_iter_stage}[/bold yellow]"
        ui.console.print("\r" + new_line + "\r")
        _iter_line = new_line


def finalize_iteration_line() -> None:
    """Finalize the iteration line with a newline."""
    global _iter_line, _iter_count, _iter_stage
    if _iter_count > 0:
        ui.console.print("\r" + _iter_line)
        _iter_line = ""
        _iter_count = 0
        _iter_stage = ""


def log_stall_warning(stage_id: str, report_msg: str) -> None:
    if ui.is_hud_active():
        ui.hud_log("STALL", f"{stage_id}: {report_msg}")
    else:
        ui.console.print(
            Panel(
                f"[yellow]{stage_id}[/yellow]\n[dim]{report_msg}[/dim]",
                title="[bold yellow]\u26a0 Stall Detected[/bold yellow]",
                border_style="yellow",
            )
        )


def trace_node(stage_id: str):
    """Decorator that logs stage entry, activates spinner, times execution, and renders handoff panel.

    If the handler called log_stage_skip, renders a skip panel instead of
    a completed panel so the visual output is consistent.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(state: dict[str, Any], *args, **kwargs):
            iteration = state.get("iteration", 0)
            log_stage_enter(stage_id, iteration)
            t0 = time.monotonic()
            was_skipped = False
            try:
                if ui.is_hud_active():
                    result = fn(state, *args, **kwargs)
                    tool_count = 0
                    inner_iterations = 0
                    inner_summary = ""
                else:
                    with stage_context(stage_id) as ctx:
                        result = fn(state, *args, **kwargs)
                        tool_count = ctx.spinner.tool_count
                        inner_iterations = ctx.iterations
                        inner_summary = ctx.summary
                        was_skipped = ctx.skipped
                elapsed = time.monotonic() - t0
                tracker.record_stage(stage_id, elapsed)
                if was_skipped:
                    log_stage_cached(stage_id, "already done")
                else:
                    log_stage_complete(
                        stage_id,
                        duration=elapsed,
                        tool_calls=tool_count,
                        summary=inner_summary,
                        iterations=inner_iterations,
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
    "_get_active_stage_ctx",
    "clear_live_indicator",
    "console",
    "finalize_iteration_line",
    "finalize_live_indicator",
    "format_time",
    "init_live_indicator",
    "log_artifact",
    "log_blocked",
    "log_complexity",
    "log_decision",
    "log_iteration",
    "log_model_done",
    "log_model_invoke",
    "log_stage_cached",
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
    "update_live_indicator",
]

from __future__ import annotations

import asyncio
import sys
import threading
from typing import TYPE_CHECKING, Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Input,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

if TYPE_CHECKING:
    from eng_loop.tools.execution_state import ExecutionState, HUDSnapshot, NodePayload


PHASE_ORDER = ["init", "design", "arch", "impl", "verify", "qa", "deploy", "doc", "post"]
PHASE_LABELS = {
    "init": "INIT",
    "design": "DESIGN",
    "arch": "ARCH",
    "impl": "IMPL",
    "verify": "VERIFY",
    "qa": "QA",
    "deploy": "DEPLOY",
    "doc": "DOC",
    "post": "POST",
}
PHASE_COLORS = {
    "init": "blue",
    "design": "cyan",
    "arch": "magenta",
    "impl": "green",
    "verify": "yellow",
    "qa": "red",
    "deploy": "bright_blue",
    "doc": "bright_cyan",
    "post": "white",
}

CLASS_ICONS = {
    "MAGE": "G",
    "DESIGNER": "D",
    "ARCHITECT": "A",
    "WARRIOR": "W",
    "CHRONICLER": "C",
    "INSPECTOR": "I",
    "ALCHMIST": "E",
    "GUARD": "S",
    "SCRIBE": "R",
    "SPEEDSTER": "P",
    "PILOT": "Z",
    "HERO": "H",
}


def _get_role(node_name: str) -> str:
    mapping = {
        "init": "MAGE",
        "design": "DESIGNER",
        "arch": "ARCHITECT",
        "impl": "WARRIOR",
        "verify": "INSPECTOR",
        "e2e": "ALCHMIST",
        "qa.security": "GUARD",
        "qa.api-contract": "SCRIBE",
        "qa.performance": "SPEEDSTER",
        "deploy": "PILOT",
        "smoke": "ALCHMIST",
        "doc": "CHRONICLER",
        "post": "HERO",
    }
    for key, role in mapping.items():
        if node_name.startswith(key):
            return role
    return "NPC"


def _get_icon(node_name: str) -> str:
    role = _get_role(node_name)
    return CLASS_ICONS.get(role, "?")


def _get_color(node_name: str) -> str:
    mapping = {
        "init": "blue",
        "design": "cyan",
        "arch": "magenta",
        "impl": "green",
        "verify": "yellow",
        "e2e": "bright_magenta",
        "qa.security": "red",
        "qa.api-contract": "cyan",
        "qa.performance": "bright_yellow",
        "deploy": "bright_blue",
        "smoke": "bright_magenta",
        "doc": "white",
        "post": "white",
    }
    for key, color in mapping.items():
        if node_name.startswith(key):
            return color
    return "white"


def _get_phase(node_name: str) -> str:
    for phase in PHASE_ORDER:
        if node_name.startswith(phase):
            return phase
    return "post"


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins < 60:
        return f"{mins}m {secs}s"
    hours = mins // 60
    remaining_mins = mins % 60
    return f"{hours}h {remaining_mins}m {secs}s"


# ─── Custom Messages ─────────────────────────────────────────────────


class NodeSelected:
    """Emitted when a node is selected in the graph tree."""

    def __init__(self, node_name: str) -> None:
        self.node_name = node_name


class PauseToggled:
    """Emitted when pause/resume is toggled."""

    def __init__(self, is_paused: bool) -> None:
        self.is_paused = is_paused


class StepRequested:
    """Emitted when step-by-step mode is requested."""


class InterventionRequested:
    """Emitted when user requests to intervene."""

    def __init__(self, node_name: str) -> None:
        self.node_name = node_name


class QuitRequested:
    """Emitted when user requests to quit."""


class StdoutCaptured(Message):
    """Emitted when stdout/stderr output is captured by the redirector."""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


# ─── Output Redirector (sequesters stdout/stderr) ────────────────────


class OutputRedirector:
    """Captures stray print() and logging output, routes to HUD RichLog.

    Prevents stdout/stderr leakage that corrupts the Textual alternative
    screen. Thread-safe: uses a queue to bridge background threads with
    the Textual event loop.
    """

    def __init__(self, app: MAGEHUDApp) -> None:
        self._app = app
        self._buffer: list[str] = []
        self._flush_interval = 0.1
        self._timer_token: Any = None

    def install(self) -> None:
        """Replace sys.stdout/stderr with this redirector."""
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self

    def uninstall(self) -> None:
        """Restore original stdout/stderr, flush remaining buffer."""
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self._flush_buffer()

    def write(self, message: str) -> int:
        if message.strip():
            self._buffer.append(message)
            if len(self._buffer) >= 5:
                self._flush_buffer()
        return len(message)

    def flush(self) -> None:
        pass

    def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        text = "".join(self._buffer)
        self._buffer.clear()
        try:
            self._app.call_after_refresh(lambda: self._app.post_message(StdoutCaptured(text)))
        except Exception:
            pass


# ─── Widgets ─────────────────────────────────────────────────────────


class QuestBar(Static):
    """Top bar showing quest title, status, elapsed time."""

    DEFAULT_CSS = """
    QuestBar {
        border: round $accent;
        padding: 0 1;
        height: 3;
        grid-column-end: span 2;
    }
    """

    def __init__(self, snapshot: HUDSnapshot | None = None) -> None:
        super().__init__()
        self._snapshot = snapshot

    def update_snapshot(self, snapshot: HUDSnapshot) -> None:
        self._snapshot = snapshot
        self.refresh()

    def render_str(self) -> str:
        if not self._snapshot:
            return "  MAGE HUD v2.0 — Awaiting quest..."
        s = self._snapshot
        elapsed = _format_duration(s.elapsed_seconds)
        status_colors = {
            "pending": "dim",
            "running": "green",
            "completed": "green",
            "failed": "red",
            "cancelled": "yellow",
        }
        status_color = status_colors.get(s.quest_status, "white")
        pause_indicator = " [bold red blink]PAUSED[/]" if s.is_paused else ""
        step_indicator = " [bold yellow]STEP MODE[/]" if s.step_mode else ""
        return (
            f"[bold gold1]MAIN QUEST:[/bold gold1] [white]{s.quest_title}[/white]"
            f"\n[dim]Status:[/dim] [{status_color}]{s.quest_status.upper()}[/]{pause_indicator}{step_indicator}"
            f"  [dim]Time:[/dim] [cyan]{elapsed}[/cyan]"
            f"  [dim]Gold:[/dim] [yellow]{s.gold_spent:.2f}[/yellow]"
        )


class NavigableGraph(Static):
    """Navigable graph map — replaces text-based graph with selectable nodes.

    Organized by phase. User can navigate with up/down, select with enter.
    """

    DEFAULT_CSS = """
    NavigableGraph {
        border: round $boost;
        padding: 0 1;
        width: 45%;
        height: 100%;
    }
    NavigableGraph .title-bar {
        dock: top;
        background: $boost;
        color: $text;
        height: 1;
        width: 100%;
        content-align: center middle;
    }
    """

    BINDINGS = [
        ("j", "down", "Next"),
        ("k", "up", "Prev"),
        ("enter", "select", "Select"),
    ]

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._snapshot: HUDSnapshot | None = None
        self._selected_node: str | None = None
        self._node_list: list[str] = []

    def update_snapshot(self, snapshot: HUDSnapshot) -> None:
        self._snapshot = snapshot
        self._build_node_list()
        self.refresh()

    def _build_node_list(self) -> None:
        if not self._snapshot:
            self._node_list = []
            return
        self._node_list = [n.node_name for n in self._snapshot.topology]

    def select_node(self, node_name: str) -> None:
        self._selected_node = node_name
        self.refresh()
        self.post_message(NodeSelected(node_name))

    def action_down(self) -> None:
        if not self._node_list:
            return
        idx = self._node_list.index(self._selected_node) + 1 if self._selected_node in self._node_list else 0
        if idx >= len(self._node_list):
            idx = 0
        self.select_node(self._node_list[idx])

    def action_up(self) -> None:
        if not self._node_list:
            return
        idx = self._node_list.index(self._selected_node) - 1 if self._selected_node in self._node_list else -1
        if idx < 0:
            idx = len(self._node_list) - 1
        self.select_node(self._node_list[idx])

    def action_select(self) -> None:
        if self._selected_node:
            self.post_message(NodeSelected(self._selected_node))

    def render_str(self) -> str:
        if not self._snapshot:
            return "  GRAPH MAP — No data"

        lines = ["[bold white on $boost]  GRAPH MAP (NAVIGABLE)  [/]", ""]
        current_phase = ""

        for node in self._snapshot.topology:
            phase = node.phase
            if phase != current_phase:
                current_phase = phase
                label = PHASE_LABELS.get(phase, phase.upper())
                color = PHASE_COLORS.get(phase, "white")
                lines.append(f"[bold {color}]{label}[/bold {color}]")

            is_selected = node.node_name == self._selected_node
            status_mark = self._node_status_mark(node.status, node.node_name)
            name = node.node_name

            if is_selected:
                name = f"[reverse][bold]{name}[/][/]"

            if node.status == "completed" and node.duration_seconds:
                dur = _format_duration(node.duration_seconds)
                lines.append(f"  {status_mark} {name} [dim]({dur})[/dim]")
            else:
                lines.append(f"  {status_mark} {name}")

        if self._selected_node:
            lines.append("")
            lines.append(f"[dim]Selected: [bold]{self._selected_node}[/][/]  [dim](Enter for details)[/]")

        return "\n".join(lines)

    def _node_status_mark(self, status: str, node_name: str) -> str:
        icon = _get_icon(node_name)
        if status == "completed":
            return f"[bold green][\u2713]{icon}[/bold green]"
        elif status == "cached":
            return f"[bold cyan][\u21bb]{icon}[/bold cyan]"
        elif status == "active":
            return f"[bold cyan blink][>{icon}[/bold cyan blink]"
        elif status == "failed":
            return f"[bold red][!]{icon}[/bold red]"
        elif status == "skipped":
            return f"[dim][—]{icon}[/dim]"
        elif status == "locked":
            return f"[dim][\U0001f512]{icon}[/dim]"
        else:
            return f"[dim][ ]{icon}[/dim]"


class PartyStatusPanel(Static):
    """Right panel showing active agents with stats."""

    DEFAULT_CSS = """
    PartyStatusPanel {
        border: round $accent;
        padding: 0 1;
        width: 55%;
        height: 100%;
    }
    """

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._snapshot: HUDSnapshot | None = None

    def update_snapshot(self, snapshot: HUDSnapshot) -> None:
        self._snapshot = snapshot
        self.refresh()

    def render_str(self) -> str:
        if not self._snapshot:
            return "  PARTY STATUS — No data"

        lines = ["[bold white on $accent]  PARTY STATUS (ACTIVE AGENTS)  [/]", ""]
        party = self._snapshot.party

        if not party:
            lines.append("[dim]PARTY IS RESTING[/dim]")
        else:
            for member in party:
                lines.append(f"[{member.color}][{member.icon}] {member.role}[/] [bold]{member.node_name}[/bold]")
                lines.append(f"  [dim]Attempt:[/dim] {member.attempt}/{member.attempts_max}")

                stamina_bar = _draw_bar(member.stamina_current, member.attempts_max, 10, "red")
                lines.append(f"  [dim]Stamina:[/dim] {stamina_bar}")

                mana_bar = _draw_bar(member.mana_current, member.mana_max, 10, "blue")
                lines.append(f"  [dim]Mana:[/dim] {mana_bar}")

                threat_icon = {
                    "low": "[green]\u25cf[/green]",
                    "medium": "[yellow]\u25cf[/yellow]",
                    "high": "[red]\u25cf[/red]",
                    "critical": "[bold red blink]\u25cf[/bold red blink]",
                }.get(member.threat_level, "[dim]\u25cf[/dim]")
                lines.append(f"  [dim]Threat:[/dim] {threat_icon} {member.threat_level.upper()}")

                duration = _format_duration(member.duration_seconds)
                lines.append(f"  [dim]Duration:[/dim] [cyan]{duration}[/cyan]")

                phase_color = _get_phase_color(member.phase_name)
                casting = _draw_casting_bar(member.tool_count, 10, phase_color)
                lines.append(f"  [dim]Casting:[/dim] {casting} [dim]{member.phase_name}[/dim]")

                lines.append(f"  [dim]Last action:[/dim] {member.last_action}")
                lines.append("")

        return "\n".join(lines)


class ThoughtsPanel(Static):
    """Live token stream from active agents."""

    DEFAULT_CSS = """
    ThoughtsPanel {
        border: round $warning;
        padding: 0 1;
        height: auto;
        max-height: 6;
    }
    """

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._snapshot: HUDSnapshot | None = None

    def update_snapshot(self, snapshot: HUDSnapshot) -> None:
        self._snapshot = snapshot
        self.refresh()

    def render_str(self) -> str:
        if not self._snapshot:
            return ""

        lines = []
        for member in self._snapshot.party:
            if not member.thinking_preview:
                continue
            icon = member.icon
            color = member.color
            text = member.thinking_preview
            wrapped = _wrap_text(text, 100)

            lines.append(f"[{color}][{icon}] {member.role}[/]")
            for line in wrapped:
                lines.append(f"[dim]{line}[/dim]")
            lines.append("")

        if not lines:
            lines.append("[dim]Awaiting agent thoughts...[/dim]")

        return "\n".join(lines)


class BottomTabs(TabbedContent):
    """Bottom section with Narrative Log and Node Inspector tabs."""

    DEFAULT_CSS = """
    BottomTabs {
        height: 100%;
    }
    """


class NarrativeLogPanel(Static):
    """Scrollable narrative event log."""

    DEFAULT_CSS = """
    NarrativeLogPanel {
        padding: 0 1;
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._snapshot: HUDSnapshot | None = None

    def update_snapshot(self, snapshot: HUDSnapshot) -> None:
        self._snapshot = snapshot
        self.refresh()

    def render_str(self) -> str:
        if not self._snapshot:
            return "[dim]No events yet...[/dim]"

        lines = []
        for ev in self._snapshot.narrative:
            wall_ts = self._snapshot.wall_clock_ref + (ev.timestamp - self._snapshot.monotonic_ref)
            import datetime

            ts = datetime.datetime.fromtimestamp(wall_ts).strftime("%H:%M:%S")
            action_icon = {
                "enter": "[cyan]>>[/cyan]",
                "exit": "[green]OK[/green]",
                "read": "[blue]R[/blue]",
                "write": "[green]W[/green]",
                "edit": "[yellow]E[/yellow]",
                "bash": "[bold]$[/bold]",
                "glob": "[dim]G[/dim]",
                "grep": "[dim]S[/dim]",
            }.get(ev.action_type, "[dim].[/dim]")
            lines.append(f"[dim][{ts}][/dim] [{ev.color}]{ev.icon}[/] {action_icon} {ev.description}")

        if not lines:
            lines.append("[dim]No events yet...[/dim]")

        return "\n".join(lines)


class NodeInspectorPanel(Static):
    """X-Ray view of a selected node's payload (input prompt + output result)."""

    DEFAULT_CSS = """
    NodeInspectorPanel {
        padding: 0 1;
        height: 100%;
        overflow: auto;
    }
    """

    BINDINGS = [
        ("i", "intervene", "Intervene"),
    ]

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        self._payload: NodePayload | None = None
        self._selected_node: str | None = None

    def set_payload(self, node_name: str, payload: NodePayload | None) -> None:
        self._selected_node = node_name
        self._payload = payload
        self.refresh()

    def action_intervene(self) -> None:
        if self._selected_node:
            self.post_message(InterventionRequested(self._selected_node))

    def render_str(self) -> str:
        if not self._selected_node:
            return (
                "[bold white]NODE INSPECTOR (X-RAY)[/]\n"
                "\n"
                "[dim]Select a node from the GRAPH MAP to inspect its payload.[/]\n"
                "[dim]Use Up/Down to navigate, Enter to select.[/]"
            )

        lines = [f"[bold white]NODE INSPECTOR: [bold cyan]{self._selected_node}[/][/]", ""]

        if not self._payload:
            lines.append("[dim]No payload data available for this node yet.[/dim]")
            lines.append("[dim]Press [bold]I[/] to intervene if node is active.[/]")
            return "\n".join(lines)

        payload = self._payload

        # Input prompt
        lines.append("[bold blue]INPUT PROMPT:[/bold blue]")
        if payload.input_prompt:
            prompt_preview = payload.input_prompt[:3000]
            if len(payload.input_prompt) > 3000:
                prompt_preview += f"\n[dim]... ({len(payload.input_prompt)} total chars)[/]"
            lines.append(prompt_preview)
        else:
            lines.append("[dim](no input prompt stored)[/dim]")

        lines.append("")

        # Output result
        lines.append("[bold green]OUTPUT RESULT:[/bold green]")
        if payload.output_result:
            result_preview = payload.output_result[:3000]
            if len(payload.output_result) > 3000:
                result_preview += f"\n[dim]... ({len(payload.output_result)} total chars)[/]"
            lines.append(result_preview)
        elif payload.output_data:
            import json

            try:
                json_str = json.dumps(payload.output_data, indent=2, default=str)
                if len(json_str) > 3000:
                    json_str += f"\n[dim]... ({len(json_str)} total chars)[/]"
                lines.append(json_str)
            except Exception:
                lines.append(str(payload.output_data)[:3000])
        else:
            lines.append("[dim](no output result stored)[/dim]")

        lines.append("")
        lines.append("[dim]Press [bold]I[/] to intervene if node is active.[/]")

        return "\n".join(lines)


class CapturedOutputLog(RichLog):
    """RichLog widget that captures stray stdout/stderr output.

    Prevents terminal corruption by sequestering any print() calls
    that leak through despite the TUI-active guards.
    """

    DEFAULT_CSS = """
    CapturedOutputLog {
        padding: 0 1;
        height: 100%;
        color: $text;
        background: $boost;
    }
    """


class StatusBar(Static):
    """Bottom status bar with bindings and execution state."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        content-align: center middle;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._is_paused = False
        self._step_mode = False

    def update_state(self, is_paused: bool, step_mode: bool) -> None:
        self._is_paused = is_paused
        self._step_mode = step_mode
        self.refresh()

    def render_str(self) -> str:
        pause_text = (
            "[bold red]PAUSED (Space to resume)[/]" if self._is_paused else "[green]RUNNING (Space to pause)[/]"
        )
        step_text = " [bold yellow]STEP MODE (S to toggle)[/]" if self._step_mode else ""
        return f"  {pause_text}{step_text}  |  j/k Navigate  Enter Select  S Step  I Intervene  Q Quit"


# ─── Intervention Modal ──────────────────────────────────────────────


class InterventionModal(ModalScreen[str]):
    """Modal screen for direct agent intervention.

    Returns the intervention text on confirm, or empty string on cancel.
    """

    DEFAULT_CSS = """
    InterventionModal {
        align: center middle;
    }
    InterventionModal #modal-container {
        border: thick $warning;
        padding: 1 2;
        width: 70%;
        height: 40%;
    }
    InterventionModal #modal-title {
        dock: top;
        background: $warning;
        color: $text;
        height: 1;
        content-align: center middle;
    }
    InterventionModal #node-label {
        padding: 1 0 0 0;
    }
    InterventionModal #instruction-text {
        padding: 0 0 1 0;
    }
    InterventionModal .input-area {
        dock: bottom;
        padding: 1 0 0 0;
    }
    InterventionModal #intervention-input {
        width: 100%;
        height: 6;
    }
    """

    def __init__(self, node_name: str) -> None:
        super().__init__()
        self.node_name = node_name

    def compose(self) -> ComposeResult:
        yield Container(
            id="modal-container",
        ).compose(
            Label("[bold]INTERVENTION MODAL[/]", id="modal-title"),
            Label(f"Node: [bold cyan]{self.node_name}[/bold cyan]", id="node-label"),
            Label(
                "Type instructions to inject into the agent's context.\n"
                "This will be added as a system message to guide the agent.",
                id="instruction-text",
            ),
            Input(
                placeholder="Type your intervention here...",
                id="intervention-input",
            ),
            Label(
                "[green]Enter[/green] to confirm  |  [red]Esc[/red] to cancel",
                classes="input-area",
            ),
        )

    def on_mount(self) -> None:
        self.query_one("#intervention-input", Input).focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss("")
        elif event.key == "enter":
            input_widget = self.query_one("#intervention-input", Input)
            text = input_widget.value.strip()
            self.dismiss(text)


# ─── Main App ────────────────────────────────────────────────────────


class MAGEHUDApp(App):
    """MAGE HUD v2.0 — Interactive Control Panel.

    A Textual-based TUI that provides:
    - Navigable graph visualization
    - Node inspector (X-Ray payload view)
    - Execution controls (pause/resume/step)
    - Intervention modal
    - Live token streaming
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-rows: 3 1fr 4 1;
        grid-gutter: 1;
        height: 100%;
    }
    """

    CSS_TEMPLATE = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-rows: 3 1fr 4 1;
        grid-gutter: 1;
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_pause", "Pause/Resume"),
        ("s", "step", "Step"),
        ("i", "intervene", "Intervene"),
    ]

    def __init__(
        self,
        execution_state: ExecutionState | None = None,
        normalizer: Any | None = None,
    ) -> None:
        super().__init__()
        self.execution_state = execution_state
        self.normalizer = normalizer
        self._refresh_task: asyncio.Task | None = None
        self._running = True
        self._redirector = OutputRedirector(self)

    def compose(self) -> ComposeResult:
        # Row 1: Quest Bar (spans both columns)
        yield QuestBar()

        # Row 2: Graph + Party (side by side)
        yield NavigableGraph(id="graph")
        yield PartyStatusPanel(id="party")

        # Row 3: Bottom tabs (Narrative + Inspector + Captured Output)
        bottom_tabs = BottomTabs(id="bottom-tabs")
        yield bottom_tabs
        bottom_tabs.mount(
            TabPane("Narrative Log", NarrativeLogPanel(id="narrative")),
            TabPane("Node Inspector", NodeInspectorPanel(id="inspector")),
            TabPane("Captured Output", CapturedOutputLog(id="captured-output")),
        )

        # Row 4: Status Bar
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self._refresh_task = self.set_interval(0.25, self._refresh_from_state)
        # Sequester stdout/stderr to prevent leakage that corrupts the TUI
        self._redirector.install()

    def on_exit(self) -> None:
        # Restore original stdout/stderr when TUI exits
        self._redirector.uninstall()

    def _refresh_from_state(self) -> None:
        if not self.execution_state:
            return
        try:
            snapshot = self.execution_state.get_snapshot()
            self._update_widgets(snapshot)
        except Exception:
            pass

    def _update_widgets(self, snapshot: HUDSnapshot) -> None:
        quest_bar = self.query_one("QuestBar")
        quest_bar.update_snapshot(snapshot)

        graph = self.query_one("#graph", NavigableGraph)
        graph.update_snapshot(snapshot)

        party = self.query_one("#party", PartyStatusPanel)
        party.update_snapshot(snapshot)

        narrative = self.query_one("#narrative", NarrativeLogPanel)
        narrative.update_snapshot(snapshot)

        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_state(snapshot.is_paused, snapshot.step_mode)

    def action_quit(self) -> None:
        self._running = False
        self.post_message(QuitRequested())
        self.exit()

    def action_toggle_pause(self) -> None:
        if not self.execution_state:
            return
        if self.execution_state.is_paused:
            self.execution_state.resume()
        else:
            self.execution_state.pause()
        self.post_message(PauseToggled(self.execution_state.is_paused))

    def action_step(self) -> None:
        if not self.execution_state:
            return
        self.execution_state.step()
        self.post_message(StepRequested())

    def action_intervene(self) -> None:
        graph = self.query_one("#graph", NavigableGraph)
        node_name = graph._selected_node
        if not node_name:
            node_name = self._get_active_node()
        if not node_name:
            return
        self.push_screen(InterventionModal(node_name), self._on_intervention_complete)

    def _get_active_node(self) -> str | None:
        if not self.execution_state:
            return None
        for exec_record in self.execution_state.active_party:
            return exec_record.node_name
        return None

    def _on_intervention_complete(self, text: str) -> None:
        if not text or not self.normalizer:
            return
        graph = self.query_one("#graph", NavigableGraph)
        node_name = graph._selected_node or self._get_active_node()
        if node_name:
            self.execution_state.add_intervention(node_name, text)

    # ─── Event Handlers ──────────────────────────────────────────

    @on(NodeSelected)
    def on_node_selected(self, event: NodeSelected) -> None:
        inspector = self.query_one("#inspector", NodeInspectorPanel)
        if self.execution_state:
            payload = self.execution_state.get_payload(event.node_name)
        else:
            payload = None
        inspector.set_payload(event.node_name, payload)
        # Switch to inspector tab
        tabs = self.query_one("#bottom-tabs", BottomTabs)
        tabs.active = "Node Inspector"

    @on(InterventionRequested)
    def on_intervention_requested(self, event: InterventionRequested) -> None:
        self.push_screen(InterventionModal(event.node_name), self._on_intervention_complete)

    @on(StdoutCaptured)
    def on_stdout_captured(self, event: StdoutCaptured) -> None:
        """Route captured stdout/stderr to the Captured Output tab."""
        try:
            log = self.query_one("#captured-output", CapturedOutputLog)
            log.write(event.text)
        except Exception:
            pass


# ─── Helper Functions ────────────────────────────────────────────────


def _draw_bar(current: int, maximum: int, width: int, color: str) -> str:
    if maximum <= 0:
        maximum = 1
    ratio = min(current / maximum, 1.0)
    filled = max(0, min(int(ratio * width), width))
    empty = width - filled
    bar = f"[{color}]" + "\u2588" * filled + "\u2591" * empty + f"[/{color}]"
    return f"{bar} {current}/{maximum}"


PHASE_COLORS_MAP = {
    "thinking": "blue",
    "reading": "blue",
    "searching": "yellow",
    "writing": "green",
    "editing": "green",
    "bashing": "red",
    "globing": "yellow",
    "gripping": "yellow",
    "idle": "dim",
}


def _draw_casting_bar(tool_count: int, width: int, color: str) -> str:
    cycle = tool_count % (width + 1)
    filled = max(0, min(cycle, width))
    empty = width - filled
    bar = f"[{color}]" + "\u2588" * filled + "\u2591" * empty + f"[/{color}]"
    return bar


def _get_phase_color(phase_name: str) -> str:
    return PHASE_COLORS_MAP.get(phase_name, "white")


def _wrap_text(text: str, max_width: int) -> list[str]:
    wrapped = []
    while len(text) > max_width:
        break_point = text[:max_width].rfind(" ")
        if break_point <= 0:
            break_point = max_width
        wrapped.append(text[:break_point])
        text = text[break_point:].lstrip()
    if text:
        wrapped.append(text)
    return wrapped


# ─── HUD Controller (bridges Textual app with CLI engine) ────────────


class TextualHUDController:
    """Controls the Textual HUD from the CLI engine thread.

    The engine calls methods on this controller, which schedules
    updates on the Textual app's event loop.
    """

    def __init__(
        self,
        execution_state: ExecutionState,
        normalizer: Any,
        work_item: str,
    ) -> None:
        self.execution_state = execution_state
        self.normalizer = normalizer
        self.app = MAGEHUDApp(execution_state, normalizer)
        self._work_item = work_item
        self._running = False
        self._app_thread: threading.Thread | None = None

    def _run_app_thread(self) -> None:
        """Run the Textual app in a background thread."""
        try:
            self.app.run()
        except Exception:
            pass
        self._running = False

    def start(self) -> None:
        """Start the HUD in a background thread."""
        from eng_loop.tools.progress import ui as progress_ui

        progress_ui.set_tui_active(True)
        self._running = True
        self._app_thread = threading.Thread(target=self._run_app_thread, daemon=True)
        self._app_thread.start()

    def stop(self) -> None:
        """Stop the HUD."""
        from eng_loop.tools.progress import ui as progress_ui

        self._running = False
        self.app.exit()
        if self._app_thread and self._app_thread.is_alive():
            self._app_thread.join(timeout=5)
        progress_ui.set_tui_active(False)

    def is_paused(self) -> bool:
        """Check if execution is paused (for engine to check)."""
        return self.execution_state.is_paused

    def wait_if_paused(self) -> asyncio.Future:
        """Return a future that completes when not paused.

        The engine should await this before executing each node.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        if not self.execution_state.is_paused:
            future.set_result(None)
            return future

        def check_unpaused():
            if not self.execution_state.is_paused and not future.done():
                future.set_result(None)

        self.app.set_interval(0.1, check_unpaused)
        return future

    def has_intervention(self, node_name: str) -> str | None:
        """Check for and retrieve intervention text for a node."""
        return self.execution_state.get_intervention(node_name)

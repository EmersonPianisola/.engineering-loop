from __future__ import annotations

import datetime
import threading
import time
from collections import deque
from typing import Any

from rich import box
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from eng_loop.state import get_work_item_text
from eng_loop.tools.trace_logger import trace as _trace_logger

STAGE_CLASSES = {
    "init": ("MAGE", "blue"),
    "init.ideate": ("MAGE", "blue"),
    "init.bdd": ("MAGE", "blue"),
    "init.refine": ("MAGE", "blue"),
    "design.user-research": ("DESIGNER", "cyan"),
    "design.personas": ("DESIGNER", "cyan"),
    "design.info-arch": ("DESIGNER", "cyan"),
    "design.interaction": ("DESIGNER", "cyan"),
    "design.design-system": ("DESIGNER", "cyan"),
    "design.visual-design": ("DESIGNER", "cyan"),
    "arch.requirements": ("ARCHITECT", "magenta"),
    "arch.solution": ("ARCHITECT", "magenta"),
    "arch.review": ("ARCHITECT", "magenta"),
    "impl.design": ("ARCHITECT", "magenta"),
    "impl.code": ("WARRIOR", "green"),
    "doc.update": ("CHRONICLER", "white"),
    "verify": ("INSPECTOR", "yellow"),
    "qa.static": ("ANALYST", "bright_cyan"),
    "qa.unit": ("ALCHMIST", "bright_magenta"),
    "qa.integration": ("SCRIBE", "cyan"),
    "e2e.execute": ("ALCHMIST", "bright_magenta"),
    "qa.security": ("GUARD", "red"),
    "qa.api-contract": ("SCRIBE", "cyan"),
    "qa.performance": ("SPEEDSTER", "bright_yellow"),
    "qa.human.flow": ("EMPATH", "bright_white"),
    "qa.human.ux": ("EMPATH", "bright_white"),
    "deploy.prepare": ("PILOT", "bright_blue"),
    "smoke.test": ("ALCHMIST", "bright_magenta"),
    "doc.decisions": ("CHRONICLER", "white"),
    "doc.project": ("CHRONICLER", "white"),
    "post": ("HERO", "green"),
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
    "ANALYST": "N",
    "EMPATH": "M",
}

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


def _stage_to_node(stage_id):
    return stage_id.replace(".", "-").replace("_", "-")


def _node_to_stage(node_name):
    # Only replace the first hyphen (prefix separator). Sub-ids may contain hyphens.
    # e.g. "design-user-research" -> "design.user-research"
    return node_name.replace("-", ".", 1)


def _get_phase(stage_id):
    for phase in PHASE_ORDER:
        if stage_id.startswith(phase):
            return phase
    return "post"


def _get_max_attempts(config, stage_id):
    key = "max_" + stage_id.replace(".", "_").replace("-", "_") + "_attempts"
    return config.get("constraints", {}).get(key, 2)


class ActionLog:
    def __init__(self, max_lines=8):
        self.max_lines = max_lines
        self.lines = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def append(self, level, message):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        styles = {
            "DEBUG": "dim",
            "WARN": "yellow",
            "ERROR": "bold red",
            "SYS": "bold magenta",
            "INFO": "white",
            "STALL": "bold yellow",
        }
        style = styles.get(level.upper(), "white")
        entry = f"[dim][{now}][/dim] [{style}][{level.upper()}][/] {message}"
        with self._lock:
            self.lines.append(entry)

    def render(self):
        with self._lock:
            lines = list(self.lines)
        text = "\n".join(lines)
        missing = self.max_lines - len(lines)
        if missing > 0:
            text += "\n" * missing
        return Panel(
            Text.from_markup(text),
            title="[grey15] ACTION LOG (TOWN CRIER)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )


class HUDRenderer:
    def __init__(
        self,
        console,
        execution_state: Any | None = None,
        normalizer: Any | None = None,
        graph=None,
        thread_config=None,
    ):
        self.console = console
        self.execution_state = execution_state
        self.normalizer = normalizer
        self.graph = graph
        self.config = thread_config or {}
        self.action_log = ActionLog(max_lines=8)
        self.live = None
        self._work_item = ""
        self._active_stages = []
        self._hud_config = {}
        self._running = False
        self._thread = None
        self._last_refresh = 0.0
        self._last_event = None
        self._current_stage = ""
        self._lock = threading.RLock()

    def log(self, level, message):
        self.action_log.append(level, message)
        if self.live:
            self.live.refresh()

    def set_current_stage(self, stage_id):
        self._current_stage = stage_id
        self._force_refresh()

    def _force_refresh(self):
        if self.live:
            try:
                layout = self._build_layout()
                with self._lock:
                    self.live.update(layout)
            except Exception as e:
                import sys

                print(f"\n[HUD _force_refresh error] {e}", file=sys.stderr)
                import traceback

                traceback.print_exc(file=sys.stderr)

    def clear_current_stage(self):
        self._current_stage = ""

    def start(self, work_item, active_stages, config, initial_state=None):
        self._work_item = work_item
        self._active_stages = active_stages
        self._hud_config = config
        self._running = True
        if initial_state:
            self._last_event = initial_state
        if active_stages:
            self._current_stage = active_stages[0]
        layout = self._build_layout()
        self.live = Live(layout, console=self.console, screen=False, refresh_per_second=4)
        self.live.start()
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._thread.start()

    def update(self, event=None):
        if event:
            self._last_event = event
        if not self.live:
            return
        try:
            with self._lock:
                layout = self._build_layout()
                self.live.update(layout)
        except Exception as e:
            import sys

            print(f"\n[HUD update error] {e}", file=sys.stderr)
            import traceback

            traceback.print_exc(file=sys.stderr)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self.live:
            self.live.stop()
            self.live = None

    def _refresh_loop(self):
        while self._running:
            time.sleep(0.2)
            now = time.monotonic()
            if now - self._last_refresh < 0.15:
                continue
            self._last_refresh = now
            try:
                self.update()
            except Exception as e:
                import sys

                print(f"\n[HUD refresh error] {e}", file=sys.stderr)
                import traceback

                traceback.print_exc(file=sys.stderr)

    def _get_graph_state(self):
        if not self.graph or not self.config:
            return {}
        try:
            with self._lock:
                state_obj = self.graph.get_state(self.config)
                values = dict(state_obj.values) if state_obj.values else {}
                next_nodes = list(state_obj.next) if state_obj.next else []
                values["_next_nodes"] = next_nodes
                return values
        except Exception:
            return {}

    def _build_layout(self):
        if self.execution_state:
            snapshot = self.execution_state.get_snapshot()
            return self._build_layout_from_snapshot(snapshot)
        if self._last_event:
            state = self._last_event
        else:
            state = self._get_graph_state()
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=2),
            Layout(name="main"),
            Layout(name="trace", size=8),
            Layout(name="footer", size=6),
        )
        layout["main"].split_row(
            Layout(name="map"),
            Layout(name="party"),
        )
        work_item = get_work_item_text(state, self._work_item)
        layout["header"].update(self._render_quest_bar_legacy(work_item))
        layout["map"].update(self._render_graph_map_legacy(state))
        layout["party"].update(self._render_party_status_legacy(state))
        layout["trace"].update(_trace_logger.render_panel())
        layout["footer"].update(self.action_log.render())
        return layout

    # ─── Snapshot-based rendering ──────────────────────────────────

    def _build_layout_from_snapshot(self, snapshot: Any) -> Layout:
        layout = Layout()
        has_thoughts = any(m.thinking_preview for m in snapshot.party)
        thoughts_size = 4 if has_thoughts else 0
        footer_size = max(6, 10 - thoughts_size)

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="thoughts", size=thoughts_size),
            Layout(name="trace", size=8),
            Layout(name="footer", size=footer_size),
        )
        layout["main"].split_row(
            Layout(name="map"),
            Layout(name="party"),
        )
        layout["header"].update(self._render_quest_bar(snapshot))
        layout["map"].update(self._render_graph_map(snapshot))
        layout["party"].update(self._render_party_status(snapshot))
        layout["thoughts"].update(self._render_thoughts(snapshot))
        layout["trace"].update(_trace_logger.render_panel())

        footer_content = Layout()
        footer_content.split_row(
            Layout(name="narrative"),
            Layout(name="cmdhistory"),
            Layout(name="actionlog"),
        )
        footer_content["narrative"].update(self._render_narrative_log(snapshot))
        footer_content["cmdhistory"].update(self._render_command_history(snapshot))
        footer_content["actionlog"].update(self.action_log.render())
        layout["footer"].update(footer_content)
        return layout

    def _render_quest_bar(self, snapshot: Any) -> Panel:
        status_style = self._get_quest_status_style(snapshot.quest_status)
        elapsed = _format_duration(snapshot.elapsed_seconds)
        title_text = f"[bold gold1] MAIN QUEST:[/bold gold1] [white]{snapshot.quest_title}[/white]"
        info_text = f"[dim]Status:[/dim] {status_style}  [dim]Time:[/dim] [cyan]{elapsed}[/cyan]  [dim]Gold:[/dim] [yellow]{snapshot.gold_spent:.2f}[/yellow]"
        return Panel(
            f"{title_text}\n{info_text}",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _render_graph_map(self, snapshot: Any) -> Panel:
        topology = snapshot.topology
        phases = {}
        for node in topology:
            phase = node.phase
            phases.setdefault(phase, []).append(node)

        # Build action label map from active party members
        action_map = {}
        for member in snapshot.party:
            if member.phase_name and member.phase_name != "idle":
                action_map[member.node_name] = member.phase_name

        lines = []
        for phase in PHASE_ORDER:
            nodes = phases.get(phase, [])
            if not nodes:
                continue
            label = PHASE_LABELS.get(phase, phase.upper())
            color = PHASE_COLORS.get(phase, "white")
            lines.append(f"[bold {color}]{label}[/bold {color}]")
            for node in nodes:
                action_label = action_map.get(node.node_name, "")
                status_mark = self._node_status_mark(node.status, node.node_name, action_label)
                if node.status == "completed" and node.duration_seconds:
                    dur = _format_duration(node.duration_seconds)
                    lines.append(f"  {status_mark} [dim]{node.node_name}[/dim] [dim]({dur})[/dim]")
                elif node.status == "completed":
                    lines.append(f"  {status_mark} [dim]{node.node_name}[/dim]")
                else:
                    lines.append(f"  {status_mark} [dim]{node.node_name}[/dim]")
            lines.append("")

        if not lines:
            lines.append("[dim]No active stages[/dim]")

        return Panel(
            "\n".join(lines),
            title="[grey15] GRAPH MAP (TOPOLOGY)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _node_status_mark(self, status: str, node_name: str, action_label: str = "") -> str:
        role = self._get_role(node_name)
        icon = CLASS_ICONS.get(role, "?")
        if status == "completed":
            return f"[bold green][\u2713]{icon}[/bold green]"
        elif status == "cached":
            return f"[bold cyan][\u21bb]{icon}[/bold cyan]"
        elif status == "active":
            suffix = f" ({action_label})" if action_label else ""
            return f"[bold cyan blink][>{icon}[/bold cyan blink]{suffix}"
        elif status == "failed":
            return f"[bold red][!]{icon}[/bold red]"
        elif status == "skipped":
            return f"[dim][—]{icon}[/dim]"
        elif status == "locked":
            return f"[dim][\U0001f512]{icon}[/dim]"
        else:
            return f"[dim][ ]{icon}[/dim]"

    def _render_party_status(self, snapshot: Any) -> Panel:
        party = snapshot.party
        lines = []
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

                # Casting bar — cyclic progress indicator for tool calls
                phase_color = _get_phase_color(member.phase_name)
                casting = _draw_casting_bar(member.tool_count, 10, phase_color)
                lines.append(f"  [dim]Casting:[/dim] {casting} [dim]{member.phase_name}[/dim]")

                lines.append(f"  [dim]Last action:[/dim] {member.last_action}")
                lines.append("")

        return Panel(
            "\n".join(lines),
            title="[grey15] PARTY STATUS (ACTIVE AGENTS)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _render_thoughts(self, snapshot: Any) -> Panel:
        """Render MAGE THOUGHTS panel — live token stream from active agents."""
        lines = []
        for member in snapshot.party:
            if not member.thinking_preview:
                continue
            role = member.role
            icon = member.icon
            color = member.color
            # Wrap long text to fit panel width (~60 chars per line)
            text = member.thinking_preview
            wrapped = []
            while len(text) > 60:
                break_point = text[:60].rfind(" ")
                if break_point <= 0:
                    break_point = 60
                wrapped.append(text[:break_point])
                text = text[break_point:].lstrip()
            if text:
                wrapped.append(text)

            header = f"[{color}][{icon}] {role}[/]"
            lines.append(header)
            for line in wrapped:
                lines.append(f"[dim]{line}[/dim]")
            lines.append("")

        if not lines:
            lines.append("[dim]Awaiting agent thoughts...[/dim]")

        return Panel(
            "\n".join(lines),
            title="[grey15] MAGE THOUGHTS (LIVE STREAM)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _render_narrative_log(self, snapshot: Any) -> Panel:
        events = snapshot.narrative
        lines = []
        for ev in events:
            wall_ts = snapshot.wall_clock_ref + (ev.timestamp - snapshot.monotonic_ref)
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

        return Panel(
            "\n".join(lines),
            title="[grey15] NARRATIVE LOG[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _render_command_history(self, snapshot: Any) -> Panel:
        """Render COMMAND HISTORY panel — CommandHistoryBuffer visibility."""
        entries = getattr(snapshot, "command_history", [])
        lines = []
        if not entries:
            lines.append("[dim]No commands yet...[/dim]")
        else:
            tool_icons = {
                "read": "[blue]R[/blue]",
                "write": "[green]W[/green]",
                "edit": "[yellow]E[/yellow]",
                "bash": "[bold]$[/bold]",
                "glob": "[dim]G[/dim]",
                "grep": "[dim]S[/dim]",
            }
            for entry in entries:
                icon = tool_icons.get(entry.tool_name, "[dim].[/dim]")
                count = entry.count
                if entry.is_intercepted:
                    status = "[bold red blink]![/bold red blink]"
                    count_str = f"[bold red]{count}x[/bold red]"
                elif count >= 3:
                    status = "[bold yellow]![/bold yellow]"
                    count_str = f"[bold yellow]{count}x[/bold yellow]"
                elif count >= 2:
                    status = "[dim].[/dim]"
                    count_str = f"[dim]{count}x[/dim]"
                else:
                    status = "[dim].[/dim]"
                    count_str = "[dim]1x[/dim]"
                target = entry.target[:30] if entry.target else ""
                lines.append(f"  {icon} {status} [{entry.tool_name}] {count_str} {target}")

        return Panel(
            "\n".join(lines),
            title="[grey15] COMMAND HISTORY[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _get_quest_status_style(self, status: str) -> str:
        styles = {
            "pending": "[dim]PENDING[/dim]",
            "running": "[bold green]RUNNING[/bold green]",
            "completed": "[bold green]COMPLETED[/bold green]",
            "failed": "[bold red]FAILED[/bold red]",
            "cancelled": "[bold yellow]CANCELLED[/bold yellow]",
        }
        return styles.get(status, f"[white]{status}[/white]")

    @staticmethod
    def _get_role(node_name: str) -> str:
        for key, (role, _) in STAGE_CLASSES.items():
            if node_name == key or node_name.startswith(key + "."):
                return role
        prefix = node_name.split(".")[0] if "." in node_name else node_name.split("-")[0]
        for key, (role, _) in STAGE_CLASSES.items():
            if key.startswith(prefix + "."):
                return role
        return "NPC"

    @staticmethod
    def _get_color(node_name: str) -> str:
        for key, (_, color) in STAGE_CLASSES.items():
            if node_name == key or node_name.startswith(key + "."):
                return color
        prefix = node_name.split(".")[0] if "." in node_name else node_name.split("-")[0]
        for key, (_, color) in STAGE_CLASSES.items():
            if key.startswith(prefix + "."):
                return color
        return "white"

    # ─── Legacy rendering (backward compat when no execution_state) ─

    def _render_quest_bar_legacy(self, work_item) -> Panel:
        if not work_item:
            work_item = "Awaiting Main Quest..."
        return Panel(
            f"[bold gold1]? MAIN QUEST:[/bold gold1] [white]{work_item}[/white]",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _render_graph_map_legacy(self, state) -> Panel:
        stages = state.get("stages", {})
        next_nodes = state.get("_next_nodes", [])
        current_node = state.get("current_stage", "")
        current_stage_id = _node_to_stage(current_node) if current_node else ""
        active = self._active_stages
        if not active and state.get("active_nodes"):
            active = state["active_nodes"]
        done_set = {s for s in active if stages.get(s, {}).get("done", False)}
        current_set = set()
        if self._current_stage:
            current_set.add(self._current_stage)
        if current_stage_id and current_stage_id not in current_set:
            current_set.add(current_stage_id)
        for n in next_nodes:
            current_set.add(_node_to_stage(n))
        phases = {}
        for sid in active:
            phase = _get_phase(sid)
            phases.setdefault(phase, []).append(sid)
        lines = []
        for phase in PHASE_ORDER:
            stage_list = phases.get(phase, [])
            if not stage_list:
                continue
            label = PHASE_LABELS.get(phase, phase.upper())
            color = PHASE_COLORS.get(phase, "white")
            lines.append(f"[bold {color}]{label}[/bold {color}]")
            for sid in stage_list:
                if sid in done_set:
                    lines.append(f"  [bright_green][X][/bright_green] [dim]{sid}[/dim] [dim](Cleared)[/dim]")
                elif sid in current_set:
                    lines.append(f"  [bold cyan blink][>][/bold cyan blink] [bold cyan]{sid}[/bold cyan]")
                else:
                    lines.append(f"  [dim][ ][/dim] [dim]{sid} (Locked)[/dim]")
            lines.append("")
        if not lines:
            lines.append("[dim]No active stages[/dim]")
        return Panel(
            "\n".join(lines),
            title="[grey15] GRAPH MAP (TOPOLOGY)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _render_party_status_legacy(self, state) -> Panel:
        stages = state.get("stages", {})
        next_nodes = state.get("_next_nodes", [])
        current_node = state.get("current_stage", "")
        current_stage_id = _node_to_stage(current_node) if current_node else ""
        timing = state.get("timing", {})
        active = self._active_stages
        if not active and state.get("active_nodes"):
            active = state["active_nodes"]
        current_set = set()
        if self._current_stage:
            current_set.add(self._current_stage)
        if current_stage_id and current_stage_id not in current_set:
            current_set.add(current_stage_id)
        for n in next_nodes:
            current_set.add(_node_to_stage(n))
        lines = []
        for sid in active:
            cls_name, color = self._class_for_stage(sid)
            icon = CLASS_ICONS.get(cls_name, "?")
            stage_data = stages.get(sid, {})
            is_done = stage_data.get("done", False)
            attempts = stage_data.get("attempts", 0)
            max_att = _get_max_attempts(self._hud_config, sid)
            stage_timing = timing.get(sid, {})
            total_time = stage_timing.get("total_seconds", 0) if isinstance(stage_timing, dict) else 0
            if is_done:
                status_text = "[green][RESTING][/green]"
            elif sid in current_set:
                if attempts >= max_att:
                    status_text = "[bold red][STUNNED][/bold red] [dim](Debuff: Max attempts)[/dim]"
                else:
                    status_text = "[bold yellow][GRINDING][/bold yellow]"
            else:
                status_text = "[dim][UNAVAILABLE][/dim]"
            hp_current = max(0, max_att - attempts)
            hp_bar = self._hp_bar(hp_current, max_att)
            elapsed_str = self._format_time(total_time)
            lines.append(f"[{color}][{icon}] {cls_name}[/] [bold]{sid}[/bold]")
            lines.append(f"  Status: {status_text}")
            lines.append(f"  HP: {hp_bar}  |  Time: [dim]{elapsed_str}[/dim]")
            lines.append("")
        if not lines:
            lines.append("[dim]Party is resting...[/dim]")
        return Panel(
            "\n".join(lines),
            title="[grey15] PARTY STATUS (ACTIVE NODES)[/grey15]",
            title_align="left",
            box=box.SQUARE,
            border_style="grey50",
        )

    def _hp_bar(self, current, maximum, width=10):
        if maximum <= 0:
            maximum = 1
        filled = max(0, min(int((current / maximum) * width), width))
        empty = width - filled
        pct = int((current / maximum) * 100)
        color = "red"
        if pct > 60:
            color = "green"
        elif pct > 30:
            color = "yellow"
        return f"[{color}]" + "S" * filled + "U" * empty + f"[/{color}] {pct}%"

    def _format_time(self, seconds):
        if seconds < 60:
            return f"{seconds:.0f}s"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"

    def _class_for_stage(self, stage_id):
        if stage_id in STAGE_CLASSES:
            return STAGE_CLASSES[stage_id]
        for key, value in STAGE_CLASSES.items():
            if stage_id.startswith(key.split(".")[0] + "."):
                return value
        return ("NPC", "white")


# ─── Helper functions ─────────────────────────────────────────────────


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
    """Cyclic progress bar that fills as tool calls accumulate.

    Uses tool_count mod (width+1) so the bar cycles like a skill cooldown,
    giving constant visual motion during agent execution.
    """
    cycle = tool_count % (width + 1)
    filled = max(0, min(cycle, width))
    empty = width - filled
    bar = f"[{color}]" + "\u2588" * filled + "\u2591" * empty + f"[/{color}]"
    return bar


def _get_phase_color(phase_name: str) -> str:
    return PHASE_COLORS_MAP.get(phase_name, "white")


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

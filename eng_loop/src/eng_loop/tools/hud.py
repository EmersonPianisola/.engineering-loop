from __future__ import annotations

import datetime
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Optional

from rich import box
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from eng_loop.tools.execution_state import ExecutionState, HUDSnapshot
    from eng_loop.tools.event_normalizer import EventNormalizer


STAGE_CLASSES = {
    'init': ('MAGE', 'blue'),
    'init.ideate': ('MAGE', 'blue'),
    'init.bdd': ('MAGE', 'blue'),
    'init.refine': ('MAGE', 'blue'),
    'design.user-research': ('DESIGNER', 'cyan'),
    'design.personas': ('DESIGNER', 'cyan'),
    'design.info-arch': ('DESIGNER', 'cyan'),
    'design.interaction': ('DESIGNER', 'cyan'),
    'design.design-system': ('DESIGNER', 'cyan'),
    'design.visual-design': ('DESIGNER', 'cyan'),
    'arch.requirements': ('ARCHITECT', 'magenta'),
    'arch.solution': ('ARCHITECT', 'magenta'),
    'arch.review': ('ARCHITECT', 'magenta'),
    'impl.design': ('ARCHITECT', 'magenta'),
    'impl.code': ('WARRIOR', 'green'),
    'doc.update': ('CHRONICLER', 'white'),
    'verify': ('INSPECTOR', 'yellow'),
    'e2e.execute': ('ALCHMIST', 'bright_magenta'),
    'qa.security': ('GUARD', 'red'),
    'qa.api-contract': ('SCRIBE', 'cyan'),
    'qa.performance': ('SPEEDSTER', 'bright_yellow'),
    'deploy.prepare': ('PILOT', 'bright_blue'),
    'smoke.test': ('ALCHMIST', 'bright_magenta'),
    'doc.decisions': ('CHRONICLER', 'white'),
    'doc.project': ('CHRONICLER', 'white'),
    'post': ('HERO', 'green'),
}

CLASS_ICONS = {
    'MAGE': 'G', 'DESIGNER': 'D', 'ARCHITECT': 'A', 'WARRIOR': 'W',
    'CHRONICLER': 'C', 'INSPECTOR': 'I', 'ALCHMIST': 'E', 'GUARD': 'S',
    'SCRIBE': 'R', 'SPEEDSTER': 'P', 'PILOT': 'Z', 'HERO': 'H',
}

PHASE_ORDER = ['init', 'design', 'arch', 'impl', 'verify', 'qa', 'deploy', 'doc', 'post']
PHASE_LABELS = {
    'init': 'INIT', 'design': 'DESIGN', 'arch': 'ARCH', 'impl': 'IMPL',
    'verify': 'VERIFY', 'qa': 'QA', 'deploy': 'DEPLOY', 'doc': 'DOC', 'post': 'POST',
}
PHASE_COLORS = {
    'init': 'blue', 'design': 'cyan', 'arch': 'magenta', 'impl': 'green',
    'verify': 'yellow', 'qa': 'red', 'deploy': 'bright_blue',
    'doc': 'bright_cyan', 'post': 'white',
}


def _stage_to_node(stage_id):
    return stage_id.replace('.', '-').replace('_', '-')


def _node_to_stage(node_name):
    # Only replace the first hyphen (prefix separator). Sub-ids may contain hyphens.
    # e.g. "design-user-research" -> "design.user-research"
    return node_name.replace('-', '.', 1)


def _get_phase(stage_id):
    for phase in PHASE_ORDER:
        if stage_id.startswith(phase):
            return phase
    return 'post'


def _get_max_attempts(config, stage_id):
    key = 'max_' + stage_id.replace('.', '_').replace('-', '_') + '_attempts'
    return config.get('constraints', {}).get(key, 2)


class ActionLog:
    def __init__(self, max_lines=8):
        self.max_lines = max_lines
        self.lines = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def append(self, level, message):
        now = datetime.datetime.now().strftime('%H:%M:%S')
        styles = {
            'DEBUG': 'dim', 'WARN': 'yellow', 'ERROR': 'bold red',
            'SYS': 'bold magenta', 'INFO': 'white', 'STALL': 'bold yellow',
        }
        style = styles.get(level.upper(), 'white')
        entry = '[dim][%s][/dim] [%s][%s][/] %s' % (now, style, level.upper(), message)
        with self._lock:
            self.lines.append(entry)

    def render(self):
        with self._lock:
            lines = list(self.lines)
        text = '\n'.join(lines)
        missing = self.max_lines - len(lines)
        if missing > 0:
            text += '\n' * missing
        return Panel(
            Text.from_markup(text),
            title='[grey15] ACTION LOG (TOWN CRIER)[/grey15]',
            title_align='left',
            box=box.SQUARE,
            border_style='grey50',
        )


class HUDRenderer:
    def __init__(
        self,
        console,
        execution_state: Optional[Any] = None,
        normalizer: Optional[Any] = None,
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
        self._work_item = ''
        self._active_stages = []
        self._hud_config = {}
        self._running = False
        self._thread = None
        self._last_refresh = 0.0
        self._last_event = None
        self._current_stage = ''
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
        self._current_stage = ''

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
                values['_next_nodes'] = next_nodes
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
            Layout(name='header', size=2),
            Layout(name='main'),
            Layout(name='footer', size=10),
        )
        layout['main'].split_row(
            Layout(name='map'),
            Layout(name='party'),
        )
        work_item = state.get('work_item', self._work_item)
        layout['header'].update(self._render_quest_bar_legacy(work_item))
        layout['map'].update(self._render_graph_map_legacy(state))
        layout['party'].update(self._render_party_status_legacy(state))
        layout['footer'].update(self.action_log.render())
        return layout

    # ─── Snapshot-based rendering ──────────────────────────────────

    def _build_layout_from_snapshot(self, snapshot: Any) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name='header', size=3),
            Layout(name='main'),
            Layout(name='footer', size=10),
        )
        layout['main'].split_row(
            Layout(name='map'),
            Layout(name='party'),
        )
        layout['header'].update(self._render_quest_bar(snapshot))
        layout['map'].update(self._render_graph_map(snapshot))
        layout['party'].update(self._render_party_status(snapshot))
        footer_content = Layout()
        footer_content.split_row(
            Layout(name='narrative'),
            Layout(name='actionlog'),
        )
        footer_content['narrative'].update(self._render_narrative_log(snapshot))
        footer_content['actionlog'].update(self.action_log.render())
        layout['footer'].update(footer_content)
        return layout

    def _render_quest_bar(self, snapshot: Any) -> Panel:
        status_style = self._get_quest_status_style(snapshot.quest_status)
        elapsed = _format_duration(snapshot.elapsed_seconds)
        title_text = f"[bold gold1] MAIN QUEST:[/bold gold1] [white]{snapshot.quest_title}[/white]"
        info_text = f"[dim]Status:[/dim] {status_style}  [dim]Time:[/dim] [cyan]{elapsed}[/cyan]  [dim]Gold:[/dim] [yellow]{snapshot.gold_spent:.2f}[/yellow]"
        return Panel(
            f"{title_text}\n{info_text}",
            box=box.SQUARE,
            border_style='grey50',
        )

    def _render_graph_map(self, snapshot: Any) -> Panel:
        topology = snapshot.topology
        phases = {}
        for node in topology:
            phase = node.phase
            phases.setdefault(phase, []).append(node)

        lines = []
        for phase in PHASE_ORDER:
            nodes = phases.get(phase, [])
            if not nodes:
                continue
            label = PHASE_LABELS.get(phase, phase.upper())
            color = PHASE_COLORS.get(phase, 'white')
            lines.append(f'[bold {color}]{label}[/bold {color}]')
            for node in nodes:
                status_mark = self._node_status_mark(node.status, node.node_name)
                if node.status == 'completed' and node.duration_seconds:
                    dur = _format_duration(node.duration_seconds)
                    lines.append(f'  {status_mark} [dim]{node.node_name}[/dim] [dim]({dur})[/dim]')
                elif node.status == 'completed':
                    lines.append(f'  {status_mark} [dim]{node.node_name}[/dim]')
                else:
                    lines.append(f'  {status_mark} [dim]{node.node_name}[/dim]')
            lines.append('')

        if not lines:
            lines.append('[dim]No active stages[/dim]')

        return Panel(
            '\n'.join(lines),
            title='[grey15] GRAPH MAP (TOPOLOGY)[/grey15]',
            title_align='left',
            box=box.SQUARE,
            border_style='grey50',
        )

    def _node_status_mark(self, status: str, node_name: str) -> str:
        role = self._get_role(node_name)
        icon = CLASS_ICONS.get(role, '?')
        if status == 'completed':
            return f'[bold green][\u2713]{icon}[/bold green]'
        elif status == 'active':
            return f'[bold cyan blink][>{icon}[/bold cyan blink]'
        elif status == 'failed':
            return f'[bold red][!]{icon}[/bold red]'
        elif status == 'locked':
            return f'[dim][\U0001f512]{icon}[/dim]'
        else:
            return f'[dim][ ]{icon}[/dim]'

    def _render_party_status(self, snapshot: Any) -> Panel:
        party = snapshot.party
        lines = []
        if not party:
            lines.append('[dim]PARTY IS RESTING[/dim]')
        else:
            for member in party:
                lines.append(f'[{member.color}][{member.icon}] {member.role}[/] [bold]{member.node_name}[/bold]')
                lines.append(f'  [dim]Attempt:[/dim] {member.attempt}/{member.attempts_max}')

                stamina_bar = _draw_bar(member.stamina_current, member.attempts_max, 10, 'red')
                lines.append(f'  [dim]Stamina:[/dim] {stamina_bar}')

                mana_bar = _draw_bar(member.mana_current, member.mana_max, 10, 'blue')
                lines.append(f'  [dim]Mana:[/dim] {mana_bar}')

                threat_icon = {
                    'low': '[green]\u25cf[/green]',
                    'medium': '[yellow]\u25cf[/yellow]',
                    'high': '[red]\u25cf[/red]',
                    'critical': '[bold red blink]\u25cf[/bold red blink]',
                }.get(member.threat_level, '[dim]\u25cf[/dim]')
                lines.append(f'  [dim]Threat:[/dim] {threat_icon} {member.threat_level.upper()}')

                duration = _format_duration(member.duration_seconds)
                lines.append(f'  [dim]Duration:[/dim] [cyan]{duration}[/cyan]')
                lines.append(f'  [dim]Last action:[/dim] {member.last_action}')
                lines.append('')

        return Panel(
            '\n'.join(lines),
            title='[grey15] PARTY STATUS (ACTIVE AGENTS)[/grey15]',
            title_align='left',
            box=box.SQUARE,
            border_style='grey50',
        )

    def _render_narrative_log(self, snapshot: Any) -> Panel:
        events = snapshot.narrative
        lines = []
        for ev in events:
            wall_ts = snapshot.wall_clock_ref + (ev.timestamp - snapshot.monotonic_ref)
            ts = datetime.datetime.fromtimestamp(wall_ts).strftime('%H:%M:%S')
            action_icon = {
                'enter': '[cyan]>>[/cyan]',
                'exit': '[green]OK[/green]',
                'read': '[blue]R[/blue]',
                'write': '[green]W[/green]',
                'edit': '[yellow]E[/yellow]',
                'bash': '[bold]$[/bold]',
                'glob': '[dim]G[/dim]',
                'grep': '[dim]S[/dim]',
            }.get(ev.action_type, '[dim].[/dim]')
            lines.append(f'[dim][{ts}][/dim] [{ev.color}]{ev.icon}[/] {action_icon} {ev.description}')

        if not lines:
            lines.append('[dim]No events yet...[/dim]')

        return Panel(
            '\n'.join(lines),
            title='[grey15] NARRATIVE LOG[/grey15]',
            title_align='left',
            box=box.SQUARE,
            border_style='grey50',
        )

    def _get_quest_status_style(self, status: str) -> str:
        styles = {
            'pending': '[dim]PENDING[/dim]',
            'running': '[bold green]RUNNING[/bold green]',
            'completed': '[bold green]COMPLETED[/bold green]',
            'failed': '[bold red]FAILED[/bold red]',
            'cancelled': '[bold yellow]CANCELLED[/bold yellow]',
        }
        return styles.get(status, f'[white]{status}[/white]')

    @staticmethod
    def _get_role(node_name: str) -> str:
        for key, (role, _) in STAGE_CLASSES.items():
            if node_name == key or node_name.startswith(key + '.'):
                return role
        prefix = node_name.split('.')[0] if '.' in node_name else node_name.split('-')[0]
        for key, (role, _) in STAGE_CLASSES.items():
            if key.startswith(prefix + '.'):
                return role
        return 'NPC'

    @staticmethod
    def _get_color(node_name: str) -> str:
        for key, (_, color) in STAGE_CLASSES.items():
            if node_name == key or node_name.startswith(key + '.'):
                return color
        prefix = node_name.split('.')[0] if '.' in node_name else node_name.split('-')[0]
        for key, (_, color) in STAGE_CLASSES.items():
            if key.startswith(prefix + '.'):
                return color
        return 'white'

    # ─── Legacy rendering (backward compat when no execution_state) ─

    def _render_quest_bar_legacy(self, work_item) -> Panel:
        if not work_item:
            work_item = 'Awaiting Main Quest...'
        return Panel(
            '[bold gold1]? MAIN QUEST:[/bold gold1] [white]%s[/white]' % work_item,
            box=box.SQUARE,
            border_style='grey50',
        )

    def _render_graph_map_legacy(self, state) -> Panel:
        stages = state.get('stages', {})
        next_nodes = state.get('_next_nodes', [])
        current_node = state.get('current_stage', '')
        current_stage_id = _node_to_stage(current_node) if current_node else ''
        active = self._active_stages
        if not active and state.get('active_nodes'):
            active = state['active_nodes']
        done_set = set(s for s in active if stages.get(s, {}).get('done', False))
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
            color = PHASE_COLORS.get(phase, 'white')
            lines.append('[bold %s]%s[/bold %s]' % (color, label, color))
            for sid in stage_list:
                if sid in done_set:
                    lines.append('  [bright_green][X][/bright_green] [dim]%s[/dim] [dim](Cleared)[/dim]' % sid)
                elif sid in current_set:
                    lines.append('  [bold cyan blink][>][/bold cyan blink] [bold cyan]%s[/bold cyan]' % sid)
                else:
                    lines.append('  [dim][ ][/dim] [dim]%s (Locked)[/dim]' % sid)
            lines.append('')
        if not lines:
            lines.append('[dim]No active stages[/dim]')
        return Panel(
            '\n'.join(lines),
            title='[grey15] GRAPH MAP (TOPOLOGY)[/grey15]',
            title_align='left',
            box=box.SQUARE,
            border_style='grey50',
        )

    def _render_party_status_legacy(self, state) -> Panel:
        stages = state.get('stages', {})
        next_nodes = state.get('_next_nodes', [])
        current_node = state.get('current_stage', '')
        current_stage_id = _node_to_stage(current_node) if current_node else ''
        timing = state.get('timing', {})
        active = self._active_stages
        if not active and state.get('active_nodes'):
            active = state['active_nodes']
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
            icon = CLASS_ICONS.get(cls_name, '?')
            stage_data = stages.get(sid, {})
            is_done = stage_data.get('done', False)
            attempts = stage_data.get('attempts', 0)
            max_att = _get_max_attempts(self._hud_config, sid)
            stage_timing = timing.get(sid, {})
            total_time = stage_timing.get('total_seconds', 0) if isinstance(stage_timing, dict) else 0
            if is_done:
                status_text = '[green][RESTING][/green]'
            elif sid in current_set:
                if attempts >= max_att:
                    status_text = '[bold red][STUNNED][/bold red] [dim](Debuff: Max attempts)[/dim]'
                else:
                    status_text = '[bold yellow][GRINDING][/bold yellow]'
            else:
                status_text = '[dim][UNAVAILABLE][/dim]'
            hp_current = max(0, max_att - attempts)
            hp_bar = self._hp_bar(hp_current, max_att)
            elapsed_str = self._format_time(total_time)
            lines.append('[%s][%s] %s[/] [bold]%s[/bold]' % (color, icon, cls_name, sid))
            lines.append('  Status: %s' % status_text)
            lines.append('  HP: %s  |  Time: [dim]%s[/dim]' % (hp_bar, elapsed_str))
            lines.append('')
        if not lines:
            lines.append('[dim]Party is resting...[/dim]')
        return Panel(
            '\n'.join(lines),
            title='[grey15] PARTY STATUS (ACTIVE NODES)[/grey15]',
            title_align='left',
            box=box.SQUARE,
            border_style='grey50',
        )

    def _hp_bar(self, current, maximum, width=10):
        if maximum <= 0:
            maximum = 1
        filled = max(0, min(int((current / maximum) * width), width))
        empty = width - filled
        pct = int((current / maximum) * 100)
        color = 'red'
        if pct > 60:
            color = 'green'
        elif pct > 30:
            color = 'yellow'
        return '[%s]' % color + 'S' * filled + 'U' * empty + '[/%s] %d%%' % (color, pct)

    def _format_time(self, seconds):
        if seconds < 60:
            return '%.0fs' % seconds
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return '%dm %ds' % (mins, secs)

    def _class_for_stage(self, stage_id):
        if stage_id in STAGE_CLASSES:
            return STAGE_CLASSES[stage_id]
        for key, value in STAGE_CLASSES.items():
            if stage_id.startswith(key.split('.')[0] + '.'):
                return value
        return ('NPC', 'white')


# ─── Helper functions ─────────────────────────────────────────────────


def _draw_bar(current: int, maximum: int, width: int, color: str) -> str:
    if maximum <= 0:
        maximum = 1
    ratio = min(current / maximum, 1.0)
    filled = max(0, min(int(ratio * width), width))
    empty = width - filled
    bar = f'[{color}]' + '\u2588' * filled + '\u2591' * empty + f'[/{color}]'
    return f'{bar} {current}/{maximum}'


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f'{seconds:.0f}s'
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins < 60:
        return f'{mins}m {secs}s'
    hours = mins // 60
    remaining_mins = mins % 60
    return f'{hours}h {remaining_mins}m {secs}s'

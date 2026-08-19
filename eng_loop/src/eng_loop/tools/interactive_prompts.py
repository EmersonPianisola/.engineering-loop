from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console(force_terminal=True, soft_wrap=False)


# ── Severity styling ──────────────────────────────────────────────────
SEVERITY_STYLE: dict[str, str] = {
    "high": "red",
    "medium": "yellow",
    "low": "green",
}


def _severity_style(severity: str) -> str:
    return SEVERITY_STYLE.get(severity, "white")


# ── Arrow-key selectable list (prompt_toolkit) ────────────────────────
def _select_with_arrows(options: list[str], prompt: str) -> str | None:
    """Present options as an arrow-key navigable list.

    Falls back to numbered selection if prompt_toolkit is unavailable.
    Returns selected option string, or None on cancel.
    """
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import (
            HSplit,
            Layout,
            Window,
        )
        from prompt_toolkit.widgets import RadioList

        items = [(str(i + 1), opt) for i, opt in enumerate(options)]
        radio = RadioList(items)

        root = HSplit(
            [
                Window(
                    content=Text(prompt + "\n  Use ↑↓ to navigate, Enter to select, Esc to cancel.\n"),
                    always_hide=True,
                ),
                radio,
            ]
        )

        result = [None]

        kb = KeyBindings()

        def _set_and_exit(value: str | None) -> None:
            if value is not None:
                result[0] = value
            # Use event loop stop

        @kb.add("enter")
        def _enter(event):
            current = radio.current_value
            _set_and_exit(current[1] if current else None)
            event.app.exit()

        @kb.add("c-c")
        @kb.add("escape")
        def _cancel(event):
            event.app.exit()

        app = Application(
            layout=Layout(root),
            key_bindings=kb,
            full_screen=True,
        )
        app.run()

        return result[0]

    except ImportError:
        return _select_numbered_fallback(options, prompt)


def _select_numbered_fallback(options: list[str], prompt: str) -> str | None:
    """Fallback: numbered list with manual input."""
    console.print(f"\n{prompt}")
    console.print("  Arrow keys not available. Select by number:\n")
    for i, opt in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}[/]. {opt}")
    console.print("  [dim]Esc to cancel[/dim]\n")

    while True:
        try:
            raw = input("  Selection: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None

        if raw.lower() in ("q", "cancel", "abort"):
            return None

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass


# ── Free-form text input with bracketed paste support ─────────────────
def _text_input(prompt_text: str) -> str | None:
    """Collect free-form text input. Returns None on cancel."""
    try:
        raw = input(f"{prompt_text} ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if raw.lower() in ("q", "cancel", "abort"):
        return None
    return raw if raw else None


# ── Abort confirmation ────────────────────────────────────────────────
def _confirm_abort() -> str:
    """Prompt user: cancel pipeline or skip this step.

    Returns: 'cancel' or 'skip'
    """
    console.print()
    console.print(
        Panel(
            "[bold]What would you like to do?[/bold]\n\n"
            "  [bold green]1[/]. [bold]Cancel[/bold] — halt the pipeline\n"
            "  [bold yellow]2[/]. [bold]Skip[/bold] — skip this step and continue",
            title="[bold yellow]⚠ Interrupt[/bold yellow]",
            border_style="yellow",
        )
    )

    while True:
        try:
            raw = input("[1] Cancel / [2] Skip: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "cancel"

        if raw in ("1", "cancel", "c"):
            return "cancel"
        if raw in ("2", "skip", "s"):
            return "skip"


# ── Core: Paginated question collector ────────────────────────────────
class QuestionCollector:
    """Step-by-step question collector with in-place updates.

    Presents one question at a time. After each answer, renders a compact
    green confirmation line. Supports arrow-key selection for options.
    """

    def __init__(
        self,
        questions: list[dict[str, Any]],
        stage_id: str,
    ) -> None:
        self.questions = questions
        self.stage_id = stage_id
        self.answers: dict[str, str] = {}
        self._echo_lines: list[str] = []

    def collect(self) -> dict[str, str] | None:
        """Collect answers one question at a time.

        Returns dict of {question_id: answer} or None on cancel.
        """
        if not self.questions:
            return {}

        # Print header panel
        console.print()
        console.print(
            Panel(
                Text(
                    f"Stage [bold]{self.stage_id}[/bold] needs clarification.\n"
                    f"[dim]{len(self.questions)} question(s) — one at a time.[/dim]\n"
                    "[dim]Esc / Ctrl+C to interrupt.[/dim]",
                    style="yellow",
                ),
                title="[bold yellow]Essence Gate[/bold yellow]",
                border_style="yellow",
            )
        )

        for i, q in enumerate(self.questions, 1):
            result = self._ask_one(i, q)
            if result is None:
                # User interrupted
                action = _confirm_abort()
                if action == "cancel":
                    console.print("[red]Pipeline cancelled by user.[/red]")
                    return None
                # skip: return what we have so far
                if self.answers:
                    return self.answers
                return None

        # Print summary
        self._print_summary()
        return self.answers

    def _ask_one(self, index: int, q: dict[str, Any]) -> bool:
        """Ask a single question. Returns True if answered, False on skip."""
        qid = q.get("id", f"q_{index}")
        question = q.get("question", "Please clarify.")
        severity = q.get("severity", "medium")
        finding_summary = q.get("finding_summary", "")
        options = q.get("options", [])

        sev_style = _severity_style(severity)

        # Print question in a box
        q_lines = [
            f"[bold]{index}.[/bold] [bold {sev_style}][{severity.upper()}][/bold {sev_style}] {question}",
        ]
        if finding_summary:
            q_lines.append(f"   [dim]Finding: {finding_summary}[/dim]")

        console.print()
        console.print("\n".join(q_lines))

        # Decide input method
        answer = None

        if options:
            console.print(f"   Options: [cyan]{', '.join(options)}[/cyan]\n")
            selected = _select_with_arrows(
                options,
                f"  Select an option (Q{index}/{len(self.questions)}):",
            )
            if selected is None:
                return self._handle_interrupt(index)
            answer = selected
        else:
            raw = _text_input(f"  Your answer (Q{index}/{len(self.questions)})")
            if raw is None:
                return self._handle_interrupt(index)
            if raw.lower() == "skip":
                return True  # skip this question, move on
            answer = raw

        # Store answer
        self.answers[qid] = answer

        # Clean echo — compact green confirmation
        display_q = question[:60]
        if len(question) > 60:
            display_q += "…"
        self._echo_lines.append(f"[bold green]✓[/] Q{index} [dim]{display_q}:[/dim] [green]{answer}[/]")
        console.print(self._echo_lines[-1])

        return True

    def _handle_interrupt(self, index: int) -> bool:
        """Handle user interrupt (Esc/Ctrl+C) on a single question."""
        action = _confirm_abort()
        return action != "cancel"

    def _print_summary(self) -> None:
        """Print compact summary of all answers."""
        console.print()
        console.print("[dim]━" * 40 + "[/dim]")
        for line in self._echo_lines:
            console.print(line)
        console.print(f"[bold green]✓[/] [bold]{len(self.answers)}[/] answer(s) collected, proceeding.")
        console.print("[dim]━" * 40 + "[/dim]")


# ── Free-form question collector (for ask_user tool) ──────────────────
class FreeFormCollector:
    """Collect answers to free-form agent questions, one at a time."""

    def __init__(
        self,
        questions: list[str],
        context: str,
        stage_id: str,
    ) -> None:
        self.questions = questions
        self.context = context
        self.stage_id = stage_id

    def collect(self) -> list[str] | None:
        """Collect answers one at a time. Returns list or None on cancel."""
        if not self.questions:
            return []

        console.print()
        console.print(
            Panel(
                Text(
                    f"Stage [bold]{self.stage_id}[/bold] has questions for you.\n"
                    f"[dim]{len(self.questions)} question(s) — one at a time.[/dim]",
                    style="cyan",
                ),
                title="[bold cyan]Agent Needs Information[/bold cyan]",
                border_style="cyan",
            )
        )

        if self.context:
            console.print(f"   [dim]Context: {self.context}[/dim]")

        answers = []
        for i, q in enumerate(self.questions, 1):
            raw = _text_input(f"  {q} (Q{i}/{len(self.questions)})")
            if raw is None:
                action = _confirm_abort()
                if action == "cancel":
                    return None
                answers.append("")
                continue

            answers.append(raw)
            display_q = q[:50]
            if len(q) > 50:
                display_q += "…"
            console.print(f"[bold green]✓[/] Q{i} [dim]{display_q}:[/dim] [green]{raw}[/]")

        return answers


__all__ = [
    "FreeFormCollector",
    "QuestionCollector",
]

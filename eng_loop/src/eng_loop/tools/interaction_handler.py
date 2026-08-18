from __future__ import annotations

import sys
from typing import Any, Protocol


class InteractionRequest:
    """Abstraction over what the user needs to provide."""

    def __init__(
        self,
        blocking_condition: str,
        questions: list[dict[str, Any]],
        stage_id: str,
    ):
        self.blocking_condition = blocking_condition
        self.questions = questions
        self.stage_id = stage_id


class InteractionHandler(Protocol):
    """Collect user input for pending interactions.

    Abstracts the interaction surface so the CLI only presents
    and the handler collects. Prepares for Web UI, API, Slack, etc.
    """

    def collect(self, request: InteractionRequest) -> dict[str, str]:
        """Collect answers. Returns {question_id: answer} or empty dict on cancel."""
        ...

    def collect_questions(
        self,
        questions: list[str],
        context: str,
        stage_id: str,
    ) -> list[str]:
        """Collect answers to free-form questions (used by ask_user tool).

        Returns list of answers in same order as questions, or empty list on cancel.
        """
        ...

    def is_available(self) -> bool:
        """Whether this handler can operate in the current environment."""
        ...


class TTYInteractionHandler:
    """Interactive handler for TTY environments.

    Delegates to interactive_prompts for step-by-step pagination,
    arrow-key selection, and clean echo.
    """

    def is_available(self) -> bool:
        return sys.stdin.isatty() and sys.stdout.isatty()

    def collect(self, request: InteractionRequest) -> dict[str, str]:
        if not self.is_available():
            return {}

        questions = request.questions
        if not questions:
            return {}

        from eng_loop.tools.interactive_prompts import QuestionCollector

        collector = QuestionCollector(
            questions=questions,
            stage_id=request.stage_id,
        )
        result = collector.collect()
        return result if result is not None else {}

    def collect_questions(
        self,
        questions: list[str],
        context: str,
        stage_id: str,
    ) -> list[str]:
        if not self.is_available():
            return []

        from eng_loop.tools.interactive_prompts import FreeFormCollector

        collector = FreeFormCollector(
            questions=questions,
            context=context,
            stage_id=stage_id,
        )
        result = collector.collect()
        return result if result is not None else []


class NoOpInteractionHandler:
    """Non-interactive handler. Always unavailable — caller handles block."""

    def is_available(self) -> bool:
        return False

    def collect(self, request: InteractionRequest) -> dict[str, str]:
        return {}

    def collect_questions(
        self,
        questions: list[str],
        context: str,
        stage_id: str,
    ) -> list[str]:
        return []


def get_interaction_handler() -> InteractionHandler:
    """Return the best available interaction handler."""
    tty = TTYInteractionHandler()
    if tty.is_available():
        return tty
    return NoOpInteractionHandler()


__all__ = [
    "InteractionHandler",
    "InteractionRequest",
    "NoOpInteractionHandler",
    "TTYInteractionHandler",
    "get_interaction_handler",
]

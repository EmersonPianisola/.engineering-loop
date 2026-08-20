from __future__ import annotations

import json
import textwrap
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class AskUserInput(BaseModel):
    """Schema for asking the user questions during agent execution."""

    questions: list[str] = Field(
        description="List of questions to ask the user. Each question should be clear and specific.",
        min_length=1,
    )
    context: str = Field(
        default="",
        description="Optional context explaining why you need this information. Keep it brief.",
    )


class _AskUserState:
    """Thread-local marker for ask_user interception.

    The agent_runner intercepts ask_user tool calls before execution.
    This module-level storage records pending requests so the runner
    can detect and handle them.
    """

    def __init__(self):
        self.pending: dict | None = None

    def set(self, questions: list[str], context: str) -> str:
        """Record a pending ask_user request. Returns marker path."""
        marker = Path("__ask_user_marker__.json")
        self.pending = {
            "questions": questions,
            "context": context,
        }
        marker.write_text(
            json.dumps({"questions": questions, "context": context}),
            encoding="utf-8",
        )
        return str(marker)

    def clear(self):
        self.pending = None
        marker = Path("__ask_user_marker__.json")
        if marker.exists():
            marker.unlink()


_state = _AskUserState()


def _ask_user(questions: list[str], context: str = "") -> str:
    """Ask the user for input.

    IMPORTANT: This tool will be intercepted by the agent runner.
    The actual implementation writes a marker file that signals
    the runner to pause execution and collect user input from the terminal.

    Do NOT call this tool unless you genuinely need information only
    the user can provide. Use it when:
    - Requirements are ambiguous and cannot be resolved from context
    - A decision must be made that affects project direction
    - The user's preference is needed between valid alternatives

    Do NOT use this tool to:
    - Confirm information you already have
    - Ask about code that you can read yourself
    - Request approval for routine actions
    """
    marker_path = _state.set(questions, context)
    return (
        f"[SYSTEM] User input requested. Execution paused.\n"
        f"Marker written to: {marker_path}\n"
        f"Questions: {len(questions)}\n"
        "Waiting for user response..."
    )


def create_ask_user_tool() -> StructuredTool:
    """Create the ask_user LangChain tool.

    Note: This tool's function is intercepted by agent_runner before
    actual execution. The StructuredTool definition exists solely to
    provide the schema and description to the LLM.
    """
    return StructuredTool(
        name="ask_user",
        description=textwrap.dedent("""\
            Ask the user for information that you cannot determine from context.
            Use this when requirements are ambiguous, a decision is needed,
            or the user's preference is required. The agent will pause and
            present your questions to the user. You will receive their answers
            before continuing. Maximum 3 uses per task.
        """).strip(),
        func=_ask_user,
        args_schema=AskUserInput,
    )


__all__ = ["AskUserInput", "create_ask_user_tool"]

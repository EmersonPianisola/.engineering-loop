from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class EditInput(BaseModel):
    file_path: str = Field(description="Absolute or relative path to the file to edit")
    old_string: str = Field(description="Exact string to find and replace. Must appear exactly once in the file.")
    new_string: str = Field(description="Replacement string. If empty, deletes old_string.")


def _edit(file_path: str, old_string: str, new_string: str = "") -> str:
    if not file_path:
        return "Error: file_path is required"
    if not old_string:
        return "Error: old_string is required"
    if old_string == new_string:
        return "Error: old_string and new_string are identical"
    p = Path(file_path)
    if not p.exists():
        return f"Error: file not found: {file_path}"

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"

    if old_string not in content:
        lines = content.split("\n")
        snippet = "\n".join(lines[:20]) if len(lines) > 20 else content
        return f"Error: old_string not found in {file_path}. First 20 lines for context:\n{snippet}"

    if content.count(old_string) > 1:
        return (
            f"Error: old_string appears {content.count(old_string)} times. "
            f"Provide more surrounding context to make it unique."
        )

    new_content = content.replace(old_string, new_string, 1)
    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    return f"Edited {file_path}: replaced {len(old_string)} chars with {len(new_string)} chars"


def create_edit_tool() -> StructuredTool:
    return StructuredTool(
        name="edit",
        description=textwrap.dedent("""\
            Perform an exact string replacement in a file.
            Use for: modifying existing code, fixing bugs, updating configurations.
            The old_string must appear exactly once in the file.
            Provide enough surrounding context (neighboring lines) to make it unique.
            Do NOT include line numbers in old_string — only the actual file content.
        """).strip(),
        func=_edit,
        args_schema=EditInput,
    )


__all__ = ["EditInput", "create_edit_tool"]

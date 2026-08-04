from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_edit_tool() -> Tool:
    """Create an Edit tool that performs exact string replacements in files."""

    def _edit(file_path: str, old_string: str, new_string: str) -> str:
        p = Path(file_path)
        if not p.exists():
            return f"Error: file not found: {file_path}"
        if old_string == new_string:
            return f"Error: old_string and new_string are identical"

        try:
            content = p.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"

        if old_string not in content:
            # Provide context for what was found near the expected location
            lines = content.split("\n")
            snippet = "\n".join(lines[:20]) if len(lines) > 20 else content
            return (
                f"Error: old_string not found in {file_path}. "
                f"First 20 lines for context:\n{snippet}"
            )

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

    return Tool(
        name="edit",
        description=textwrap.dedent("""\
            Perform an exact string replacement in a file.
            Use for: modifying existing code, fixing bugs, updating configurations.
            The old_string must appear exactly once in the file.
            Provide enough surrounding context (neighboring lines) to make it unique.
            Do NOT include line numbers in old_string — only the actual file content.
        """).strip(),
        func=_edit,
    )


__all__ = ["create_edit_tool"]

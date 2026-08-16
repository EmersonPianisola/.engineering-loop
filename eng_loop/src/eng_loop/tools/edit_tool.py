from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_edit_tool() -> Tool:
    """Create an Edit tool that performs exact string replacements in files."""

    def _edit(*args, **kwargs) -> str:
        # Support: _edit(file_path, old_string, new_string), _edit(filePath=..., oldString=...)
        if "file_path" in kwargs or "filePath" in kwargs:
            file_path = kwargs.get("file_path") or kwargs.get("filePath", "")
        elif args:
            file_path = args[0]
        else:
            return "Error: file_path is required"

        if "old_string" in kwargs or "oldString" in kwargs:
            old_string = kwargs.get("old_string") or kwargs.get("oldString", "")
        elif len(args) >= 2:
            old_string = args[1]
        else:
            return "Error: old_string is required"

        if "new_string" in kwargs or "newString" in kwargs:
            new_string = kwargs.get("new_string") or kwargs.get("newString", "")
        elif len(args) >= 3:
            new_string = args[2]
        else:
            new_string = ""

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
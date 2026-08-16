from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_write_tool() -> Tool:
    """Create a Write tool for writing files to the filesystem."""

    def _write(*args, **kwargs) -> str:
        # Support: _write(file_path, content), _write(filePath=..., content=...)
        if "file_path" in kwargs or "filePath" in kwargs:
            file_path = kwargs.get("file_path") or kwargs.get("filePath", "")
        elif args:
            file_path = args[0]
        else:
            return "Error: file_path is required"

        if "content" in kwargs:
            content = kwargs.get("content", "")
        elif len(args) >= 2:
            content = args[1]
        else:
            return "Error: content is required"

        if not file_path:
            return "Error: file_path is required"
        if not content:
            return "Error: content is required"

        p = Path(file_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            lines = content.count("\n") + 1
            return f"Wrote {file_path} ({lines} lines, {len(content)} bytes)"
        except Exception as e:
            return f"Error writing file: {e}"

    return Tool(
        name="write",
        description=textwrap.dedent("""\
            Write content to a file, creating parent directories as needed.
            Overwrites existing files. Use for: creating new source files,
            writing test files, generating configuration files, creating documentation.
            Returns the number of lines and bytes written.
        """).strip(),
        func=_write,
    )


__all__ = ["create_write_tool"]
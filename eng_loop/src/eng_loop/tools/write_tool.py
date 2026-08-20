from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class WriteInput(BaseModel):
    file_path: str = Field(description="Absolute or relative path to the file to write")
    content: str = Field(description="Content to write to the file")


def _write(file_path: str = "", content: str = "", **kwargs) -> str:
    fp = kwargs.get("filePath", file_path)
    if fp:
        file_path = fp
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


def create_write_tool() -> StructuredTool:
    return StructuredTool(
        name="write",
        description=textwrap.dedent("""\
            Write content to a file, creating parent directories as needed.
            Overwrites existing files. Use for: creating new source files,
            writing test files, generating configuration files, creating documentation.
            Returns the number of lines and bytes written.
        """).strip(),
        func=_write,
        args_schema=WriteInput,
    )


__all__ = ["WriteInput", "create_write_tool"]

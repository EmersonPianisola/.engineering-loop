from __future__ import annotations

import textwrap
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from eng_loop.tools.sandbox import check_path


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

    p = check_path(file_path, kwargs.get("_sandbox"))
    if p is None:
        return f"Error: path '{file_path}' is outside the project root — blocked by sandbox"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        lines = content.count("\n") + 1
        return f"Wrote {file_path} ({lines} lines, {len(content)} bytes)"
    except Exception as e:
        return f"Error writing file: {e}"


def create_write_tool(sandbox: dict[str, Any] | None = None) -> StructuredTool:
    def _write_sandboxed(file_path: str = "", content: str = "", **kwargs) -> str:
        return _write(file_path, content, **{**kwargs, "_sandbox": sandbox})

    return StructuredTool(
        name="write",
        description=textwrap.dedent("""\
            Write content to a file, creating parent directories as needed.
            Overwrites existing files. Use for: creating new source files,
            writing test files, generating configuration files, creating documentation.
            Returns the number of lines and bytes written.
            Paths are relative to the project root and must stay inside it.
        """).strip(),
        func=_write_sandboxed,
        args_schema=WriteInput,
    )


__all__ = ["WriteInput", "create_write_tool"]

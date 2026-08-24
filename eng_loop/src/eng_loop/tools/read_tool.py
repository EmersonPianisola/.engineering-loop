from __future__ import annotations

import textwrap
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from eng_loop.tools.sandbox import check_path


class ReadInput(BaseModel):
    file_path: str = Field(description="Absolute or relative path to the file or directory to read")
    offset: int = Field(default=1, description="Line number to start reading from (1-indexed)")
    limit: int = Field(default=500, description="Maximum number of lines to read")


def _read(file_path: str = "", offset: int = 1, limit: int = 500, **kwargs) -> str:
    fp = kwargs.get("filePath", file_path)
    if fp:
        file_path = fp
    if not file_path:
        return "Error: file_path is required"
    sandbox = kwargs.get("_sandbox")
    p = check_path(file_path, sandbox)
    if p is None:
        return f"Error: path '{file_path}' is outside the project root — blocked by sandbox"
    if not p.exists():
        return f"Error: path not found: {file_path}"

    if p.is_dir():
        try:
            entries = sorted(str(e) for e in p.iterdir())
            dirs = [e + "/" for e in entries if p.joinpath(e).is_dir()]
            files = [e for e in entries if p.joinpath(e).is_file()]
            return f"Directory {file_path}:\n" + "\n".join(dirs + files)
        except Exception as e:
            return f"Error listing directory: {e}"

    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error reading file: {e}"

    lines = content.split("\n")
    total = len(lines)
    start = max(0, offset - 1)
    end = min(start + limit, total)
    sliced = lines[start:end]

    prefixed = []
    for i, line in enumerate(sliced, start=start + 1):
        truncated = line[:2000] if len(line) > 2000 else line
        prefixed.append(f"{i}: {truncated}")

    result = "\n".join(prefixed)
    if end < total:
        result += f"\n... ({total - end} more lines, use offset={end + 1} to continue)"
    if start > 0:
        result = f"... (continuing from line {start})\n" + result

    return f"({total} total lines, showing {start + 1}-{end})\n{result}"


def create_read_tool(sandbox: dict[str, Any] | None = None) -> StructuredTool:
    def _read_sandboxed(file_path: str = "", offset: int = 1, limit: int = 500, **kwargs) -> str:
        return _read(file_path, offset, limit, **{**kwargs, "_sandbox": sandbox})

    return StructuredTool(
        name="read",
        description=textwrap.dedent("""\
            Read a file or directory from the local filesystem.
            For files: returns content with line number prefixes.
            For directories: lists entries with trailing / for subdirectories.
            Use offset (1-indexed) and limit to read specific sections of large files.
            Lines longer than 2000 characters are truncated.
            Paths are relative to the project root and must stay inside it.
        """).strip(),
        func=_read_sandboxed,
        args_schema=ReadInput,
    )


__all__ = ["ReadInput", "create_read_tool"]

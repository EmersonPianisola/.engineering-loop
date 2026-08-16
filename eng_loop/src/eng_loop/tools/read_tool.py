from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_read_tool() -> Tool:
    """Create a Read tool for reading files and directories."""

    def _read(*args, **kwargs) -> str:
        # Support: _read(file_path), _read(file_path, offset, limit), _read(filePath=...)
        if "file_path" in kwargs or "filePath" in kwargs:
            actual_path = kwargs.get("file_path") or kwargs.get("filePath", "")
        elif args:
            actual_path = args[0]
        else:
            return "Error: file_path is required"

        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", 500)
        if len(args) >= 2:
            offset = args[1]
        if len(args) >= 3:
            limit = args[2]

        p = Path(actual_path)
        if not p.exists():
            return f"Error: path not found: {actual_path}"

        if p.is_dir():
            try:
                entries = sorted(str(e) for e in p.iterdir())
                dirs = [e + "/" for e in entries if p.joinpath(e).is_dir()]
                files = [e for e in entries if p.joinpath(e).is_file()]
                return f"Directory {actual_path}:\n" + "\n".join(dirs + files)
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

    return Tool(
        name="read",
        description=textwrap.dedent("""\
            Read a file or directory from the local filesystem.
            For files: returns content with line number prefixes.
            For directories: lists entries with trailing / for subdirectories.
            Use offset (1-indexed) and limit to read specific sections of large files.
            Lines longer than 2000 characters are truncated.
        """).strip(),
        func=_read,
    )


__all__ = ["create_read_tool"]
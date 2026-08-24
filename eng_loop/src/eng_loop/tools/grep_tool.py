from __future__ import annotations

import re
import textwrap
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from eng_loop.tools.sandbox import check_path


class GrepInput(BaseModel):
    pattern: str = Field(description="Regular expression pattern to search for")
    path: str = Field(default=".", description="Directory to search in")
    include: str = Field(
        default="*", description="File glob pattern to filter which files to search (e.g., '*.py', '*.{ts,tsx}')"
    )


def _grep(pattern: str = "", path: str = ".", include: str = "*", **kwargs) -> str:
    if not pattern:
        return "Error: pattern is required"
    base = check_path(path, kwargs.get("_sandbox"))
    if base is None:
        return f"Error: path '{path}' is outside the project root — blocked by sandbox"
    if not base.exists():
        return f"Error: path not found: {path}"

    try:
        regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as e:
        return f"Error: invalid regex '{pattern}': {e}"

    matches = []
    files_searched = 0

    for file_path in base.glob(f"**/{include}"):
        if not file_path.is_file():
            continue
        if file_path.suffix in (".png", ".jpg", ".gif", ".ico", ".exe", ".dll", ".so", ".pyc"):
            continue
        try:
            files_searched += 1
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line_num, line in enumerate(content.split("\n"), 1):
            if regex.search(line):
                rel = str(file_path.relative_to(base))
                truncated = line[:200]
                matches.append(f"{rel}:{line_num}: {truncated}")
                if len(matches) >= 200:
                    break
        if len(matches) >= 200:
            break

    if not matches:
        return f"No matches for '{pattern}' in {path} ({files_searched} files searched)"

    count = len(matches)
    return f"{count} matches for '{pattern}':\n" + "\n".join(matches)


def create_grep_tool(sandbox: dict[str, Any] | None = None) -> StructuredTool:
    def _grep_sandboxed(pattern: str = "", path: str = ".", include: str = "*", **kwargs) -> str:
        return _grep(pattern, path, include, **{**kwargs, "_sandbox": sandbox})

    return StructuredTool(
        name="grep",
        description=textwrap.dedent("""\
            Search file contents using regular expressions.
            Returns file paths and line numbers with matching lines.
            Use for: finding code patterns, searching for function definitions,
            locating specific strings across the codebase.
            The include parameter filters which files to search (e.g., "*.py", "*.{ts,tsx}").
            Paths are relative to the project root and must stay inside it.
        """).strip(),
        func=_grep_sandboxed,
        args_schema=GrepInput,
    )


__all__ = ["GrepInput", "create_grep_tool"]

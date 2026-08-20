from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern to match files (e.g., '**/*.py', 'src/**/*.ts')")
    path: str = Field(default=".", description="Directory to search in")


def _glob(pattern: str = "", path: str = ".") -> str:
    if not pattern:
        return "Error: pattern is required"
    base = Path(path)
    if not base.exists():
        return f"Error: directory not found: {path}"
    try:
        matches = sorted(str(m) for m in base.glob(pattern))
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        count = len(matches)
        max_show = 200
        if count > max_show:
            lines = "\n".join(matches[:max_show])
            return f"{count} files matching '{pattern}':\n{lines}\n... and {count - max_show} more"
        return f"{count} files matching '{pattern}':\n" + "\n".join(matches)
    except Exception as e:
        return f"Error globbing: {e}"


def create_glob_tool() -> StructuredTool:
    return StructuredTool(
        name="glob",
        description=textwrap.dedent("""\
            Find files by name pattern using glob syntax.
            Supports patterns like "**/*.py", "src/**/*.ts", "*.md".
            Returns matching file paths relative to the search directory.
            Use for: finding files by name, exploring project structure.
        """).strip(),
        func=_glob,
        args_schema=GlobInput,
    )


__all__ = ["GlobInput", "create_glob_tool"]

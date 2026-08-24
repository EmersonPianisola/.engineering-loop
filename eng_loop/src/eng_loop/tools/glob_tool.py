from __future__ import annotations

import textwrap
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from eng_loop.tools.sandbox import check_path, resolve_in_root


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern to match files (e.g., '**/*.py', 'src/**/*.ts')")
    path: str = Field(default=".", description="Directory to search in")


def _glob(pattern: str = "", path: str = ".", **kwargs) -> str:
    if not pattern:
        return "Error: pattern is required"
    sandbox = kwargs.get("_sandbox")
    base = check_path(path, sandbox)
    if base is None:
        return f"Error: directory '{path}' is outside the project root — blocked by sandbox"
    if not base.exists():
        return f"Error: directory not found: {path}"
    try:
        matches = sorted(str(m) for m in base.glob(pattern))
        # Patterns can contain '..' segments — keep only results inside the sandbox
        if sandbox and sandbox.get("enabled") and not sandbox.get("allow_out_of_root"):
            matches = [m for m in matches if resolve_in_root(m, sandbox.get("root", ".")) is not None]
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


def create_glob_tool(sandbox: dict[str, Any] | None = None) -> StructuredTool:
    def _glob_sandboxed(pattern: str = "", path: str = ".", **kwargs) -> str:
        return _glob(pattern, path, **{**kwargs, "_sandbox": sandbox})

    return StructuredTool(
        name="glob",
        description=textwrap.dedent("""\
            Find files by name pattern using glob syntax.
            Supports patterns like "**/*.py", "src/**/*.ts", "*.md".
            Returns matching file paths relative to the search directory.
            Use for: finding files by name, exploring project structure.
            Paths are relative to the project root and must stay inside it.
        """).strip(),
        func=_glob_sandboxed,
        args_schema=GlobInput,
    )


__all__ = ["GlobInput", "create_glob_tool"]

from __future__ import annotations

import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_glob_tool() -> Tool:
    """Create a Glob tool for file pattern matching."""

    def _glob(*args, **kwargs) -> str:
        # Support: _glob(pattern, path), _glob(pattern=..., path=...)
        if "pattern" in kwargs:
            pattern = kwargs.get("pattern", "")
        elif args:
            pattern = args[0]
        else:
            return "Error: pattern is required"

        if "path" in kwargs or "searchPath" in kwargs:
            path = kwargs.get("path") or kwargs.get("searchPath", ".")
        elif len(args) >= 2:
            path = args[1]
        else:
            path = "."

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

    return Tool(
        name="glob",
        description=textwrap.dedent("""\
            Find files by name pattern using glob syntax.
            Supports patterns like "**/*.py", "src/**/*.ts", "*.md".
            Returns matching file paths relative to the search directory.
            Use for: finding files by name, exploring project structure.
        """).strip(),
        func=_glob,
    )


__all__ = ["create_glob_tool"]
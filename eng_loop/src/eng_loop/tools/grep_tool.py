from __future__ import annotations

import re
import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_grep_tool() -> Tool:
    """Create a Grep tool for content search using regex."""

    def _grep(*args, **kwargs) -> str:
        # Support: _grep(pattern, path, include), _grep(pattern=..., path=...)
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

        if "include" in kwargs:
            include = kwargs.get("include", "*")
        elif len(args) >= 3:
            include = args[2]
        else:
            include = "*"

        if not pattern:
            return "Error: pattern is required"
        base = Path(path)
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

    return Tool(
        name="grep",
        description=textwrap.dedent("""\
            Search file contents using regular expressions.
            Returns file paths and line numbers with matching lines.
            Use for: finding code patterns, searching for function definitions,
            locating specific strings across the codebase.
            The include parameter filters which files to search (e.g., "*.py", "*.{ts,tsx}").
        """).strip(),
        func=_grep,
    )


__all__ = ["create_grep_tool"]
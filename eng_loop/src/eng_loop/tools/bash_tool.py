from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from langchain_core.tools import Tool


def create_bash_tool(
    workdir: str,
    timeout: int = 120,
) -> Tool:
    """Create a Bash tool that executes shell commands in the project directory."""

    def _bash(*args, **kwargs) -> str:
        # Support: _bash(command), _bash(cmd=...)
        if "command" in kwargs:
            command = kwargs.get("command", "")
        elif "cmd" in kwargs:
            command = kwargs.get("cmd", "")
        elif args:
            command = args[0]
        else:
            return "Error: command is required"

        if not command:
            return "Error: command is required"
        workdir_path = Path(workdir)
        if not workdir_path.exists():
            return f"Error: working directory does not exist: {workdir}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(workdir_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if not output.strip():
                output = "(no output)"
            return f"exit_code={result.returncode}\n{output}"
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s: {command}"
        except Exception as e:
            return f"Error executing command: {e}"

    return Tool(
        name="bash",
        description=textwrap.dedent("""\
            Execute a shell command in the project directory.
            Use for: running tests, builds, git commands, installing dependencies,
            checking file existence, listing directories, running linters.
            The working directory is the project root.
            Returns exit code and stdout/stderr.
        """).strip(),
        func=_bash,
    )


__all__ = ["create_bash_tool"]
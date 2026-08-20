from __future__ import annotations

import platform
import shutil
import subprocess
import textwrap
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

_SYSTEM = platform.system()

_BASH_EXE: str | None = None
if _SYSTEM == "Windows":
    _BASH_EXE = shutil.which("bash")


class BashInput(BaseModel):
    command: str = Field(description="Shell command to execute")


def _run_command(command: str, cwd: str, timeout: int) -> str:
    """Execute a shell command, using bash on Windows for POSIX compatibility."""
    if _SYSTEM == "Windows" and _BASH_EXE:
        result = subprocess.run(
            [_BASH_EXE, "-c", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    else:
        # shell=True required for shell pipeline support (|, &&, ;;).
        # Commands are sandboxed; user operates in controlled workspace.
        # nosec B602
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
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


def create_bash_tool(
    workdir: str,
    timeout: int = 120,
) -> StructuredTool:
    bash_exe_info = _BASH_EXE if _BASH_EXE else "fallback to cmd.exe"

    def _bash(command: str = "", **kwargs) -> str:
        cmd = kwargs.get("cmd", command)
        if cmd:
            command = cmd
        if not command:
            return "Error: command is required"
        workdir_path = Path(workdir)
        if not workdir_path.exists():
            return f"Error: working directory does not exist: {workdir}"

        try:
            return _run_command(command, str(workdir_path), timeout)
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout}s: {command}"
        except Exception as e:
            return f"Error executing command: {e}"

    return StructuredTool(
        name="bash",
        description=textwrap.dedent(f"""\
            Execute a shell command in the project directory.
            Shell: {_BASH_EXE if (_SYSTEM == "Windows" and _BASH_EXE) else "system default"}.
            Use for: running tests, builds, git commands, installing dependencies,
            checking file existence, listing directories, running linters.
            The working directory is the project root.
            Returns exit code and stdout/stderr.
        """).strip(),
        func=_bash,
        args_schema=BashInput,
    )


__all__ = ["BashInput", "create_bash_tool"]

"""F1.5 — H8a/H8b: opencode backend output handling.

- H8a: stdout is text mode (Popen encoding="utf-8") — lines are str, the old
  `.decode()` + AttributeError retry crashed the read loop.
- H8b: the output file was returned without validation against the stage
  schema; parse failure set `complete: True` and passed on. Now invalid
  parse/validation returns AgentResult(error=...) so the node can retry.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from eng_loop.tools.agent_runner import run_agent_via_opencode


class VerifyOutput(BaseModel):
    complete: bool = False
    verdict: str = ""


class FakeStdout:
    """Mimics text-mode proc.stdout: readline() returns str, "" at EOF."""

    def __init__(self, lines: list[str]):
        self._lines = list(lines)

    def readline(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        return ""


class FakeProc:
    def __init__(self, lines: list[str], on_wait=None, returncode: int = 0):
        self.stdout = FakeStdout(lines)
        self.returncode = returncode
        self._on_wait = on_wait
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.killed = True

    def wait(self) -> int:
        if self._on_wait:
            self._on_wait()
        return self.returncode


TEXT_EVENT = '{"type": "text", "part": {"content": "working on it"}}\n'


def _run_opencode(output_content: str | None, schema: type[BaseModel] | None = None) -> tuple:
    """Run run_agent_via_opencode with a fake Popen; returns (result, output_file_path)."""
    created: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def fake_mkstemp(suffix: str = "", prefix: str = ""):
        fd, path = real_mkstemp(suffix=suffix, prefix=prefix)
        created.append(path)
        return fd, path

    def on_wait() -> None:
        if output_content is not None:
            Path(created[0]).write_text(output_content, encoding="utf-8")

    fake_proc = FakeProc([TEXT_EVENT], on_wait=on_wait)

    with (
        patch("eng_loop.tools.agent_runner.tempfile.mkstemp", side_effect=fake_mkstemp),
        patch("eng_loop.tools.agent_runner.subprocess.Popen", return_value=fake_proc),
    ):
        result = run_agent_via_opencode(
            prompt="do the task",
            stage_id="verify",
            output_schema=schema,
            project_root=".",
            model_name="test-model",
            config={"hardware": {"stage_timeout_seconds": 30, "idle_timeout_seconds": 10}},
        )
    return result, created[0]


class TestOpencodeBackend:
    def test_valid_json_passes_schema(self) -> None:
        result, _ = _run_opencode('{"complete": true, "verdict": "PASS"}', schema=VerifyOutput)
        assert result.error is None
        assert result.data == {"complete": True, "verdict": "PASS"}

    def test_invalid_json_returns_error(self) -> None:
        result, _ = _run_opencode("this is not json {{{", schema=VerifyOutput)
        assert result.error is not None
        assert "failed to parse/validate" in result.error
        assert result.data.get("complete") is not True

    def test_schema_violation_returns_error(self) -> None:
        # Valid JSON, but "complete" is not coercible to bool → validation fails
        result, _ = _run_opencode('{"complete": "banana", "verdict": "PASS"}', schema=VerifyOutput)
        assert result.error is not None
        assert "failed to parse/validate" in result.error

    def test_empty_output_file_returns_error(self) -> None:
        # mkstemp creates the file; the agent never wrote it → empty content →
        # JSON parse failure must surface as an error (not complete=True).
        result, _ = _run_opencode(None, schema=VerifyOutput)
        assert result.error is not None
        assert "failed to parse/validate" in result.error

    def test_text_mode_stdout_no_attribute_error(self) -> None:
        """H8a: str lines from text-mode stdout must not raise AttributeError.

        The fake stdout yields real str lines (like Popen encoding="utf-8");
        a success result proves the read loop survived them.
        """
        result, _ = _run_opencode('{"complete": true}', schema=VerifyOutput)
        assert result.error is None

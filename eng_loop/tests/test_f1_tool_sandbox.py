"""F1.6 — C4: tool sandboxing.

File tools must contain paths to the project root; the bash tool must
screen commands. Tests use tmp_path as the sandbox root (NOT the CWD).
"""

from __future__ import annotations

from pathlib import Path

from eng_loop.tools.bash_tool import create_bash_tool
from eng_loop.tools.edit_tool import create_edit_tool
from eng_loop.tools.glob_tool import create_glob_tool
from eng_loop.tools.grep_tool import create_grep_tool
from eng_loop.tools.read_tool import create_read_tool
from eng_loop.tools.sandbox import build_sandbox, check_bash_command, check_path, resolve_in_root, sandbox_config
from eng_loop.tools.write_tool import create_write_tool


def _sb(root: Path, **overrides) -> dict:
    sb = {"enabled": True, "root": str(root), "allow_out_of_root": False}
    sb.update(overrides)
    return sb


class TestResolveInRoot:
    def test_relative_inside(self, tmp_path: Path) -> None:
        assert resolve_in_root("src/a.py", tmp_path) == tmp_path.resolve() / "src" / "a.py"

    def test_absolute_inside(self, tmp_path: Path) -> None:
        target = tmp_path / "x.txt"
        assert resolve_in_root(str(target), tmp_path) == target.resolve()

    def test_root_itself(self, tmp_path: Path) -> None:
        assert resolve_in_root(".", tmp_path) == tmp_path.resolve()

    def test_dotdot_escape(self, tmp_path: Path) -> None:
        assert resolve_in_root("../outside.txt", tmp_path) is None
        assert resolve_in_root("..", tmp_path) is None
        assert resolve_in_root("a/../../b", tmp_path) is None

    def test_absolute_outside(self, tmp_path: Path) -> None:
        assert resolve_in_root("/etc/passwd", tmp_path) is None


class TestSandboxConfig:
    def test_defaults(self) -> None:
        assert sandbox_config(None) == {"enabled": True, "allow_out_of_root": False}
        assert sandbox_config({}) == {"enabled": True, "allow_out_of_root": False}

    def test_explicit_overrides(self) -> None:
        cfg = {"agent": {"tools": {"sandbox": {"enabled": False, "allow_out_of_root": True}}}}
        assert sandbox_config(cfg) == {"enabled": False, "allow_out_of_root": True}

    def test_build_sandbox_disabled_returns_none(self) -> None:
        cfg = {"agent": {"tools": {"sandbox": {"enabled": False}}}}
        assert build_sandbox("/r", cfg) is None
        assert build_sandbox("/r", None) == {"enabled": True, "root": "/r", "allow_out_of_root": False}

    def test_check_path_no_sandbox_passthrough(self, tmp_path: Path) -> None:
        assert check_path("../outside", None) == Path("../outside")
        assert check_path("../outside", _sb(tmp_path, allow_out_of_root=True)) == Path("../outside")
        assert check_path("../outside", _sb(tmp_path, enabled=False)) == Path("../outside")


class TestReadTool:
    def test_inside_root_works(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        tool = create_read_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": "a.txt"})
        assert "hello" in out

    def test_dotdot_blocked(self, tmp_path: Path) -> None:
        (tmp_path.parent / "outside.txt").write_text("secret", encoding="utf-8")
        tool = create_read_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": "../outside.txt"})
        assert "outside the project root" in out
        assert "secret" not in out

    def test_absolute_outside_blocked(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "abs_outside.txt"
        outside.write_text("secret", encoding="utf-8")
        tool = create_read_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": str(outside)})
        assert "outside the project root" in out
        assert "secret" not in out

    def test_no_sandbox_keeps_legacy_behavior(self, tmp_path: Path) -> None:
        # Without a sandbox, relative paths resolve against CWD (legacy)
        tool = create_read_tool()
        out = tool.invoke({"file_path": "no_such_file_xyz.txt"})
        assert "not found" in out or "blocked" not in out


class TestWriteTool:
    def test_inside_root_writes(self, tmp_path: Path) -> None:
        tool = create_write_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": "new.txt", "content": "data"})
        assert "Wrote" in out
        assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "data"

    def test_outside_root_blocked_no_side_effect(self, tmp_path: Path) -> None:
        target = tmp_path.parent / "should_not_exist.txt"
        tool = create_write_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": "../should_not_exist.txt", "content": "x"})
        assert "outside the project root" in out
        assert not target.exists()

    def test_allow_out_of_root_writes(self, tmp_path: Path) -> None:
        tool = create_write_tool(sandbox=_sb(tmp_path, allow_out_of_root=True))
        out = tool.invoke({"file_path": "sub/ok.txt", "content": "x"})
        assert "Wrote" in out


class TestEditTool:
    def test_inside_root_edits(self, tmp_path: Path) -> None:
        (tmp_path / "f.py").write_text("a = 1\n", encoding="utf-8")
        tool = create_edit_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": "f.py", "old_string": "a = 1", "new_string": "a = 2"})
        assert "Edited" in out
        assert (tmp_path / "f.py").read_text(encoding="utf-8") == "a = 2\n"

    def test_outside_root_blocked(self, tmp_path: Path) -> None:
        target = tmp_path.parent / "victim.py"
        target.write_text("x = 1\n", encoding="utf-8")
        tool = create_edit_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"file_path": "../victim.py", "old_string": "x = 1", "new_string": "x = 2"})
        assert "outside the project root" in out
        assert target.read_text(encoding="utf-8") == "x = 1\n"


class TestGlobGrepTools:
    def test_glob_inside(self, tmp_path: Path) -> None:
        (tmp_path / "m.py").write_text("x", encoding="utf-8")
        tool = create_glob_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"pattern": "*.py", "path": "."})
        assert "m.py" in out

    def test_glob_base_outside_blocked(self, tmp_path: Path) -> None:
        tool = create_glob_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"pattern": "*", "path": ".."})
        assert "outside the project root" in out

    def test_glob_dotdot_pattern_filtered(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "escape_match.txt"
        outside.write_text("x", encoding="utf-8")
        tool = create_glob_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"pattern": "../*", "path": "."})
        assert "escape_match.txt" not in out

    def test_grep_inside(self, tmp_path: Path) -> None:
        (tmp_path / "f.txt").write_text("needle here\n", encoding="utf-8")
        tool = create_grep_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"pattern": "needle", "path": "."})
        assert "f.txt" in out

    def test_grep_base_outside_blocked(self, tmp_path: Path) -> None:
        tool = create_grep_tool(sandbox=_sb(tmp_path))
        out = tool.invoke({"pattern": "x", "path": ".."})
        assert "outside the project root" in out


class TestBashGuard:
    def test_benign_commands_pass(self, tmp_path: Path) -> None:
        tool = create_bash_tool(workdir=str(tmp_path), timeout=10, sandbox=_sb(tmp_path))
        out = tool.invoke({"command": "echo sandbox-ok"})
        assert "sandbox-ok" in out
        assert "BLOCKED" not in out

    def test_rm_rf_system_blocked_not_executed(self, tmp_path: Path) -> None:
        sentinel = tmp_path / "sentinel.txt"
        tool = create_bash_tool(workdir=str(tmp_path), timeout=10, sandbox=_sb(tmp_path))
        out = tool.invoke({"command": f"touch {sentinel} && rm -rf /"})
        assert "BLOCKED" in out
        assert not sentinel.exists()

    def test_rm_rf_home_blocked(self, tmp_path: Path) -> None:
        tool = create_bash_tool(workdir=str(tmp_path), timeout=10, sandbox=_sb(tmp_path))
        assert "BLOCKED" in tool.invoke({"command": "rm -rf ~"})
        assert "BLOCKED" in tool.invoke({"command": "rm -r -f /etc"})

    def test_legit_cleanup_allowed(self, tmp_path: Path) -> None:
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "art.bin").write_text("x", encoding="utf-8")
        tool = create_bash_tool(workdir=str(tmp_path), timeout=10, sandbox=_sb(tmp_path))
        out = tool.invoke({"command": "rm -rf ./build"})
        assert "BLOCKED" not in out
        if "exit_code=0" in out:
            assert not (tmp_path / "build").exists()

    def test_risk_keyword_blocked(self, tmp_path: Path) -> None:
        tool = create_bash_tool(workdir=str(tmp_path), timeout=10, sandbox=_sb(tmp_path))
        assert "BLOCKED" in tool.invoke({"command": "chmod 777 /etc/passwd"})
        assert "BLOCKED" in tool.invoke({"command": "drop database prod"})

    def test_disabled_sandbox_bypasses_guard(self, tmp_path: Path) -> None:
        tool = create_bash_tool(workdir=str(tmp_path), timeout=10, sandbox={"enabled": False, "root": str(tmp_path)})
        out = tool.invoke({"command": "echo credentials"})
        assert "credentials" in out
        assert "BLOCKED" not in out

    def test_check_bash_command_none_sandbox(self) -> None:
        assert check_bash_command("rm -rf /", None) is None
        assert check_bash_command("rm -rf /", {"enabled": False, "root": "/x"}) is None

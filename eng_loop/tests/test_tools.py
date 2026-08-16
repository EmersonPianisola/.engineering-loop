from __future__ import annotations

"""Tests for LLM tool implementations: read, write, edit, bash, glob, grep."""

import os
import tempfile
from pathlib import Path

from eng_loop.tools.agent_tools import (
    STAGE_TOOLS,
    get_essence_tools,
    get_tools_for_stage,
)
from eng_loop.tools.bash_tool import create_bash_tool
from eng_loop.tools.edit_tool import create_edit_tool
from eng_loop.tools.glob_tool import create_glob_tool
from eng_loop.tools.grep_tool import create_grep_tool
from eng_loop.tools.read_tool import create_read_tool
from eng_loop.tools.write_tool import create_write_tool

# ============================================================
# READ TOOL
# ============================================================


class TestReadTool:
    def test_read_file(self):
        tool = create_read_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("line1\nline2\nline3", encoding="utf-8")
            result = tool.func(str(p))
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert "(3 total lines" in result

    def test_read_file_with_offset(self):
        tool = create_read_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("\n".join(f"line{i}" for i in range(1, 11)), encoding="utf-8")
            result = tool.func(str(p), offset=5, limit=3)
        assert "line5" in result
        assert "line6" in result
        assert "line7" in result
        assert "line1" not in result

    def test_read_file_pagination(self):
        tool = create_read_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("\n".join(f"line{i}" for i in range(1, 101)), encoding="utf-8")
            result = tool.func(str(p), offset=1, limit=50)
        assert "more lines" in result
        assert "offset=51" in result

    def test_read_directory(self):
        tool = create_read_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a", encoding="utf-8")
            (Path(tmp) / "b.txt").write_text("b", encoding="utf-8")
            (Path(tmp) / "sub").mkdir()
            result = tool.func(tmp)
        assert "a.txt" in result
        assert "b.txt" in result
        assert "sub/" in result

    def test_read_nonexistent(self):
        tool = create_read_tool()
        result = tool.func("/nonexistent/path/file.txt")
        assert "Error" in result
        assert "not found" in result

    def test_read_long_lines_truncated(self):
        tool = create_read_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("x" * 3000, encoding="utf-8")
            result = tool.func(str(p))
        assert "1: xxx" in result
        assert len(result.split("\n")[1]) <= 2000 + 5

    def test_read_tool_metadata(self):
        tool = create_read_tool()
        assert tool.name == "read"
        assert "Read a file" in tool.description


# ============================================================
# WRITE TOOL
# ============================================================


class TestWriteTool:
    def test_write_file(self):
        tool = create_write_tool()
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = tool.func("test.txt", "hello world\nline2")
            finally:
                os.chdir(old_cwd)
            assert "Wrote" in result
            assert Path(tmp, "test.txt").read_text(encoding="utf-8") == "hello world\nline2"

    def test_write_creates_parent_dirs(self):
        tool = create_write_tool()
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                result = tool.func("a/b/c/test.txt", "content")
            finally:
                os.chdir(old_cwd)
            assert "Wrote" in result
            assert Path(tmp, "a/b/c/test.txt").exists()

    def test_write_overwrites(self):
        tool = create_write_tool()
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                tool.func("test.txt", "original")
                tool.func("test.txt", "replaced")
            finally:
                os.chdir(old_cwd)
            assert Path(tmp, "test.txt").read_text(encoding="utf-8") == "replaced"

    def test_write_tool_metadata(self):
        tool = create_write_tool()
        assert tool.name == "write"
        assert "Write content" in tool.description


# ============================================================
# EDIT TOOL
# ============================================================


class TestEditTool:
    def test_edit_replaces_string(self):
        tool = create_edit_tool()
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            os.chdir(tmp)
            try:
                Path("test.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
                result = tool.func("test.py", "return 1", "return 2")
            finally:
                os.chdir(old_cwd)
            assert "Edited" in result
            assert "return 2" in Path(tmp, "test.py").read_text(encoding="utf-8")

    def test_edit_file_not_found(self):
        tool = create_edit_tool()
        result = tool.func("/nonexistent/file.py", "old", "new")
        assert "Error" in result
        assert "not found" in result

    def test_edit_old_string_not_found(self):
        tool = create_edit_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = str(Path(tmp) / "test.py")
            Path(p).write_text("hello", encoding="utf-8")
            result = tool.func(p, "goodbye", "new")
        assert "Error" in result
        assert "not found" in result

    def test_edit_multiple_occurrences(self):
        tool = create_edit_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = str(Path(tmp) / "test.py")
            Path(p).write_text("foo\nfoo\nfoo", encoding="utf-8")
            result = tool.func(p, "foo", "bar")
        assert "Error" in result
        assert "3 times" in result

    def test_edit_identical_strings(self):
        tool = create_edit_tool()
        with tempfile.TemporaryDirectory() as tmp:
            p = str(Path(tmp) / "test.py")
            Path(p).write_text("hello", encoding="utf-8")
            result = tool.func(p, "hello", "hello")
        assert "Error" in result
        assert "identical" in result

    def test_edit_tool_metadata(self):
        tool = create_edit_tool()
        assert tool.name == "edit"
        assert "exact string replacement" in tool.description


# ============================================================
# BASH TOOL
# ============================================================


class TestBashTool:
    def test_bash_success(self):
        tool = create_bash_tool(workdir=".")
        result = tool.func("echo hello")
        assert "exit_code=0" in result
        assert "hello" in result

    def test_bash_failure(self):
        tool = create_bash_tool(workdir=".")
        result = tool.func("exit 1")
        assert "exit_code=1" in result

    def test_bash_nonexistent_workdir(self):
        tool = create_bash_tool(workdir="/nonexistent/dir")
        result = tool.func("echo hello")
        assert "Error" in result

    def test_bash_timeout(self):
        tool = create_bash_tool(workdir=".", timeout=1)
        result = tool.func("sleep 10")
        assert "timed out" in result

    def test_bash_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool = create_bash_tool(workdir=tmp)
            result = tool.func("pwd")
        assert "exit_code=0" in result

    def test_bash_no_output(self):
        tool = create_bash_tool(workdir=".")
        result = tool.func("true")
        assert "(no output)" in result

    def test_bash_stderr(self):
        tool = create_bash_tool(workdir=".")
        result = tool.func("echo error >&2")
        assert "[stderr]" in result

    def test_bash_tool_metadata(self):
        tool = create_bash_tool(workdir=".")
        assert tool.name == "bash"
        assert "shell command" in tool.description


# ============================================================
# GLOB TOOL
# ============================================================


class TestGlobTool:
    def test_glob_finds_files(self):
        tool = create_glob_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("a", encoding="utf-8")
            (Path(tmp) / "b.py").write_text("b", encoding="utf-8")
            (Path(tmp) / "c.txt").write_text("c", encoding="utf-8")
            result = tool.func("*.py", tmp)
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result
        assert "2 files" in result

    def test_glob_recursive(self):
        tool = create_glob_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "a.py").write_text("a", encoding="utf-8")
            result = tool.func("**/*.py", tmp)
        assert "a.py" in result

    def test_glob_no_matches(self):
        tool = create_glob_tool()
        with tempfile.TemporaryDirectory() as tmp:
            result = tool.func("*.xyz", tmp)
        assert "No files" in result

    def test_glob_nonexistent_directory(self):
        tool = create_glob_tool()
        result = tool.func("*.py", "/nonexistent")
        assert "Error" in result

    def test_glob_many_files(self):
        tool = create_glob_tool()
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(250):
                (Path(tmp) / f"file{i}.py").write_text("", encoding="utf-8")
            result = tool.func("*.py", tmp)
        assert "250 files" in result
        assert "and 50 more" in result

    def test_glob_tool_metadata(self):
        tool = create_glob_tool()
        assert tool.name == "glob"
        assert "glob" in tool.description


# ============================================================
# GREP TOOL
# ============================================================


class TestGrepTool:
    def test_grep_finds_pattern(self):
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
            (Path(tmp) / "b.py").write_text("def world():\n    return 2\n", encoding="utf-8")
            result = tool.func("def ", tmp)
        assert "hello" in result
        assert "world" in result
        assert "2 matches" in result

    def test_grep_include_filter(self):
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("hello", encoding="utf-8")
            (Path(tmp) / "b.txt").write_text("hello", encoding="utf-8")
            result = tool.func("hello", tmp, "*.py")
        assert "a.py" in result
        assert "b.txt" not in result

    def test_grep_no_matches(self):
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("hello", encoding="utf-8")
            result = tool.func("goodbye", tmp)
        assert "No matches" in result

    def test_grep_invalid_regex(self):
        tool = create_grep_tool()
        result = tool.func("[invalid", ".")
        assert "Error" in result
        assert "invalid regex" in result

    def test_grep_skips_binary(self):
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "image.png").write_bytes(b"\x89PNG")
            (Path(tmp) / "a.py").write_text("hello", encoding="utf-8")
            result = tool.func("hello", tmp)
        assert "a.py" in result
        assert "image.png" not in result

    def test_grep_line_numbers(self):
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("line1\nhello\nline3", encoding="utf-8")
            result = tool.func("hello", tmp)
        assert ":2:" in result

    def test_grep_tool_metadata(self):
        tool = create_grep_tool()
        assert tool.name == "grep"
        assert "regular expressions" in tool.description


# ============================================================
# STAGE TOOLS CONFIGURATION
# ============================================================


class TestStageTools:
    def test_impl_code_has_full_toolkit(self):
        assert STAGE_TOOLS["impl.code"] == ["read", "write", "edit", "bash", "glob", "grep"]

    def test_init_has_readonly_tools(self):
        assert "write" not in STAGE_TOOLS["init"]
        assert "edit" not in STAGE_TOOLS["init"]
        assert "bash" not in STAGE_TOOLS["init"]

    def test_verify_has_bash(self):
        assert "bash" in STAGE_TOOLS["verify"]

    def test_deploy_has_bash(self):
        assert "bash" in STAGE_TOOLS["deploy.prepare"]

    def test_get_tools_returns_correct_count(self):
        tools = get_tools_for_stage("impl.code", {"project_root": "."})
        assert len(tools) == 6

    def test_get_tools_readonly(self):
        tools = get_tools_for_stage("init", {"project_root": "."})
        names = [t.name for t in tools]
        assert "read" in names
        assert "glob" in names
        assert "write" not in names

    def test_get_essence_tools(self):
        tools = get_essence_tools({"project_root": "."})
        names = [t.name for t in tools]
        assert names == ["read", "glob"]

    def test_get_tools_unknown_stage_defaults_to_read(self):
        tools = get_tools_for_stage("unknown.stage", {"project_root": "."})
        names = [t.name for t in tools]
        assert "read" in names

    def test_all_stages_have_tool_definitions(self):
        from eng_loop.state import STAGE_ORDER

        for stage_id in STAGE_ORDER:
            assert stage_id in STAGE_TOOLS, f"Missing tools for {stage_id}"

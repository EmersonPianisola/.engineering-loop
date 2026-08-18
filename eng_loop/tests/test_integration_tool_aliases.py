from __future__ import annotations

"""Integration tests for tool parameter aliases.

Validates that all tools accept both snake_case and camelCase parameter names.
Tools use **kwargs internally to support both conventions.
"""

import os
import tempfile
from pathlib import Path

from eng_loop.tools.bash_tool import create_bash_tool
from eng_loop.tools.edit_tool import create_edit_tool
from eng_loop.tools.glob_tool import create_glob_tool
from eng_loop.tools.grep_tool import create_grep_tool
from eng_loop.tools.read_tool import create_read_tool
from eng_loop.tools.write_tool import create_write_tool


class TestReadToolAliases:
    def test_positional_call_via_kwargs(self):
        """Tool accepts file_path as keyword."""
        tool = create_read_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello")
            f.flush()
            result = tool.func(file_path=f.name)
        assert "hello" in result
        os.unlink(f.name)

    def test_camel_case_filepath(self):
        """Tool accepts filePath as keyword."""
        tool = create_read_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello")
            f.flush()
            result = tool.func(filePath=f.name)
        assert "hello" in result
        os.unlink(f.name)

    def test_directory_listing(self):
        """Tool can list directories."""
        tool = create_read_tool()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_text("a")
            result = tool.func(file_path=tmp)
        assert "a.txt" in result

    def test_missing_path_error(self):
        """Empty path returns error, not crash."""
        tool = create_read_tool()
        result = tool.func()
        assert "Error" in result

    def test_nonexistent_path_error(self):
        """Nonexistent path returns error."""
        tool = create_read_tool()
        result = tool.func(file_path="/nonexistent/file.txt")
        assert "Error" in result

    def test_offset_and_limit(self):
        """offset and limit work correctly."""
        tool = create_read_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("\n".join(f"line{i}" for i in range(1, 11)))
            f.flush()
            result = tool.func(file_path=f.name, offset=5, limit=3)
        assert "line5" in result
        assert "line7" in result
        assert "line1" not in result
        os.unlink(f.name)


class TestWriteToolAliases:
    def test_snake_case_write(self):
        """Tool accepts file_path as keyword."""
        tool = create_write_tool()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.close()
            result = tool.func(file_path=f.name, content="hello")
        assert "Wrote" in result
        assert Path(f.name).read_text(encoding="utf-8") == "hello"
        os.unlink(f.name)

    def test_camel_case_filepath(self):
        """Tool accepts filePath as keyword."""
        tool = create_write_tool()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.close()
            result = tool.func(filePath=f.name, content="hello")
        assert "Wrote" in result
        os.unlink(f.name)

    def test_creates_parent_dirs(self):
        """Parent directories are created automatically."""
        tool = create_write_tool()
        with tempfile.TemporaryDirectory() as tmp:
            rel_path = "a/b/c/test.txt"
            import os as _os

            old_cwd = _os.getcwd()
            _os.chdir(tmp)
            try:
                result = tool.func(file_path=rel_path, content="content")
            finally:
                _os.chdir(old_cwd)
            assert "Wrote" in result
            assert Path(tmp, rel_path).exists()

    def test_missing_path_error(self):
        """Empty path returns error."""
        tool = create_write_tool()
        result = tool.func(content="hello")
        assert "Error" in result

    def test_missing_content_error(self):
        """Empty content returns error."""
        tool = create_write_tool()
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.close()
            result = tool.func(file_path=f.name)
        assert "Error" in result
        os.unlink(f.name)


class TestGlobToolAliases:
    def test_glob_files(self):
        """Tool finds files by pattern."""
        tool = create_glob_tool()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.py").write_text("a")
            Path(tmp, "b.py").write_text("b")
            result = tool.func(pattern="**/*.py", path=tmp)
        assert "a.py" in result
        assert "b.py" in result

    def test_no_matches(self):
        """No matches returns informative message."""
        tool = create_glob_tool()
        with tempfile.TemporaryDirectory() as tmp:
            result = tool.func(pattern="**/*.py", path=tmp)
        assert "No files" in result

    def test_missing_pattern_error(self):
        """Empty pattern returns error."""
        tool = create_glob_tool()
        result = tool.func()
        assert "Error" in result


class TestGrepToolAliases:
    def test_grep_matches(self):
        """Tool finds matching content."""
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "test.py").write_text("def hello():\n    pass")
            result = tool.func(pattern="hello", path=tmp, include="*.py")
        assert "hello" in result

    def test_no_matches(self):
        """No matches returns informative message."""
        tool = create_grep_tool()
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "test.py").write_text("def hello():\n    pass")
            result = tool.func(pattern="nonexistent", path=tmp, include="*.py")
        assert "No matches" in result

    def test_missing_pattern_error(self):
        """Empty pattern returns error."""
        tool = create_grep_tool()
        result = tool.func()
        assert "Error" in result


class TestEditToolAliases:
    def test_snake_case_edit(self):
        """Tool accepts snake_case parameters."""
        tool = create_edit_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            result = tool.func(file_path=f.name, old_string="hello", new_string="goodbye")
        assert "Edited" in result
        assert Path(f.name).read_text(encoding="utf-8") == "goodbye world"
        os.unlink(f.name)

    def test_camel_case_edit(self):
        """Tool accepts camelCase parameters."""
        tool = create_edit_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            result = tool.func(filePath=f.name, oldString="hello", newString="goodbye")
        assert "Edited" in result
        assert Path(f.name).read_text(encoding="utf-8") == "goodbye world"
        os.unlink(f.name)

    def test_missing_path_error(self):
        """Empty path returns error."""
        tool = create_edit_tool()
        result = tool.func(old_string="a", new_string="b")
        assert "Error" in result

    def test_missing_old_string_error(self):
        """Empty old_string returns error."""
        tool = create_edit_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello")
            f.flush()
            result = tool.func(file_path=f.name, new_string="b")
        assert "Error" in result
        os.unlink(f.name)

    def test_identical_strings_error(self):
        """Identical old and new returns error."""
        tool = create_edit_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello")
            f.flush()
            result = tool.func(file_path=f.name, old_string="hello", new_string="hello")
        assert "identical" in result
        os.unlink(f.name)

    def test_not_found_error(self):
        """Not found returns context."""
        tool = create_edit_tool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            result = tool.func(file_path=f.name, old_string="nonexistent", new_string="replacement")
        assert "not found" in result
        os.unlink(f.name)


class TestBashToolAliases:
    def test_command_keyword(self):
        """Tool accepts command keyword."""
        tool = create_bash_tool(workdir="/tmp")
        result = tool.func(command="echo hello")
        assert "hello" in result

    def test_cmd_keyword(self):
        """Tool accepts cmd keyword alias."""
        tool = create_bash_tool(workdir="/tmp")
        result = tool.func(cmd="echo hello")
        assert "hello" in result

    def test_missing_command_error(self):
        """Empty command returns error."""
        tool = create_bash_tool(workdir="/tmp")
        result = tool.func()
        assert "Error" in result

    def test_exit_code_in_output(self):
        """Exit code is included in output."""
        tool = create_bash_tool(workdir="/tmp")
        result = tool.func(command="echo test")
        assert "exit_code=0" in result

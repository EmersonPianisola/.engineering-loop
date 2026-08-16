"""Tests for ProjectMap and ToolResultCache — context optimization layer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from eng_loop.tools.agent_runner import CACHABLE_TOOLS, INVALIDATING_TOOLS, ToolResultCache
from eng_loop.tools.project_map import ProjectMap

# ============================================================
# PROJECT MAP TESTS
# ============================================================


class TestProjectMapBuild:
    def test_build_on_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pm = ProjectMap.build(tmp)
        assert pm.tree == "" or "(empty" in pm.tree
        assert pm.stats["total_files"] == 0

    def test_build_detects_python_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "main.py").write_text("print('hi')", encoding="utf-8")
            (Path(tmp) / "utils.py").write_text("def f(): pass", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        assert pm.languages.get("python", 0) >= 2
        assert pm.stats["total_files"] >= 2

    def test_build_detects_typescript_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "index.ts").write_text("console.log(1)", encoding="utf-8")
            (Path(tmp) / "src" / "App.tsx").write_text("export default {}", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        assert pm.languages.get("typescript", 0) >= 2

    def test_build_detects_config_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text("{}", encoding="utf-8")
            (Path(tmp) / "tsconfig.json").write_text("{}", encoding="utf-8")
            (Path(tmp) / "pyproject.toml").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        assert "package.json" in pm.config_files
        assert "tsconfig.json" in pm.config_files
        assert "pyproject.toml" in pm.config_files

    def test_build_detects_entry_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "index.ts").write_text("", encoding="utf-8")
            (Path(tmp) / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        assert "src/index.ts" in pm.entry_points
        assert "main.py" in pm.entry_points

    def test_build_detects_test_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            (Path(tmp) / "e2e").mkdir()
            pm = ProjectMap.build(tmp)
        assert any("tests/" in d for d in pm.test_dirs)
        assert any("e2e/" in d for d in pm.test_dirs)

    def test_build_excludes_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "node_modules").mkdir()
            (Path(tmp) / "node_modules" / "pkg").mkdir()
            (Path(tmp) / "node_modules" / "pkg" / "index.js").write_text("", encoding="utf-8")
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "index.ts").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        # node_modules should not appear in the tree
        assert "node_modules" not in pm.tree
        # Only the src file should be counted
        assert pm.stats["total_files"] == 1

    def test_build_excludes_hidden_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".git").mkdir()
            (Path(tmp) / ".git" / "config").write_text("", encoding="utf-8")
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "index.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        assert ".git" not in pm.tree
        assert pm.stats["total_files"] == 1

    def test_build_tree_has_ascii_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        # All chars should be ASCII (no box-drawing characters)
        for ch in pm.tree:
            assert ord(ch) < 128, f"Non-ASCII char in tree: {ch!r}"

    def test_to_prompt_section_includes_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        section = pm.to_prompt_section()
        assert "## PROJECT MAP" in section
        assert "### File Structure" in section


class TestProjectMapSerialization:
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src").mkdir()
            (Path(tmp) / "src" / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        data = pm.to_dict()
        pm2 = ProjectMap.from_dict(data)
        assert pm2.tree == pm.tree
        assert pm2.languages == pm.languages
        assert pm2.stats == pm.stats
        assert pm2.entry_points == pm.entry_points

    def test_from_empty_dict(self):
        pm = ProjectMap.from_dict({})
        assert pm.tree == ""
        assert pm.stats == {}

    def test_to_dict_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        data = pm.to_dict()
        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0


class TestProjectMapPromptHelpers:
    def test_get_project_map_returns_none_when_absent(self):
        from eng_loop.tools.project_map import get_project_map

        assert get_project_map({}) is None

    def test_get_project_map_returns_map_when_present(self):
        from eng_loop.tools.project_map import ProjectMap, get_project_map

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        state = {"project_map": pm.to_dict()}
        result = get_project_map(state)
        assert result is not None
        assert result.stats["total_files"] >= 1

    def test_get_prompt_section_empty_when_no_map(self):
        from eng_loop.tools.project_map import get_project_map_prompt_section

        assert get_project_map_prompt_section({}) == ""

    def test_get_prompt_section_nonempty_when_map_exists(self):
        from eng_loop.tools.project_map import ProjectMap, get_project_map_prompt_section

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "main.py").write_text("", encoding="utf-8")
            pm = ProjectMap.build(tmp)
        state = {"project_map": pm.to_dict()}
        section = get_project_map_prompt_section(state)
        assert "## PROJECT MAP" in section


# ============================================================
# TOOL RESULT CACHE TESTS
# ============================================================


class TestToolResultCacheBasics:
    def test_caches_read_result(self):
        cache = ToolResultCache()
        args = {"file_path": "src/main.py", "offset": 1, "limit": 50}
        assert cache.get("read", args) is None
        cache.set("read", args, "line1\nline2")
        assert cache.get("read", args) == "line1\nline2"

    def test_different_args_different_cache_entries(self):
        cache = ToolResultCache()
        args1 = {"file_path": "src/main.py"}
        args2 = {"file_path": "src/utils.py"}
        cache.set("read", args1, "content1")
        cache.set("read", args2, "content2")
        assert cache.get("read", args1) == "content1"
        assert cache.get("read", args2) == "content2"

    def test_different_tools_different_cache_entries(self):
        cache = ToolResultCache()
        args = {"pattern": "*.py"}
        cache.set("glob", args, "src/main.py")
        assert cache.get("glob", args) == "src/main.py"
        assert cache.get("read", args) is None

    def test_does_not_cache_non_cachable_tools(self):
        cache = ToolResultCache()
        args = {"file_path": "src/main.py", "content": "new"}
        cache.set("write", args, "wrote 10 bytes")
        assert cache.get("write", args) is None  # Not cachable

    def test_stats_tracking(self):
        cache = ToolResultCache()
        args = {"file_path": "src/main.py"}
        cache.set("read", args, "content")
        cache.get("read", args)  # hit
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1


class TestToolResultCacheInvalidation:
    def test_edit_invalidates_read_cache_for_same_file(self):
        cache = ToolResultCache()
        read_args = {"file_path": "src/main.py", "offset": 1}
        cache.set("read", read_args, "old content")
        assert cache.get("read", read_args) == "old content"

        # Edit the file — should invalidate the read cache
        edit_args = {"file_path": "src/main.py", "old_string": "a", "new_string": "b"}
        cache.invalidate_on_mutation("edit", edit_args)

        assert cache.get("read", read_args) is None  # Invalidated

    def test_write_invalidates_read_cache_for_same_file(self):
        cache = ToolResultCache()
        read_args = {"file_path": "src/main.py"}
        cache.set("read", read_args, "old")
        write_args = {"file_path": "src/main.py", "content": "new"}
        cache.invalidate_on_mutation("write", write_args)
        assert cache.get("read", read_args) is None

    def test_bash_invalidates_all_cache(self):
        cache = ToolResultCache()
        cache.set("read", {"file_path": "a.py"}, "a")
        cache.set("glob", {"pattern": "*.py"}, "b")
        cache.set("grep", {"pattern": "def "}, "c")
        cache.invalidate_on_mutation("bash", {"command": "npm test"})
        assert cache.get("read", {"file_path": "a.py"}) is None
        assert cache.get("glob", {"pattern": "*.py"}) is None
        assert cache.get("grep", {"pattern": "def "}) is None

    def test_edit_one_file_preserves_other_files_cache(self):
        cache = ToolResultCache()
        cache.set("read", {"file_path": "src/a.py"}, "content_a")
        cache.set("read", {"file_path": "src/b.py"}, "content_b")
        cache.invalidate_on_mutation("edit", {"file_path": "src/a.py", "old_string": "x", "new_string": "y"})
        # a.py should be invalidated
        assert cache.get("read", {"file_path": "src/a.py"}) is None
        # b.py should still be cached
        assert cache.get("read", {"file_path": "src/b.py"}) == "content_b"

    def test_non_invalidating_tool_no_effect(self):
        cache = ToolResultCache()
        cache.set("read", {"file_path": "src/main.py"}, "content")
        cache.invalidate_on_mutation("read", {"file_path": "src/main.py"})  # read is not invalidating
        assert cache.get("read", {"file_path": "src/main.py"}) == "content"


class TestToolCacheConstants:
    def test_cachable_tools(self):
        assert "read" in CACHABLE_TOOLS
        assert "glob" in CACHABLE_TOOLS
        assert "grep" in CACHABLE_TOOLS
        assert "write" not in CACHABLE_TOOLS
        assert "edit" not in CACHABLE_TOOLS
        assert "bash" not in CACHABLE_TOOLS

    def test_invalidating_tools(self):
        assert "write" in INVALIDATING_TOOLS
        assert "edit" in INVALIDATING_TOOLS
        assert "bash" in INVALIDATING_TOOLS
        assert "read" not in INVALIDATING_TOOLS
        assert "glob" not in INVALIDATING_TOOLS

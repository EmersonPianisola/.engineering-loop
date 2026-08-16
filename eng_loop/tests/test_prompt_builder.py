from __future__ import annotations

"""Tests for prompt builder, FileCache, SystemPrefix, StageContext, PromptBuilder."""

import tempfile
import time
from pathlib import Path

from eng_loop.tools.prompt_builder import (
    ARTIFECT_KEY_MAP,
    STAGE_ARTIFACT_INCLUDES,
    FileCache,
    PromptBuilder,
    StageContext,
    SystemPrefix,
    clear_file_cache,
    load_cached_markdown,
)

# ============================================================
# FILE CACHE
# ============================================================


class TestFileCache:
    def test_get_put(self):
        cache = FileCache()
        cache.put("/path/file.md", "content")
        assert cache.get("/path/file.md") == "content"

    def test_get_missing(self):
        cache = FileCache()
        assert cache.get("/nonexistent") is None

    def test_ttl_expires(self):
        cache = FileCache(ttl_seconds=0)
        cache.put("/path/file.md", "content")
        time.sleep(0.01)
        assert cache.get("/path/file.md") is None

    def test_max_entries_evicts(self):
        cache = FileCache(max_entries=2)
        cache.put("/a.md", "a")
        cache.put("/b.md", "b")
        cache.put("/c.md", "c")
        assert len(cache) == 2
        assert cache.get("/c.md") == "c"

    def test_clear(self):
        cache = FileCache()
        cache.put("/a.md", "a")
        cache.clear()
        assert len(cache) == 0

    def test_load_cached_markdown(self):
        clear_file_cache()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.md"
            p.write_text("# Hello", encoding="utf-8")
            content = load_cached_markdown(str(p))
        assert content == "# Hello"

    def test_load_cached_markdown_cached(self):
        clear_file_cache()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.md"
            p.write_text("# Hello", encoding="utf-8")
            content1 = load_cached_markdown(str(p))
            content2 = load_cached_markdown(str(p))
        assert content1 == content2

    def test_load_cached_markdown_nonexistent(self):
        clear_file_cache()
        content = load_cached_markdown("/nonexistent/file.md")
        assert content == ""


# ============================================================
# ARTIFACT CONFIGURATION
# ============================================================


class TestArtifactConfig:
    def test_all_stages_have_artifact_config(self):
        from eng_loop.state import STAGE_ORDER

        for stage_id in STAGE_ORDER:
            assert stage_id in STAGE_ARTIFACT_INCLUDES, f"Missing artifact config for {stage_id}"

    def test_impl_code_includes_blueprint(self):
        assert "blueprint" in STAGE_ARTIFACT_INCLUDES["impl.code"]

    def test_verify_includes_blueprint(self):
        assert "blueprint" in STAGE_ARTIFACT_INCLUDES["verify"]

    def test_artifact_key_map_complete(self):
        assert "blueprint" in ARTIFECT_KEY_MAP
        assert "architecture" in ARTIFECT_KEY_MAP
        assert "lessons" in ARTIFECT_KEY_MAP


# ============================================================
# SYSTEM PREFIX
# ============================================================


class TestSystemPrefix:
    def test_build_with_work_item(self):
        state = {"work_item": "Fix the bug"}
        paths = {"project_root": "/project"}
        config = {}
        prefix = SystemPrefix(state, paths, config)
        result = prefix.build()
        assert "Fix the bug" in result
        assert "## WORK ITEM" in result

    def test_build_with_complexity(self):
        state = {"work_item": "Task", "complexity": "large"}
        paths = {}
        config = {}
        prefix = SystemPrefix(state, paths, config)
        result = prefix.build()
        assert "## COMPLEXITY" in result
        assert "large" in result

    def test_build_with_ui_project(self):
        state = {"work_item": "Task", "ui_project": True}
        paths = {}
        config = {}
        prefix = SystemPrefix(state, paths, config)
        result = prefix.build()
        assert "## UI PROJECT" in result

    def test_build_with_decisions(self):
        state = {"work_item": "Task", "decisions": ["AD-001: Use React"]}
        paths = {}
        config = {}
        prefix = SystemPrefix(state, paths, config)
        result = prefix.build()
        assert "AD-001" in result

    def test_caching(self):
        state = {"work_item": "Task"}
        paths = {}
        config = {}
        prefix = SystemPrefix(state, paths, config)
        r1 = prefix.build()
        r2 = prefix.build()
        assert r1 == r2


# ============================================================
# STAGE CONTEXT
# ============================================================


class TestStageContext:
    def test_build_with_role(self):
        ctx = StageContext(
            stage_id="impl.code",
            state={},
            paths={},
            config={},
            role_description="Implementation agent",
        )
        result = ctx.build()
        assert "Implementation agent" in result

    def test_build_with_procedure(self):
        ctx = StageContext(
            stage_id="impl.code",
            state={},
            paths={},
            config={},
            stage_proc="Do TDD",
        )
        result = ctx.build()
        assert "## PROCEDURE" in result
        assert "Do TDD" in result

    def test_build_with_skill(self):
        ctx = StageContext(
            stage_id="impl.code",
            state={},
            paths={},
            config={},
            skill_content="Skill content here",
        )
        result = ctx.build()
        assert "## SKILL" in result

    def test_build_with_handoffs(self):
        state = {
            "handoffs": {
                "init": "Init completed successfully",
                "impl.design": "Blueprint created",
            }
        }
        ctx = StageContext(
            stage_id="impl.code",
            state=state,
            paths={},
            config={},
        )
        result = ctx.build()
        assert "## PRIOR STAGE HANDOFFS" in result

    def test_artifact_inline_vs_reference(self):
        state = {
            "stage_artifacts": {
                "impl.design": "Short blueprint content",
            }
        }
        ctx = StageContext(
            stage_id="impl.code",
            state=state,
            paths={"artifact_root": ""},
            config={},
            use_references=True,
        )
        result = ctx.build()
        assert "SHORT BLUEPRINT CONTENT" in result or "blueprint" in result.lower()


# ============================================================
# PROMPT BUILDER
# ============================================================


class TestPromptBuilder:
    def test_build_complete_prompt(self):
        state = {"work_item": "Add login feature", "complexity": "medium"}
        paths = {"project_root": "/project"}
        config = {}
        builder = PromptBuilder(state, paths, config)
        prompt = builder.build(
            stage_id="impl.code",
            role_description="Coder",
            stage_proc="Write tests first",
            instructions="Implement the feature",
        )
        assert "Add login feature" in prompt
        assert "Coder" in prompt
        assert "Write tests first" in prompt
        assert "Implement the feature" in prompt

    def test_build_with_skill_content(self):
        state = {"work_item": "Task"}
        paths = {}
        config = {}
        builder = PromptBuilder(state, paths, config)
        prompt = builder.build(
            stage_id="verify",
            skill_content="Verifier skill",
        )
        assert "Verifier skill" in prompt

    def test_build_with_extra_sections(self):
        state = {"work_item": "Task"}
        paths = {}
        config = {}
        builder = PromptBuilder(state, paths, config)
        prompt = builder.build(
            stage_id="impl.code",
            extra_sections="## CUSTOM\nExtra info",
        )
        assert "## CUSTOM" in prompt

    def test_get_system_prefix(self):
        state = {"work_item": "Task", "complexity": "small"}
        paths = {}
        config = {}
        builder = PromptBuilder(state, paths, config)
        prefix = builder.get_system_prefix()
        assert "Task" in prefix

    def test_get_stage_context(self):
        state = {"work_item": "Task"}
        paths = {}
        config = {}
        builder = PromptBuilder(state, paths, config)
        ctx = builder.get_stage_context(
            stage_id="impl.code",
            role_description="Agent",
        )
        assert "Agent" in ctx

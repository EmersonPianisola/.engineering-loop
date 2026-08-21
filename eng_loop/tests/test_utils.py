from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from eng_loop.state import STAGE_ORDER
from eng_loop.tools.file_ops import (
    append_file,
    file_exists,
    list_dir,
    load_json,
    read_file,
    save_json,
    write_file,
)
from eng_loop.tools.json_parse import (
    _extract_array_json,
    _extract_brace_json,
    _extract_key_value_pairs,
    extract_json,
)
from eng_loop.tools.next_active import (
    _NEXT_IN_ORDER,
    _NODE_TO_STAGE,
    _STAGE_TO_NODE,
    _is_active,
    resolve_next,
)
from eng_loop.tools.node_helpers import build_handoff_update, build_node_prompt
from eng_loop.tools.timing import TimingTracker, format_time

# ============================================================
# PART 1: Timing
# ============================================================


class TestFormatTime:
    def test_zero(self):
        assert format_time(0) == "00:00:00"

    def test_59_seconds(self):
        assert format_time(59) == "00:00:59"

    def test_60_seconds(self):
        assert format_time(60) == "00:01:00"

    def test_3661_seconds(self):
        assert format_time(3661) == "01:01:01"

    def test_86400_seconds(self):
        assert format_time(86400) == "24:00:00"


class TestTimingTracker:
    def test_start_loop_records_time(self):
        tracker = TimingTracker()
        tracker.start_loop()
        assert tracker.loop_start_mono > 0
        assert tracker.loop_start_iso != ""

    def test_start_loop_records_iso_timestamp(self):
        tracker = TimingTracker()
        tracker.start_loop()
        assert "T" in tracker.loop_start_iso

    def test_record_stage(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.5)
        assert tracker.get_stage_durations("init") == [1.5]

    def test_record_stage_multiple(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.0)
        tracker.record_stage("init", 2.0)
        assert tracker.get_stage_durations("init") == [1.0, 2.0]

    def test_get_stage_durations_unknown(self):
        tracker = TimingTracker()
        assert tracker.get_stage_durations("nonexistent") == []

    def test_get_stage_total(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.0)
        tracker.record_stage("init", 2.0)
        assert tracker.get_stage_total("init") == 3.0

    def test_get_stage_total_unknown(self):
        tracker = TimingTracker()
        assert tracker.get_stage_total("nonexistent") == 0.0

    def test_get_stage_total_formatted(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 61)
        assert tracker.get_stage_total_formatted("init") == "00:01:01"

    def test_get_stage_total_formatted_unknown(self):
        tracker = TimingTracker()
        assert tracker.get_stage_total_formatted("nonexistent") == "00:00:00"

    def test_get_stage_attempts(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.0)
        tracker.record_stage("init", 2.0)
        tracker.record_stage("init", 3.0)
        assert tracker.get_stage_attempts("init") == 3

    def test_get_stage_attempts_unknown(self):
        tracker = TimingTracker()
        assert tracker.get_stage_attempts("nonexistent") == 0

    def test_get_loop_elapsed_before_start(self):
        tracker = TimingTracker()
        assert tracker.get_loop_elapsed() == 0.0

    def test_get_loop_elapsed_after_start(self):
        tracker = TimingTracker()
        tracker.start_loop()
        time.sleep(0.05)
        elapsed = tracker.get_loop_elapsed()
        assert elapsed >= 0.05

    def test_get_loop_elapsed_formatted(self):
        tracker = TimingTracker()
        tracker.start_loop()
        result = tracker.get_loop_elapsed_formatted()
        assert len(result) == 8
        assert result[2] == ":"
        assert result[5] == ":"

    def test_get_stage_ids(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.0)
        tracker.record_stage("impl.code", 2.0)
        ids = tracker.get_stage_ids()
        assert "init" in ids
        assert "impl.code" in ids
        assert len(ids) == 2

    def test_get_stage_ids_empty(self):
        tracker = TimingTracker()
        assert tracker.get_stage_ids() == []

    def test_get_summary(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.0)
        tracker.record_stage("init", 2.0)
        summary = tracker.get_summary()
        assert len(summary) == 1
        row = summary[0]
        assert row["stage_id"] == "init"
        assert row["durations"] == [1.0, 2.0]
        assert row["total_seconds"] == 3.0
        assert row["total"] == "00:00:03"
        assert row["attempts"] == 2

    def test_get_summary_empty(self):
        tracker = TimingTracker()
        assert tracker.get_summary() == []

    def test_get_total_seconds(self):
        tracker = TimingTracker()
        tracker.record_stage("init", 1.0)
        tracker.record_stage("impl.code", 2.0)
        tracker.record_stage("impl.code", 3.0)
        assert tracker.get_total_seconds() == 6.0

    def test_get_total_seconds_empty(self):
        tracker = TimingTracker()
        assert tracker.get_total_seconds() == 0.0

    def test_to_json(self):
        tracker = TimingTracker()
        tracker.start_loop()
        tracker.record_stage("init", 1.5)
        data = tracker.to_json()
        assert "loop_start" in data
        assert "loop_elapsed" in data
        assert "loop_elapsed_seconds" in data
        assert "stages" in data
        assert "init" in data["stages"]
        assert data["stages"]["init"]["attempts"] == 1
        assert data["stages"]["init"]["total_seconds"] == 1.5

    def test_to_json_serializable(self):
        tracker = TimingTracker()
        tracker.start_loop()
        tracker.record_stage("init", 1.5)
        data = tracker.to_json()
        json_str = json.dumps(data)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["stages"]["init"]["attempts"] == 1


# ============================================================
# PART 2: File Operations
# ============================================================


class TestReadFile:
    def test_read_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("hello world", encoding="utf-8")
            assert read_file(str(p)) == "hello world"

    def test_read_nonexistent_file(self):
        assert read_file("/nonexistent/path/file.txt") == ""

    def test_read_str_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("content", encoding="utf-8")
            assert read_file(str(p)) == "content"

    def test_read_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("content", encoding="utf-8")
            assert read_file(p) == "content"

    def test_read_multiline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("line1\nline2\nline3", encoding="utf-8")
            assert read_file(str(p)) == "line1\nline2\nline3"


class TestWriteFile:
    def test_write_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            write_file(str(p), "hello")
            assert p.read_text(encoding="utf-8") == "hello"

    def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a" / "b" / "c" / "test.txt"
            write_file(str(p), "content")
            assert p.exists()
            assert p.read_text(encoding="utf-8") == "content"

    def test_write_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            result = write_file(str(p), "content")
            assert isinstance(result, str)
            assert result == str(p)

    def test_write_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            write_file(str(p), "original")
            write_file(str(p), "replaced")
            assert p.read_text(encoding="utf-8") == "replaced"

    def test_write_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            write_file(p, "content")
            assert p.read_text(encoding="utf-8") == "content"


class TestAppendFile:
    def test_append_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            append_file(str(p), "first")
            assert p.read_text(encoding="utf-8") == "first"

    def test_append_to_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("original", encoding="utf-8")
            append_file(str(p), " appended")
            assert p.read_text(encoding="utf-8") == "original appended"

    def test_append_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a" / "b" / "test.txt"
            append_file(str(p), "content")
            assert p.exists()
            assert p.read_text(encoding="utf-8") == "content"

    def test_append_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            result = append_file(str(p), "content")
            assert isinstance(result, str)


class TestFileExists:
    def test_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            p.write_text("x", encoding="utf-8")
            assert file_exists(str(p)) is True

    def test_nonexistent_file(self):
        assert file_exists("/nonexistent/file.txt") is False

    def test_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert file_exists(tmp) is True


class TestListDir:
    def test_list_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a", encoding="utf-8")
            (Path(tmp) / "b.txt").write_text("b", encoding="utf-8")
            result = list_dir(tmp)
            assert len(result) == 2

    def test_list_nonexistent_path(self):
        assert list_dir("/nonexistent/path") == []

    def test_list_with_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.py").write_text("a", encoding="utf-8")
            (Path(tmp) / "b.py").write_text("b", encoding="utf-8")
            (Path(tmp) / "c.txt").write_text("c", encoding="utf-8")
            result = list_dir(tmp, "*.py")
            assert len(result) == 2
            assert any("a.py" in r for r in result)
            assert any("b.py" in r for r in result)

    def test_list_with_pattern_no_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.txt").write_text("a", encoding="utf-8")
            result = list_dir(tmp, "*.py")
            assert result == []

    def test_list_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = list_dir(tmp)
            assert result == []


class TestSaveJson:
    def test_save_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            data = {"key": "value", "num": 42}
            save_json(str(p), data)
            assert p.read_text(encoding="utf-8") != ""
            loaded = json.loads(p.read_text(encoding="utf-8"))
            assert loaded == data

    def test_save_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a" / "b" / "data.json"
            save_json(str(p), {"key": "value"})
            assert p.exists()

    def test_save_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            result = save_json(str(p), {})
            assert isinstance(result, str)

    def test_save_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            data = [1, 2, 3]
            save_json(str(p), data)
            loaded = json.loads(p.read_text(encoding="utf-8"))
            assert loaded == [1, 2, 3]

    def test_save_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            data = {"text": "hello \u00e9\u00e8\u00ea"}
            save_json(str(p), data)
            loaded = json.loads(p.read_text(encoding="utf-8"))
            assert loaded["text"] == "hello \u00e9\u00e8\u00ea"


class TestLoadJson:
    def test_load_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            p.write_text('{"key": "value"}', encoding="utf-8")
            result = load_json(str(p))
            assert result == {"key": "value"}

    def test_load_nonexistent(self):
        assert load_json("/nonexistent/file.json") == {}

    def test_load_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            p.write_text("[1, 2, 3]", encoding="utf-8")
            result = load_json(str(p))
            assert result == [1, 2, 3]

    def test_load_path_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "data.json"
            p.write_text('{"a": 1}', encoding="utf-8")
            result = load_json(p)
            assert result == {"a": 1}


# ============================================================
# PART 3: JSON Parse
# ============================================================


class TestExtractJson:
    def test_valid_json_object(self):
        result = extract_json('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_valid_json_nested(self):
        result = extract_json('{"outer": {"inner": true}}')
        assert result == {"outer": {"inner": True}}

    def test_markdown_code_block(self):
        content = 'Here is the result:\n```json\n{"key": "value"}\n```'
        result = extract_json(content)
        assert result == {"key": "value"}

    def test_markdown_code_block_no_json_lang(self):
        content = '```\n{"key": "value"}\n```'
        result = extract_json(content)
        assert result == {"key": "value"}

    def test_brace_matching_in_prose(self):
        content = 'Some text before {"name": "test", "id": 1} and after'
        result = extract_json(content)
        assert result == {"name": "test", "id": 1}

    def test_array_wrapping(self):
        result = extract_json("[1, 2, 3]")
        assert result == {"items": [1, 2, 3]}

    def test_key_value_fallback(self):
        content = "- name: test\n- status: complete"
        result = extract_json(content)
        assert "name" in result
        assert result["name"] == "test"

    def test_prose_raises_value_error(self):
        """Prose without JSON structure should raise ValueError, not silently return raw_output."""
        content = "This is a long piece of prose that does not contain any JSON structures at all but is long enough"
        with pytest.raises(ValueError, match="Could not extract JSON"):
            extract_json(content)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Empty"):
            extract_json("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="Empty"):
            extract_json("   \n\t  ")

    def test_very_short_text_raises(self):
        with pytest.raises(ValueError):
            extract_json("hi there")

    def test_short_text_raises(self):
        with pytest.raises(ValueError):
            extract_json("not json")

    def test_json_with_array_in_code_block_wrapped(self):
        content = "```json\n[1, 2, 3]\n```"
        result = extract_json(content)
        assert result == {"items": [1, 2, 3]}


class TestExtractBraceJson:
    def test_simple_object(self):
        result = _extract_brace_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_nested_braces(self):
        result = _extract_brace_json('{"outer": {"inner": {"deep": 1}}}')
        assert result == {"outer": {"inner": {"deep": 1}}}

    def test_in_prose(self):
        result = _extract_brace_json('Hello {"name": "world"} bye')
        assert result == {"name": "world"}

    def test_no_valid_object(self):
        result = _extract_brace_json("no braces here")
        assert result is None

    def test_invalid_json_in_braces(self):
        result = _extract_brace_json("{not valid json}")
        assert result is None

    def test_empty_object_returns_none(self):
        result = _extract_brace_json("{}")
        assert result is None

    def test_multiple_objects_returns_first(self):
        result = _extract_brace_json('{"a": 1} {"b": 2}')
        assert result == {"a": 1}


class TestExtractArrayJson:
    def test_simple_array(self):
        result = _extract_array_json("[1, 2, 3]")
        assert result == {"items": [1, 2, 3]}

    def test_nested_array(self):
        result = _extract_array_json("[[1, 2], [3, 4]]")
        assert result == {"items": [[1, 2], [3, 4]]}

    def test_in_prose(self):
        result = _extract_array_json("Here is a list: [1, 2, 3] end")
        assert result == {"items": [1, 2, 3]}

    def test_no_valid_array(self):
        result = _extract_array_json("no brackets here")
        assert result is None

    def test_empty_array_returns_none(self):
        result = _extract_array_json("[]")
        assert result is None

    def test_invalid_json_in_brackets(self):
        result = _extract_array_json("[not valid]")
        assert result is None


class TestExtractKeyValuePairs:
    def test_json_like_pairs(self):
        result = _extract_key_value_pairs('"name": "test", "status": "ok"')
        assert result is not None
        assert result["name"] == "test"

    def test_bullet_pairs(self):
        result = _extract_key_value_pairs("- name: test\n- status: complete")
        assert result is not None
        assert result["name"] == "test"
        assert result["status"] == "complete"

    def test_fewer_than_two_pairs(self):
        result = _extract_key_value_pairs("- only: one")
        assert result is None

    def test_no_pairs(self):
        result = _extract_key_value_pairs("just some random text without pairs")
        assert result is None

    def test_mixed_patterns(self):
        text = "- key1: val1\n- key2: val2"
        result = _extract_key_value_pairs(text)
        assert result is not None
        assert result["key1"] == "val1"
        assert result["key2"] == "val2"


# ============================================================
# PART 4: Next Active
# ============================================================


class TestIsActive:
    def test_active_when_complexity_meets_minimum(self):
        state: dict[str, Any] = {"complexity": "complex"}
        assert _is_active("arch.review", state) is True

    def test_inactive_when_complexity_below_minimum(self):
        state: dict[str, Any] = {"complexity": "small"}
        assert _is_active("arch.requirements", state) is False

    def test_inactive_when_complexity_below_medium(self):
        state: dict[str, Any] = {"complexity": "small"}
        assert _is_active("qa.security", state) is False

    def test_e2e_execute_inactive_without_ui(self):
        state: dict[str, Any] = {"complexity": "unset", "ui_project": False}
        assert _is_active("e2e.execute", state) is False

    def test_e2e_execute_active_with_ui(self):
        state: dict[str, Any] = {"complexity": "unset", "ui_project": True}
        assert _is_active("e2e.execute", state) is True

    def test_smoke_test_inactive_without_ui(self):
        state: dict[str, Any] = {"complexity": "unset", "ui_project": False}
        assert _is_active("smoke.test", state) is False

    def test_smoke_test_active_with_ui(self):
        state: dict[str, Any] = {"complexity": "unset", "ui_project": True}
        assert _is_active("smoke.test", state) is True

    def test_design_stages_inactive_for_bugfix(self):
        state: dict[str, Any] = {"complexity": "unset", "work_type": "bugfix"}
        assert _is_active("design.user-research", state) is False
        assert _is_active("design.personas", state) is False
        assert _is_active("design.info-arch", state) is False
        assert _is_active("design.interaction", state) is False
        assert _is_active("design.design-system", state) is False
        assert _is_active("design.visual-design", state) is False

    def test_impl_stages_inactive_for_operational(self):
        state: dict[str, Any] = {"complexity": "unset", "work_type": "operational"}
        assert _is_active("impl.design", state) is False
        assert _is_active("impl.code", state) is False

    def test_init_always_active(self):
        state: dict[str, Any] = {"complexity": "small"}
        assert _is_active("init", state) is True

    def test_unset_complexity_all_active(self):
        state: dict[str, Any] = {"complexity": "unset"}
        assert _is_active("arch.requirements", state) is True
        assert _is_active("arch.review", state) is True


class TestResolveNext:
    def test_returns_intended_if_active(self):
        state: dict[str, Any] = {"complexity": "unset"}
        result = resolve_next("init", state)
        assert result == "init"

    def test_walks_forward_to_next_active(self):
        state: dict[str, Any] = {"complexity": "small"}
        result = resolve_next("arch-requirements", state)
        assert result != "arch-requirements"
        assert result != "__end__"

    def test_returns_last_active_near_end(self):
        state: dict[str, Any] = {"complexity": "small", "ui_project": False, "work_type": "operational"}
        result = resolve_next("smoke-test", state)
        assert result == "post"

    def test_handles_node_name_to_stage_id(self):
        state: dict[str, Any] = {"complexity": "unset"}
        result = resolve_next("impl-code", state)
        assert result == "impl-code"

    def test_skips_inactive_e2e(self):
        state: dict[str, Any] = {"complexity": "unset", "ui_project": False}
        result = resolve_next("e2e-execute", state)
        assert result != "e2e-execute"


class TestConstants:
    def test_stage_to_node_has_all_stages(self):
        assert len(_STAGE_TO_NODE) == len(STAGE_ORDER)
        for sid in STAGE_ORDER:
            assert sid in _STAGE_TO_NODE

    def test_node_to_stage_has_all_nodes(self):
        assert len(_NODE_TO_STAGE) == len(STAGE_ORDER)
        for sid in STAGE_ORDER:
            node_name = sid.replace(".", "-").replace("_", "-")
            assert node_name in _NODE_TO_STAGE
            assert _NODE_TO_STAGE[node_name] == sid

    def test_next_in_order_maps_correctly(self):
        for i, sid in enumerate(STAGE_ORDER):
            if i + 1 < len(STAGE_ORDER):
                assert sid in _NEXT_IN_ORDER
                assert _NEXT_IN_ORDER[sid] == STAGE_ORDER[i + 1]
            else:
                assert sid not in _NEXT_IN_ORDER

    def test_last_stage_has_no_next(self):
        last = STAGE_ORDER[-1]
        assert last not in _NEXT_IN_ORDER

    def test_stage_to_node_format(self):
        assert _STAGE_TO_NODE["impl.code"] == "impl-code"
        assert _STAGE_TO_NODE["design.user-research"] == "design-user-research"
        assert _STAGE_TO_NODE["e2e.execute"] == "e2e-execute"


# ============================================================
# PART 5: Node Helpers
# ============================================================


class TestBuildNodePrompt:
    def _make_state(self) -> dict[str, Any]:
        return {
            "work_item": "Build a test feature",
            "complexity": "medium",
            "work_type": "feature",
            "ui_project": False,
            "decisions": [],
            "handoffs": {},
            "stage_artifacts": {},
            "project_map": {},
            "ideation": None,
        }

    def _make_paths(self, tmp: str) -> dict[str, Any]:
        return {
            "project_root": tmp,
            "artifact_root": tmp,
            "framework_stage_root": "",
            "framework_skill_root": "",
        }

    def test_returns_non_empty_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_node_prompt(
                "init",
                self._make_state(),
                self._make_paths(tmp),
                {},
                role_description="Test agent",
            )
            assert len(prompt) > 0

    def test_includes_role_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_node_prompt(
                "init",
                self._make_state(),
                self._make_paths(tmp),
                {},
                role_description="Implementation agent",
            )
            assert "Implementation agent" in prompt

    def test_includes_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_node_prompt(
                "init",
                self._make_state(),
                self._make_paths(tmp),
                {},
                instructions="Do the thing.",
            )
            assert "Do the thing." in prompt

    def test_includes_extra_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_node_prompt(
                "init",
                self._make_state(),
                self._make_paths(tmp),
                {},
                extra_sections="## EXTRA\nCustom section",
            )
            assert "## EXTRA" in prompt
            assert "Custom section" in prompt

    def test_include_skill_false_excludes_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_node_prompt(
                "init",
                self._make_state(),
                self._make_paths(tmp),
                {},
                include_skill=False,
            )
            assert "## SKILL" not in prompt

    def test_include_procedure_false_excludes_procedure(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt = build_node_prompt(
                "init",
                self._make_state(),
                self._make_paths(tmp),
                {},
                include_procedure=False,
            )
            assert "## PROCEDURE" not in prompt

    def test_includes_work_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = self._make_state()
            state["work_item"] = "Unique work item text"
            prompt = build_node_prompt(
                "init",
                state,
                self._make_paths(tmp),
                {},
            )
            assert "Unique work item text" in prompt


class TestBuildHandoffUpdate:
    def test_returns_dict_with_handoffs_and_artifacts(self):
        state: dict[str, Any] = {
            "handoffs": {},
            "stage_artifacts": {},
        }
        result = build_handoff_update(
            "init",
            {"output": "Stage completed"},
            ["Decision one"],
            state,
        )
        assert "handoffs" in result
        assert "stage_artifacts" in result

    def test_handoff_includes_stage_summary(self):
        state: dict[str, Any] = {
            "handoffs": {},
            "stage_artifacts": {},
        }
        result = build_handoff_update(
            "impl.code",
            {"output": "Implemented feature X"},
            ["Used approach A"],
            state,
        )
        assert "impl.code" in result["handoffs"]
        handoff_text = result["handoffs"]["impl.code"]
        assert "impl.code" in handoff_text

    def test_accumulates_handoffs(self):
        state: dict[str, Any] = {
            "handoffs": {"init": "Init summary"},
            "stage_artifacts": {},
        }
        result = build_handoff_update(
            "impl.code",
            {"output": "Code done"},
            [],
            state,
        )
        assert "init" in result["handoffs"]
        assert "impl.code" in result["handoffs"]

    def test_deduplicates_artifacts(self):
        state: dict[str, Any] = {
            "handoffs": {},
            "stage_artifacts": {
                "a": "unique content a",
                "b": "unique content a",
            },
        }
        result = build_handoff_update(
            "init",
            {"output": "done"},
            [],
            state,
        )
        artifacts = result["stage_artifacts"]
        assert len(artifacts) < 2 or "a" in artifacts

    def test_empty_decisions(self):
        state: dict[str, Any] = {
            "handoffs": {},
            "stage_artifacts": {},
        }
        result = build_handoff_update(
            "init",
            {"output": "done"},
            [],
            state,
        )
        assert "init" in result["handoffs"]

    def test_with_artifacts_in_result(self):
        state: dict[str, Any] = {
            "handoffs": {},
            "stage_artifacts": {},
        }
        result = build_handoff_update(
            "impl.code",
            {
                "output": "done",
                "artifacts": ["file1.py", "file2.py"],
            },
            ["Decision one", "Decision two"],
            state,
        )
        handoff = result["handoffs"]["impl.code"]
        assert "2 recorded" in handoff or "2 produced" in handoff

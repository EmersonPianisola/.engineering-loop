from __future__ import annotations

"""FASE 8 — Additional tools: stall_detector, timing, json_parse, file_ops."""

import json
from pathlib import Path

import pytest

from eng_loop.tools.file_ops import append_file, file_exists, list_dir, load_json, read_file, save_json, write_file
from eng_loop.tools.json_parse import extract_json
from eng_loop.tools.stall_detector import StallDetector, _is_safe_inspection, create_stall_detector
from eng_loop.tools.timing import TimingTracker, format_time


class TestStallDetector:
    def test_exact_repeat(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("read", {"filePath": "/f.txt"})
        r = d.check()
        assert r is not None
        assert r.stall_type == "exact_repeat"
        assert r.tool_name == "read"
        assert r.count >= 3

    def test_no_stall_different_args(self):
        d = StallDetector(exact_threshold=3)
        for i in range(5):
            d.record("read", {"filePath": f"/f{i}.txt"})
        assert d.check() is None

    def test_same_tool_repeat(self):
        d = StallDetector(same_tool_threshold=5)
        for i in range(6):
            d.record("read", {"filePath": f"/f{i}.txt"})
        r = d.check()
        assert r is not None
        assert r.stall_type == "same_tool_repeat"

    def test_no_progress(self):
        d = StallDetector(no_progress_threshold=5, productive_tools={"write", "edit", "bash"})
        for i in range(6):
            d.record("read", {"filePath": f"/f{i}.txt"})
        r = d.check()
        assert r is not None
        assert r.stall_type == "no_progress"

    def test_productive_resets(self):
        d = StallDetector(no_progress_threshold=5, productive_tools={"write"})
        for _ in range(4):
            d.record("read", {"filePath": "/f.txt"})
        d.record("write", {"filePath": "/o.txt"})
        assert d.check() is None

    def test_disabled(self):
        d = StallDetector(enabled=False)
        for _ in range(10):
            d.record("read", {"filePath": "/f.txt"})
        assert d.check() is None

    def test_reset(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("read", {"filePath": "/f.txt"})
        d.reset()
        assert d.check() is None

    def test_stats(self):
        d = StallDetector()
        d.record("read", {"f": "/a"})
        d.record("write", {"f": "/b"})
        s = d.get_stats()
        assert s["total_calls"] == 2
        assert s["tools_used"]["read"] == 1

    def test_from_config(self):
        d = create_stall_detector(
            {
                "stall_detection": {
                    "window_size": 15,
                    "exact_repeat_threshold": 4,
                    "same_tool_threshold": 12,
                    "no_progress_threshold": 10,
                }
            }
        )
        assert d.window_size == 15
        assert d.exact_threshold == 4

    def test_from_config_disabled(self):
        d = create_stall_detector({"stall_detection": {"enabled": False}})
        assert not d.enabled

    def test_ignored_arg_keys(self):
        d = StallDetector(exact_threshold=2)
        d.record("read", {"filePath": "/f.txt", "offset": 1, "limit": 100})
        d.record("read", {"filePath": "/f.txt", "offset": 200, "limit": 100})
        r = d.check()
        assert r is not None
        assert r.stall_type == "exact_repeat"

    def test_severity_soft_for_read_tool(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("read", {"filePath": "/f.txt"})
        r = d.check()
        assert r is not None
        assert r.severity == "soft"

    def test_severity_soft_for_glob_tool(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("glob", {"pattern": "**/*.py"})
        r = d.check()
        assert r is not None
        assert r.severity == "soft"

    def test_severity_soft_for_grep_tool(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("grep", {"pattern": "foo", "path": "src"})
        r = d.check()
        assert r is not None
        assert r.severity == "soft"

    def test_severity_soft_for_safe_bash(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("bash", {"command": "ls -la"})
        r = d.check()
        assert r is not None
        assert r.severity == "soft"

    def test_severity_hard_for_write(self):
        d = StallDetector(exact_threshold=3)
        for _ in range(4):
            d.record("write", {"filePath": "/f.txt", "content": "x"})
        r = d.check()
        assert r is not None
        assert r.severity == "hard"

    def test_same_tool_severity_soft(self):
        d = StallDetector(same_tool_threshold=5)
        for i in range(6):
            d.record("read", {"filePath": f"/f{i}.txt"})
        r = d.check()
        assert r is not None
        assert r.stall_type == "same_tool_repeat"
        assert r.severity == "soft"


class TestSafeInspection:
    def test_read_is_safe(self):
        assert _is_safe_inspection("read", {"filePath": "/f.txt"})

    def test_glob_is_safe(self):
        assert _is_safe_inspection("glob", {"pattern": "**/*.py"})

    def test_grep_is_safe(self):
        assert _is_safe_inspection("grep", {"pattern": "foo"})

    def test_bash_ls_is_safe(self):
        assert _is_safe_inspection("bash", {"command": "ls -la"})

    def test_bash_cat_is_safe(self):
        assert _is_safe_inspection("bash", {"command": "cat file.txt"})

    def test_bash_git_status_is_safe(self):
        assert _is_safe_inspection("bash", {"command": "git status"})

    def test_bash_find_is_safe(self):
        assert _is_safe_inspection("bash", {"command": "find . -name *.py"})

    def test_bash_pwd_is_safe(self):
        assert _is_safe_inspection("bash", {"command": "pwd"})

    def test_bash_grep_is_safe(self):
        assert _is_safe_inspection("bash", {"command": "grep foo src/"})

    def test_bash_rm_is_not_safe(self):
        assert not _is_safe_inspection("bash", {"command": "rm -rf /"})

    def test_bash_mkfs_is_not_safe(self):
        assert not _is_safe_inspection("bash", {"command": "mkfs.ext4 /dev/sda"})

    def test_write_is_not_safe(self):
        assert not _is_safe_inspection("write", {"filePath": "/f.txt"})

    def test_edit_is_not_safe(self):
        assert not _is_safe_inspection("edit", {"filePath": "/f.txt"})


class TestTiming:
    def test_format_seconds(self):
        assert format_time(45) == "00:00:45"

    def test_format_minutes(self):
        assert format_time(3600) == "01:00:00"

    def test_format_hours(self):
        assert format_time(7200) == "02:00:00"

    def test_format_mixed(self):
        assert format_time(3661) == "01:01:01"

    def test_format_zero(self):
        assert format_time(0) == "00:00:00"

    def test_tracker_record(self):
        t = TimingTracker()
        t.record_stage("init", 10.5)
        t.record_stage("init", 5.2)
        assert t.get_stage_attempts("init") == 2
        assert abs(t.get_stage_total("init") - 15.7) < 0.01

    def test_tracker_summary(self):
        t = TimingTracker()
        t.record_stage("init", 10.0)
        t.record_stage("impl.code", 30.0)
        s = t.get_summary()
        assert len(s) == 2

    def test_tracker_elapsed(self):
        t = TimingTracker()
        assert t.get_loop_elapsed() == 0.0
        t.start_loop()
        assert t.get_loop_elapsed() >= 0.0

    def test_tracker_json(self):
        t = TimingTracker()
        t.start_loop()
        t.record_stage("init", 10.0)
        j = t.to_json()
        assert "loop_start" in j
        assert "stages" in j
        assert j["stages"]["init"]["attempts"] == 1

    def test_tracker_total(self):
        t = TimingTracker()
        t.record_stage("a", 10.0)
        t.record_stage("b", 20.0)
        assert t.get_total_seconds() == 30.0

    def test_tracker_unknown(self):
        t = TimingTracker()
        assert t.get_stage_durations("x") == []
        assert t.get_stage_total("x") == 0.0
        assert t.get_stage_attempts("x") == 0


class TestJsonParse:
    def test_valid(self):
        assert extract_json('{"k": "v", "n": 42}') == {"k": "v", "n": 42}

    def test_code_block(self):
        assert extract_json('```\n{"k": "v"}\n```') == {"k": "v"}

    def test_code_block_json(self):
        assert extract_json('```json\n{"k": "v"}\n```') == {"k": "v"}

    def test_nested(self):
        assert extract_json('{"o": {"i": [1,2,3]}}') == {"o": {"i": [1, 2, 3]}}

    def test_surrounding_text(self):
        assert extract_json('before\n{"k": "v"}\nafter') == {"k": "v"}

    def test_array_wrapped(self):
        assert extract_json("[1,2,3]") == {"items": [1, 2, 3]}

    def test_empty_raises(self):
        try:
            extract_json("")
            assert False
        except ValueError:
            pass

    def test_whitespace_raises(self):
        try:
            extract_json("   \n  ")
            assert False
        except ValueError:
            pass

    def test_prose_raises(self):
        with pytest.raises(ValueError, match="Could not extract JSON"):
            extract_json("This is a long prose response with no JSON structure at all in it.")

    def test_short_raises(self):
        try:
            extract_json("hi")
            assert False
        except ValueError:
            pass

    def test_kv_fallback(self):
        r = extract_json("verdict: PASS\ncomplete: true")
        assert "verdict" in r or "complete" in r


class TestFileOps:
    def test_read(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("hello")
        assert read_file(str(p)) == "hello"

    def test_read_not_found(self):
        assert read_file("/nonexistent") == ""

    def test_write(self, tmp_path):
        p = tmp_path / "a" / "b" / "f.txt"
        r = write_file(str(p), "data")
        assert Path(r).exists()
        assert p.read_text() == "data"

    def test_append(self, tmp_path):
        p = tmp_path / "f.txt"
        write_file(str(p), "first\n")
        append_file(str(p), "second\n")
        assert p.read_text() == "first\nsecond\n"

    def test_exists(self, tmp_path):
        p = tmp_path / "e.txt"
        p.write_text("d")
        assert file_exists(str(p))
        assert not file_exists(str(tmp_path / "n.txt"))

    def test_list_dir(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        assert len(list_dir(str(tmp_path))) == 2

    def test_list_dir_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        assert len(list_dir(str(tmp_path), "*.py")) == 1

    def test_list_dir_nonexistent(self):
        assert list_dir("/nonexistent") == []

    def test_save_json(self, tmp_path):
        p = tmp_path / "d.json"
        save_json(str(p), {"k": "v"})
        assert json.loads(p.read_text()) == {"k": "v"}

    def test_load_json(self, tmp_path):
        p = tmp_path / "d.json"
        p.write_text('{"k": "v"}')
        assert load_json(str(p)) == {"k": "v"}

    def test_load_json_not_found(self):
        assert load_json("/nonexistent") == {}

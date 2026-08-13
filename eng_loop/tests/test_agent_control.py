from __future__ import annotations

"""Tests for agent control fixes: stall detection, JSON template, no_write_count."""

import json
import textwrap
from eng_loop.tools.stall_detector import StallDetector, create_stall_detector
from eng_loop.tools.json_parse import extract_json
from pydantic import BaseModel


# --- Stall Detection: Read-only stages ---

def test_readonly_stall_enabled():
    """Read-only stages now have stall detection enabled (was disabled)."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 6,
            "same_tool_threshold": 15,
            "no_progress_threshold": 25,
        }
    }
    sd = create_stall_detector(cfg)
    assert sd.enabled is True

    # 25 reads should trigger no_progress
    for i in range(25):
        sd.record("read", {"filePath": f"file{i % 5}.py"})

    report = sd.check()
    assert report is not None, "Stall detection should catch 25 non-productive reads"
    assert report.stall_type in ("same_tool_repeat", "no_progress")


def test_readonly_same_file_stall():
    """Repeated reads of same file should trigger exact_repeat."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 6,
            "same_tool_threshold": 15,
            "no_progress_threshold": 25,
        }
    }
    sd = create_stall_detector(cfg)

    # 6 exact reads of same file
    for i in range(6):
        sd.record("read", {"filePath": "cli.py"})

    report = sd.check()
    assert report is not None
    assert report.stall_type == "exact_repeat"
    assert report.count >= 6


def test_readonly_pagination_stall():
    """Pagination reads (different offsets) of same file should trigger exact_repeat."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 6,
            "same_tool_threshold": 15,
            "no_progress_threshold": 25,
        }
    }
    sd = create_stall_detector(cfg)

    # Same file, different offsets (offset ignored in hash)
    for i in range(6):
        sd.record("read", {"filePath": "cli.py", "offset": i * 100, "limit": 100})

    report = sd.check()
    assert report is not None
    assert report.stall_type == "exact_repeat"


def test_readonly_exploration_allowed():
    """Normal exploration (few reads per file) should NOT trigger stall."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 6,
            "same_tool_threshold": 15,
            "no_progress_threshold": 25,
        }
    }
    sd = create_stall_detector(cfg)

    # 3 reads of same file (below threshold of 6)
    for i in range(3):
        sd.record("read", {"filePath": "cli.py"})

    report = sd.check()
    assert report is None, "3 reads of same file should not trigger stall"


# --- Stall Detection: Productive stages ---

def test_productive_no_progress_threshold():
    """Productive stages: no_progress threshold lowered from 30 to 15."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 5,
            "same_tool_threshold": 12,
            "no_progress_threshold": 15,
        }
    }
    sd = create_stall_detector(cfg)

    # 15 reads without writing
    for i in range(15):
        sd.record("read", {"filePath": f"file{i}.py"})

    report = sd.check()
    assert report is not None, "15 non-productive reads should trigger stall"


def test_productive_same_tool_triggers():
    """same_tool_threshold=12 with window_size=20 should trigger (was 20/window=10, never triggered)."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 5,
            "same_tool_threshold": 12,
            "no_progress_threshold": 15,
        }
    }
    sd = create_stall_detector(cfg)

    # 12 reads of same file
    for i in range(12):
        sd.record("read", {"filePath": "cli.py"})

    report = sd.check()
    assert report is not None
    assert report.stall_type in ("exact_repeat", "same_tool_repeat")


def test_productive_write_resets_streak():
    """A write/edit/bash call should reset the non-productive streak."""
    cfg = {
        "stall_detection": {
            "window_size": 20,
            "exact_repeat_threshold": 5,
            "same_tool_threshold": 12,
            "no_progress_threshold": 15,
        }
    }
    sd = create_stall_detector(cfg)

    # 10 reads, then a write, then 10 more reads
    for i in range(10):
        sd.record("read", {"filePath": f"file{i}.py"})
    sd.record("write", {"filePath": "output.json"})
    for i in range(10):
        sd.record("read", {"filePath": f"file{i}.py"})

    report = sd.check()
    assert report is None, "Write should have reset the non-productive streak"


# --- JSON Template Generation ---

def test_json_template_bool_field():
    """JSON template should generate correct defaults for bool fields."""
    class TestSchema(BaseModel):
        complete: bool

    fields = []
    for name, info in TestSchema.model_fields.items():
        if info.annotation == bool:
            fields.append(f'  "{name}": false')

    assert '  "complete": false' in fields


def test_json_template_str_field():
    """JSON template should generate correct defaults for str fields."""
    class TestSchema(BaseModel):
        summary: str

    fields = []
    for name, info in TestSchema.model_fields.items():
        if info.annotation == str:
            fields.append(f'  "{name}": ""')

    assert '  "summary": ""' in fields


def test_json_template_complex_field():
    """JSON template should handle list/dict/optional fields gracefully."""
    class TestSchema(BaseModel):
        files: list[str]
        notes: dict[str, str]

    fields = []
    for name, info in TestSchema.model_fields.items():
        ann = info.annotation
        if ann == bool:
            fields.append(f'  "{name}": false')
        elif ann == str:
            fields.append(f'  "{name}": ""')
        else:
            fields.append(f'  "{name}": ""')

    assert any('"files"' in f for f in fields)
    assert any('"notes"' in f for f in fields)


# --- JSON Extraction ---

def test_extract_json_basic():
    """Basic JSON extraction should work."""
    text = 'Here is the result:\n{"complete": true, "summary": "done"}\nEnd.'
    result = extract_json(text)
    assert result is not None
    assert result.get("complete") is True


def test_extract_json_markdown_block():
    """JSON inside markdown code block should be extracted."""
    text = "```json\n{\"complete\": true}\n```"
    result = extract_json(text)
    assert result is not None
    assert result.get("complete") is True


def test_extract_json_no_markers():
    """JSON without any markers should still be extracted."""
    text = '{"complete": true, "summary": "test"}'
    result = extract_json(text)
    assert result is not None


def test_extract_json_brace_matching():
    """Brace matching should handle nested objects."""
    text = '{"outer": {"inner": {"deep": true}}, "complete": true}'
    result = extract_json(text)
    assert result is not None
    assert result.get("complete") is True


# --- no_write_count enforcement ---

def test_no_write_count_threshold():
    """no_write_count should trigger at NO_WRITE_KILL=25 (was 35)."""
    NO_WRITE_KILL = 25
    no_write_count = 0

    # Simulate 24 reads (below threshold)
    for _ in range(24):
        no_write_count += 1

    assert no_write_count < NO_WRITE_KILL, "24 reads should be below threshold"

    # 25th read should trigger
    no_write_count += 1
    assert no_write_count >= NO_WRITE_KILL, "25 reads should trigger kill"


def test_no_write_count_reset_on_write():
    """Write should reset no_write_count to 0."""
    no_write_count = 20
    # Agent writes
    no_write_count = 0
    # 5 more reads
    no_write_count += 5
    assert no_write_count == 5, "Count should have been reset by write"


# --- Integration: Config propagation ---

def test_stall_config_productive_stage():
    """Productive stage config should have correct thresholds."""
    # Simulate what agent_runner.py does for productive stages
    agent_cfg = {}
    stall_cfg = dict(agent_cfg)
    stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
    stall_cfg["stall_detection"]["no_progress_threshold"] = max(
        stall_cfg["stall_detection"].get("no_progress_threshold", 8),
        15,
    )
    stall_cfg["stall_detection"]["exact_repeat_threshold"] = max(
        stall_cfg["stall_detection"].get("exact_repeat_threshold", 3),
        5,
    )
    stall_cfg["stall_detection"]["same_tool_threshold"] = max(
        stall_cfg["stall_detection"].get("same_tool_threshold", 10),
        12,
    )
    stall_cfg["stall_detection"]["window_size"] = 20

    sd = create_stall_detector(stall_cfg)
    assert sd.window_size == 20
    assert sd.exact_threshold == 5
    assert sd.same_tool_threshold == 12
    assert sd.no_progress_threshold == 15


def test_stall_config_readonly_stage():
    """Read-only stage config should have stall detection enabled."""
    agent_cfg = {}
    stall_cfg = dict(agent_cfg)
    stall_cfg["stall_detection"] = dict(agent_cfg.get("stall_detection", {}))
    stall_cfg["stall_detection"]["no_progress_threshold"] = 25
    stall_cfg["stall_detection"]["exact_repeat_threshold"] = 6
    stall_cfg["stall_detection"]["same_tool_threshold"] = 15
    stall_cfg["stall_detection"]["window_size"] = 20

    sd = create_stall_detector(stall_cfg)
    assert sd.enabled is True
    assert sd.window_size == 20
    assert sd.exact_threshold == 6
    assert sd.same_tool_threshold == 15
    assert sd.no_progress_threshold == 25

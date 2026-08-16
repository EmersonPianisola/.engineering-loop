from __future__ import annotations

"""Tests for interactive state editing: slice building, merging, validation."""

import json
import tempfile
from pathlib import Path

from eng_loop.tools.interactive import (
    build_editable_slice,
    get_editor_command,
    merge_slice_back,
    validate_edited_json,
)


class TestBuildEditableSlice:
    def test_contains_stage_id(self):
        state = {"stages": {"init": {"done": True, "attempts": 1}}}
        slice_data = build_editable_slice(state, "init")
        assert slice_data["stage_id"] == "init"

    def test_contains_stage_status(self):
        state = {"stages": {"init": {"done": True, "attempts": 1}}}
        slice_data = build_editable_slice(state, "init")
        assert slice_data["stage_status"]["done"] is True

    def test_contains_blocking_condition(self):
        state = {
            "status": "blocked",
            "blocking_condition": "max attempts",
            "errors": ["error1"],
            "work_item": "Fix bug",
        }
        slice_data = build_editable_slice(state, "init")
        assert slice_data["blocking_condition"] == "max attempts"
        assert slice_data["errors_or_findings"] == ["error1"]

    def test_excludes_noisy_fields(self):
        state = {
            "stages": {},
            "messages": ["very long message"],
            "full_artifacts": {"key": "x" * 10000},
        }
        slice_data = build_editable_slice(state, "init")
        assert "messages" not in slice_data
        assert "full_artifacts" not in slice_data


class TestMergeSliceBack:
    def test_merges_stage_status(self):
        state = {"stages": {"init": {"done": False}}}
        edited = {"stage_id": "init", "stage_status": {"done": True, "attempts": 2}}
        result = merge_slice_back(state, edited)
        assert result["stages"]["init"]["done"] is True
        assert result["stages"]["init"]["attempts"] == 2

    def test_merges_blocking_condition(self):
        state = {"status": "running", "blocking_condition": ""}
        edited = {
            "stage_id": "init",
            "status": "blocked",
            "blocking_condition": "error",
        }
        result = merge_slice_back(state, edited)
        assert result["status"] == "blocked"
        assert result["blocking_condition"] == "error"

    def test_merges_errors(self):
        state = {"errors": []}
        edited = {
            "stage_id": "init",
            "errors_or_findings": ["new error"],
        }
        result = merge_slice_back(state, edited)
        assert result["errors"] == ["new error"]

    def test_empty_node_id_no_change(self):
        state = {"stages": {"init": {"done": True}}}
        edited = {"stage_id": ""}
        result = merge_slice_back(state, edited)
        assert result["stages"]["init"]["done"] is True


class TestValidateEditedJson:
    def test_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"key": "value"}, f)
            f.flush()
            data, error = validate_edited_json(f.name)
        Path(f.name).unlink()
        assert error is None
        assert data["key"] == "value"

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("")
            f.flush()
            _data, error = validate_edited_json(f.name)
        Path(f.name).unlink()
        assert error is not None
        assert "empty" in error.lower()

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write("{invalid json}")
            f.flush()
            _data, error = validate_edited_json(f.name)
        Path(f.name).unlink()
        assert error is not None
        assert "Invalid JSON" in error

    def test_array_root_rejected(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
            f.flush()
            _data, error = validate_edited_json(f.name)
        Path(f.name).unlink()
        assert error is not None
        assert "JSON object" in error


class TestGetEditorCommand:
    def test_returns_list(self):
        cmd = get_editor_command()
        assert isinstance(cmd, list)
        assert len(cmd) > 0

    def test_notepad_on_windows(self):
        import os

        if os.name == "nt":
            cmd = get_editor_command()
            assert any("notepad" in c.lower() for c in cmd) or len(cmd) > 0

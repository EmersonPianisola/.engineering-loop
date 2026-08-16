from __future__ import annotations

"""Tests for state history: snapshots, rollback, retention."""

import json
import tempfile
from pathlib import Path

from eng_loop.state import make_initial_state
from eng_loop.tools.state_history import (
    _extract_stage_id,
    _extract_timestamp,
    _make_snapshot_filename,
    get_history_dir,
    get_retention,
    get_snapshot_before,
    is_enabled,
    list_snapshots,
    rollback_and_save,
    rollback_to,
    save_snapshot,
)


class TestStateHistoryConfig:
    def test_enabled_by_default(self):
        assert is_enabled({}) is True

    def test_disabled(self):
        assert is_enabled({"state_history": {"enabled": False}}) is False

    def test_retention_default(self):
        assert get_retention({}) == 5

    def test_retention_custom(self):
        assert get_retention({}, {"state_history": {"retention_per_stage": 10}}) == 10

    def test_history_dir_default(self):
        paths = {"artifact_root": "artifacts"}
        d = get_history_dir(paths)
        assert "history" in str(d)


class TestSnapshotFilename:
    def test_filename_format(self):
        name = _make_snapshot_filename("impl.code")
        assert name.startswith("state_after_impl-code_")
        assert name.endswith(".json")

    def test_extract_stage_id(self):
        sid = _extract_stage_id("state_after_impl-code_20260812_143022_123456.json")
        assert sid == "impl.code"

    def test_extract_stage_id_init(self):
        sid = _extract_stage_id("state_after_init_20260812_143022_123456.json")
        assert sid == "init"

    def test_extract_timestamp(self):
        ts = _extract_timestamp("state_after_init_20260812_143022_123456.json")
        assert "2026-08-12" in ts


class TestSaveSnapshot:
    def test_save_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["work_item"] = "Test item"
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            paths = {"artifact_root": artifact_root}
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                }
            }
            result_path = save_snapshot(state, paths, "init", config)
            assert result_path is not None
            assert result_path.exists()
            data = json.loads(result_path.read_text(encoding="utf-8"))
            assert data["work_item"] == "Test item"

    def test_save_snapshot_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            paths = {"artifact_root": str(Path(tmp) / "artifacts")}
            config = {"state_history": {"enabled": False}}
            result = save_snapshot(state, paths, "init", config)
        assert result is None

    def test_save_creates_history_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            paths = {"artifact_root": artifact_root}
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                }
            }
            save_snapshot(state, paths, "init", config)
            assert Path(history_dir).exists()


class TestRetention:
    def test_retention_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            paths = {"artifact_root": artifact_root}
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                    "retention_per_stage": 3,
                }
            }
            for i in range(5):
                import time

                time.sleep(0.01)
                save_snapshot(state, paths, "init", config)
            snapshots = list(Path(history_dir).glob("state_after_init_*.json"))
            assert len(snapshots) == 3


class TestListSnapshots:
    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"artifact_root": str(Path(tmp) / "artifacts")}
            snapshots = list_snapshots(paths)
        assert snapshots == []

    def test_list_after_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            paths = {"artifact_root": artifact_root}
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                }
            }
            save_snapshot(state, paths, "init", config)
            save_snapshot(state, paths, "verify", config)
            snapshots = list_snapshots(paths, config)
        assert len(snapshots) == 2
        for s in snapshots:
            assert "path" in s
            assert "stage_id" in s
            assert "timestamp" in s


class TestRollback:
    def test_rollback_to_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["work_item"] = "Original"
            state["stages"]["init"]["done"] = True
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            paths = {"artifact_root": artifact_root}
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                }
            }
            save_snapshot(state, paths, "init", config)

            # Rollback to before verify
            restored = rollback_to("verify", paths, config)
        assert restored is not None
        assert restored["work_item"] == "Original"
        assert restored["status"] == "running"
        assert restored["current_stage"] == "verify"

    def test_rollback_no_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"artifact_root": str(Path(tmp) / "artifacts")}
            restored = rollback_to("verify", paths)
        assert restored is None

    def test_rollback_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["stages"]["init"]["done"] = True
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            state_file = str(Path(tmp) / "state.json")
            paths = {
                "artifact_root": artifact_root,
                "state_file": state_file,
            }
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                }
            }
            save_snapshot(state, paths, "init", config)

            success = rollback_and_save("verify", paths, config)
            assert success is True
            assert Path(state_file).exists()


class TestGetSnapshotBefore:
    def test_get_snapshot_before_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_initial_state({}, {})
            state["stages"]["init"]["done"] = True
            state["stages"]["impl.code"]["done"] = True
            artifact_root = str(Path(tmp) / "artifacts")
            history_dir = str(Path(tmp) / "history")
            paths = {"artifact_root": artifact_root}
            config = {
                "state_history": {
                    "enabled": True,
                    "history_dir": history_dir,
                }
            }
            save_snapshot(state, paths, "init", config)
            import time

            time.sleep(0.01)
            save_snapshot(state, paths, "impl.code", config)

            snapshot = get_snapshot_before("verify", paths, config)
            assert snapshot is not None
            assert snapshot.exists()

from __future__ import annotations

"""FASE 6B-6D — State history, schemas, config gap tests."""

import json
import tempfile
from pathlib import Path

from eng_loop.config import load_config
from eng_loop.schemas import STAGE_SCHEMA, get_schema
from eng_loop.state import STAGE_ORDER, make_initial_state, restore_snapshot


class TestStateHistory:
    def test_save_snapshot(self):
        from eng_loop.tools.state_history import save_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            s = make_initial_state({}, {})
            s["work_item"] = "Test"
            paths = {"artifact_root": tmp}
            p = save_snapshot(s, paths, "init")
            assert p is not None and p.exists()
            with open(p) as f:
                assert json.load(f)["work_item"] == "Test"

    def test_list_snapshots(self):
        from eng_loop.tools.state_history import get_history_dir, list_snapshots, save_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"artifact_root": tmp}
            config = {"state_history": {"history_dir": f"{tmp}/history"}}
            hist_dir = get_history_dir(paths, config)
            hist_dir.mkdir(parents=True, exist_ok=True)
            s = make_initial_state({}, {})
            s["work_item"] = "A"
            save_snapshot(s, paths, "init", config)
            s["work_item"] = "B"
            save_snapshot(s, paths, "impl.code", config)
            snaps = list_snapshots(paths, config)
            assert len(snaps) >= 2

    def test_restore(self):
        from eng_loop.tools.state_history import save_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            s = make_initial_state({}, {})
            s["work_item"] = "Orig"
            s["complexity"] = "medium"
            paths = {"artifact_root": tmp}
            p = save_snapshot(s, paths, "init")
            r = restore_snapshot(str(p))
            assert r["work_item"] == "Orig"
            assert r["complexity"] == "medium"

    def test_snapshot_merge(self):
        from eng_loop.tools.state_history import save_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            s = make_initial_state({}, {})
            s["work_item"] = "T"
            paths = {"artifact_root": tmp}
            p = save_snapshot(s, paths, "init")
            r = restore_snapshot(str(p))
            assert "stages" in r
            assert "status" in r

    def test_template_fields(self):
        from eng_loop.state import make_initial_state
        t = make_initial_state({}, {})
        assert "stages" in t
        assert "status" in t
        assert "complexity" in t


class TestSchemas:
    def test_all_stages_have_schema(self):
        for sid in STAGE_ORDER:
            assert sid in STAGE_SCHEMA, f"Missing: {sid}"

    def test_valid_data(self):
        from eng_loop.schemas import InitOutput, QaOutput, VerifyOutput
        i = InitOutput(valid=True, work_item_refined="t", estimated_files=5, estimated_tasks=3, notes="ok")
        assert i.valid
        v = VerifyOutput(verdict="PASS", per_ac_evidence=[], discrimination_sensor="ok", coverage_audit="ok", gaps=[], complete=True)
        assert v.verdict == "PASS"
        q = QaOutput(verdict="PASS", findings=[], critical_findings=[], complete=True)
        assert q.verdict == "PASS"

    def test_invalid_data(self):
        from pydantic import ValidationError

        from eng_loop.schemas import InitOutput
        try:
            InitOutput(valid="no", work_item_refined=123, estimated_files="five", estimated_tasks=[], notes={})
            assert False
        except ValidationError:
            pass

    def test_mapping_complete(self):
        assert len(STAGE_SCHEMA) == len(STAGE_ORDER)

    def test_get_schema(self):
        from eng_loop.schemas import ArchOutput, DesignOutput, InitOutput, VerifyOutput
        assert get_schema("init") == InitOutput
        assert get_schema("verify") == VerifyOutput
        assert get_schema("design.user-research") == DesignOutput
        assert get_schema("arch.requirements") == ArchOutput

    def test_get_schema_unknown(self):
        assert get_schema("nonexistent") is None


class TestConfig:
    def test_load_with_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = load_config(tmp, tmp)
            assert isinstance(c, dict)

    def test_project_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp) / "config-template.yaml"
            tp.write_text("agent:\n  max_agent_iterations: 25\nconstraints:\n  max_init_ideate_attempts: 3\n")
            pp = Path(tmp) / "config.yaml"
            pp.write_text("agent:\n  max_agent_iterations: 50\n")
            c = load_config(tmp, tmp)
            assert isinstance(c, dict)

    def test_resolve_paths(self):
        from eng_loop.config import resolve_paths
        with tempfile.TemporaryDirectory() as tmp:
            config = {"paths": {}}
            p = resolve_paths(config, Path(tmp), Path(tmp), Path(tmp))
            assert "project_root" in p

    def test_ensure_dirs(self):
        from eng_loop.config import ensure_directories
        with tempfile.TemporaryDirectory() as tmp:
            ensure_directories({"project_root": tmp, "artifact_root": f"{tmp}/artifacts", "log_root": f"{tmp}/logs", "history_dir": f"{tmp}/history"})
            assert Path(f"{tmp}/artifacts").exists()

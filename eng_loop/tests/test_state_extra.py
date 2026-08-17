from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from eng_loop.config import deep_merge, load_yaml
from eng_loop.schemas import (
    STAGE_SCHEMA,
    ArchOutput,
    DeployPrepareOutput,
    DesignOutput,
    DocDecisionsOutput,
    DocProjectOutput,
    E2eOutput,
    ImplCodeOutput,
    ImplDesignOutput,
    InitOutput,
    PostOutput,
    QaOutput,
    SmokeTestOutput,
    VerifyOutput,
    get_schema,
)
from eng_loop.state import (
    COMPLEXITY_ORDER,
    STAGE_MIN_COMPLEXITY,
    STAGE_ORDER,
    _last_write_wins,
    _max_int,
    _merge_dict,
    init_stages,
    is_stage_active,
    load_state_template,
    make_stage,
    restore_snapshot,
)

# ── STATE REDUCERS & HELPERS ──────────────────────────────────────────────


def test_make_stage_defaults():
    s = make_stage()
    assert s == {
        "done": False,
        "attempts": 0,
        "essence_checked": False,
        "output": "",
        "artifact_path": "",
        "verdict": "",
        "status": "",
        "findings": [],
        "evidence": {},
        "started_at": 0.0,
        "completed_at": 0.0,
    }


def test_init_stages_all_26():
    stages = init_stages()
    assert len(stages) == 31
    for sid in STAGE_ORDER:
        assert sid in stages
        assert stages[sid]["done"] is False


def test_merge_dict_deep_merge():
    old = {"a": 1, "nested": {"x": 1, "y": 2}}
    new = {"nested": {"y": 99, "z": 3}}
    result = _merge_dict(old, new)
    assert result["nested"] == {"x": 1, "y": 99, "z": 3}


def test_merge_dict_shallow_override():
    old = {"a": 1, "b": "old"}
    new = {"b": "new"}
    result = _merge_dict(old, new)
    assert result["b"] == "new"


def test_merge_dict_new_keys():
    old = {"a": 1}
    new = {"b": 2}
    result = _merge_dict(old, new)
    assert result == {"a": 1, "b": 2}


def test_last_write_wins_update_preferred():
    assert _last_write_wins("current", "new") == "new"


def test_last_write_wins_empty_update():
    assert _last_write_wins("current", "") == "current"


def test_max_int_takes_maximum():
    assert _max_int(3, 5) == 5
    assert _max_int(10, 2) == 10
    assert _max_int(0, 0) == 0


def test_stage_min_complexity_entries():
    assert STAGE_MIN_COMPLEXITY["design.user-research"] == "large"
    assert STAGE_MIN_COMPLEXITY["arch.requirements"] == "medium"
    assert STAGE_MIN_COMPLEXITY["arch.review"] == "complex"
    assert STAGE_MIN_COMPLEXITY["init.bdd"] == "large"


def test_complexity_order_values():
    assert COMPLEXITY_ORDER == {"small": 0, "medium": 1, "large": 2, "complex": 3}


def test_is_stage_active_small_complexity():
    assert is_stage_active("init", "small", False) is True
    assert is_stage_active("impl.code", "small", False) is True
    assert is_stage_active("design.user-research", "small", False) is False
    assert is_stage_active("design.personas", "small", False) is False


def test_is_stage_active_medium_complexity():
    assert is_stage_active("arch.requirements", "medium", False) is True
    assert is_stage_active("arch.solution", "medium", False) is True
    assert is_stage_active("arch.review", "medium", False) is False


def test_is_stage_active_e2e_no_ui():
    assert is_stage_active("e2e.execute", "large", False) is False
    assert is_stage_active("e2e.execute", "large", True) is True


def test_is_stage_active_smoke_no_ui():
    assert is_stage_active("smoke.test", "large", False) is False
    assert is_stage_active("smoke.test", "large", True) is True


def test_is_stage_active_bugfix():
    assert is_stage_active("design.user-research", "large", True, "bugfix") is False
    assert is_stage_active("design.personas", "large", True, "bugfix") is False
    assert is_stage_active("impl.code", "large", True, "bugfix") is True


def test_is_stage_active_documentation():
    assert is_stage_active("impl.design", "medium", False, "documentation") is False
    assert is_stage_active("verify", "medium", False, "documentation") is False
    assert is_stage_active("init", "medium", False, "documentation") is True


def test_is_stage_active_operational():
    assert is_stage_active("impl.design", "medium", False, "operational") is False
    assert is_stage_active("impl.code", "medium", False, "operational") is False
    assert is_stage_active("init", "medium", False, "operational") is True


def test_is_stage_active_unset_complexity():
    for sid in STAGE_ORDER:
        assert is_stage_active(sid, "unset", False) is True


# ── STATE TEMPLATE & RESTORE ──────────────────────────────────────────────


def test_load_state_template():
    data = {"current_stage": "init", "iteration": 3, "stages": {}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        loaded = load_state_template(f.name)
    Path(f.name).unlink()
    assert loaded["current_stage"] == "init"
    assert loaded["iteration"] == 3


def test_restore_snapshot():
    data = {
        "current_stage": "verify",
        "iteration": 2,
        "complexity": "medium",
        "stages": {"init": {"done": True, "attempts": 1}},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        restored = restore_snapshot(f.name)
    Path(f.name).unlink()
    assert restored["iteration"] == 2
    assert restored["complexity"] == "medium"
    assert restored["stages"]["init"]["done"] is True
    assert restored["status"] == "running"
    assert restored["work_type"] == "feature"


def test_restore_snapshot_missing_fields():
    data = {"current_stage": "init"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        restored = restore_snapshot(f.name)
    Path(f.name).unlink()
    assert restored["iteration"] == 0
    assert restored["complexity"] == "unset"
    assert restored["ui_project"] is False
    assert restored["stages"] == init_stages()
    assert restored["tags"] == []
    assert restored["decisions"] == []


# ── SCHEMA VALIDATION ─────────────────────────────────────────────────────


def test_all_26_stages_have_schema():
    for sid in STAGE_ORDER:
        assert sid in STAGE_SCHEMA, f"Missing schema for {sid}"


def test_schema_init_output_valid():
    obj = InitOutput(valid=True, work_item_refined="Refined task", estimated_files=5, estimated_tasks=3)
    assert obj.valid is True
    assert obj.estimated_files == 5


def test_schema_init_output_defaults():
    obj = InitOutput()
    assert obj.valid is True
    assert obj.work_item_refined == ""
    assert obj.estimated_files == 0
    assert obj.estimated_tasks == 0
    assert obj.notes == ""


def test_schema_design_output_valid():
    obj = DesignOutput(design_output="Design spec", artifacts=["figma-link"], decisions=["AD-001: nav"])
    assert obj.complete is True
    assert len(obj.artifacts) == 1


def test_schema_arch_output_valid():
    obj = ArchOutput(architecture_output="C4 model", critical_findings=["No auth"])
    assert obj.complete is True
    assert len(obj.critical_findings) == 1


def test_schema_impl_design_output_valid():
    obj = ImplDesignOutput(blueprint="Full plan", tasks=["t1"], file_structure=["a.py"])
    assert obj.complete is True
    assert len(obj.tasks) == 1


def test_schema_impl_code_output_valid():
    obj = ImplCodeOutput(
        implementation_summary="Done",
        files_created=["a.py"],
        tests_passed=True,
        diff="diff --git",
    )
    assert obj.complete is True
    assert obj.tests_passed is True


def test_schema_verify_output_valid():
    obj = VerifyOutput(
        verdict="PASS",
        per_ac_evidence=["AC1 -> file.py:10"],
        discrimination_sensor="pass",
        coverage_audit="pass",
    )
    assert obj.verdict == "PASS"
    assert obj.complete is True


def test_schema_e2e_output_valid():
    obj = E2eOutput(
        verdict="PASS",
        test_results=["Login: passed"],
        console_errors=0,
        network_errors=0,
        bdd_coverage="full",
    )
    assert obj.console_errors == 0
    assert obj.complete is True


def test_schema_qa_output_valid():
    obj = QaOutput(
        verdict="FAIL",
        findings=["Minor issue"],
        critical_findings=["Critical: XSS"],
    )
    assert obj.verdict == "FAIL"
    assert len(obj.critical_findings) == 1


def test_schema_deploy_output_valid():
    obj = DeployPrepareOutput(
        build_status="pass",
        lint_status="pass",
        type_check_status="pass",
        verdict="PASS",
    )
    assert obj.verdict == "PASS"
    assert obj.complete is True


def test_schema_smoke_output_valid():
    obj = SmokeTestOutput(
        verdict="PASS",
        critical_paths=["Login", "Checkout"],
        console_errors=0,
    )
    assert len(obj.critical_paths) == 2
    assert obj.complete is True


def test_schema_doc_decisions_output_valid():
    obj = DocDecisionsOutput(decision_log="MADR log", decisions_count=3)
    assert obj.decisions_count == 3
    assert obj.complete is True


def test_schema_doc_project_output_valid():
    obj = DocProjectOutput(
        readme="# Project",
        setup_guide="npm install",
        architecture_overview="C4 context",
        user_manual="How to use",
    )
    assert obj.readme == "# Project"
    assert obj.complete is True


def test_schema_post_output_valid():
    obj = PostOutput(summary="All done", lessons_to_share=2, final_status="done")
    assert obj.final_status == "done"
    assert obj.complete is True


def test_get_schema_returns_correct_type():
    assert get_schema("init") is InitOutput
    assert get_schema("verify") is VerifyOutput
    assert get_schema("post") is PostOutput
    assert get_schema("impl.code") is ImplCodeOutput


def test_get_schema_unknown_returns_none():
    assert get_schema("nonexistent.stage") is None
    assert get_schema("") is None


def test_schema_init_output_invalid_type():
    with pytest.raises(ValidationError):
        InitOutput(valid="yes", estimated_files="five")


def test_schema_verify_output_invalid_verdict():
    obj = VerifyOutput(verdict="MAYBE")
    assert obj.verdict == "MAYBE"

    with pytest.raises(ValidationError):
        VerifyOutput(verdict=123)


# ── CONFIG DEEP MERGE ─────────────────────────────────────────────────────


def test_deep_merge_nested_dicts():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99, "e": 5}}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3, "e": 5}}


def test_deep_merge_list_override():
    base = {"items": [1, 2, 3]}
    override = {"items": [4, 5]}
    result = deep_merge(base, override)
    assert result["items"] == [4, 5]


def test_deep_merge_new_keys():
    base = {"a": 1}
    override = {"b": 2}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": 2}


def test_deep_merge_empty_override():
    base = {"a": 1, "b": {"c": 2}}
    result = deep_merge(base, {})
    assert result == {"a": 1, "b": {"c": 2}}


def test_deep_merge_multiple_levels():
    base = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
    override = {"a": {"b": {"c": {"d": 99, "f": 3}}}}
    result = deep_merge(base, override)
    assert result == {"a": {"b": {"c": {"d": 99, "e": 2, "f": 3}}}}


def test_load_yaml_existing():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"key": "value", "num": 42}, f)
        f.flush()
        result = load_yaml(f.name)
    Path(f.name).unlink()
    assert result == {"key": "value", "num": 42}


def test_load_yaml_missing():
    assert load_yaml("/nonexistent/path/to/file.yaml") == {}


def test_load_yaml_empty_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        f.flush()
        result = load_yaml(f.name)
    Path(f.name).unlink()
    assert result == {}

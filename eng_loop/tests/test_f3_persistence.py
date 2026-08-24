"""F3.3 — Persistence completeness.

Before the fix, _make_saveable/restore_snapshot omitted context_bus,
qa_results, user_interactions, recovery_attempts, recovery_history and
task_outcome — resume zeroed the recovery budget and essence re-asked.

Round-trip contract: state -> _make_saveable -> JSON -> load_state_template
-> restore_snapshot -> every key present, values identical.
"""

from __future__ import annotations

import json
import tempfile
from typing import Any

import pytest

from eng_loop.cli import _make_saveable, _rehydrate_loaded_state
from eng_loop.context_bus import ContextBus
from eng_loop.state import (
    PipelineState,
    load_state_template,
    make_initial_state,
    restore_snapshot,
    restore_snapshot_data,
)


def _full_state() -> dict[str, Any]:
    s = make_initial_state({"model": {"base_url": "http://x"}}, {"artifact_root": "a"})
    s["work_item"] = "Add login feature"  # str so the round-trip is identity
    s["iteration"] = 2
    s["status"] = "blocked"
    s["blocking_condition"] = "need input"
    s["complexity"] = "medium"
    s["work_type"] = "bugfix"
    s["stages"]["init"] = {"done": True, "attempts": 1, "total_attempts": 1}
    s["decisions"] = ["use oauth"]
    s["handoffs"] = {"init": "validated"}
    s["fix_tasks"] = [{"source": "verify", "gap": "missing test"}]
    s["dynamic_runtime"] = {
        "cursor": 2,
        "attempts": {},
        "completed": ["init"],
        "failed": [],
        "status": "running",
        "step_audit": [],
    }
    s["essence"] = {"checked": True, "blocked_stage": "init", "auto_adjust_attempts": 2}
    s["essence_clarifying_questions"] = [{"question_id": "q1"}]
    s["qa_results"] = {"qa.unit": {"verdict": "PASS"}}
    s["user_interactions"] = [{"question_id": "q1", "answer": "a1"}]
    s["recovery_attempts"] = 3
    s["recovery_history"] = [{"attempt_number": 1, "outcome": "failed"}]
    s["task_outcome"] = "done"
    bus = ContextBus()
    bus.append("clarification", {"q": "scope?", "a": "login only"}, source_stage="init")
    s["context_bus"] = bus
    return s


def _round_trip(state: dict[str, Any]) -> dict[str, Any]:
    saveable = _make_saveable(state)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(saveable, f)
        path = f.name
    loaded = load_state_template(path)
    restored = restore_snapshot(path)
    return restored


# ── Round-trip: every key survives ───────────────────────────────────


def _saveable_keys() -> list[str]:
    # "tokens" is a runtime metrics blob, not part of PipelineState — it was
    # never restored and is not part of this contract.
    return [k for k in _make_saveable(_full_state()) if k != "tokens"]


@pytest.mark.parametrize("key", _saveable_keys())
def test_round_trip_key_present(key: str) -> None:
    restored = _round_trip(_full_state())
    assert key in restored, f"key {key!r} lost in the save/restore round-trip"


def test_round_trip_value_identity() -> None:
    state = _full_state()
    restored = _round_trip(state)
    for key in (
        "recovery_attempts",
        "recovery_history",
        "qa_results",
        "user_interactions",
        "task_outcome",
        "essence",
        "essence_clarifying_questions",
        "fix_tasks",
        "dynamic_runtime",
        "stages",
        "work_item",
        "complexity",
    ):
        assert restored[key] == state[key], f"key {key!r} changed in round-trip"


def test_round_trip_context_bus_rehydrated() -> None:
    state = _full_state()
    restored = _round_trip(state)
    assert isinstance(restored["context_bus"], ContextBus)
    assert restored["context_bus"].snapshot() == state["context_bus"].snapshot()


# ── Old-format snapshots get defaults ────────────────────────────────


def test_old_format_snapshot_gets_defaults() -> None:
    data = {"current_stage": "init", "iteration": 1, "stages": {"init": {"done": True}}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        f.flush()
        restored = restore_snapshot(f.name)
    assert restored["recovery_attempts"] == 0
    assert restored["recovery_history"] == []
    assert restored["task_outcome"] is None
    assert restored["qa_results"] == {}
    assert restored["user_interactions"] == []
    assert isinstance(restored["context_bus"], ContextBus)
    assert restored["context_bus"].entry_count == 0


def test_legacy_topology_proposal_still_read() -> None:
    data = {"current_stage": "init", "topology_proposal": {"plan_id": "old"}}
    restored = restore_snapshot_data(data)
    assert restored["topology_proposal"] == {"plan_id": "old"}


def test_make_saveable_no_longer_writes_topology_proposal() -> None:
    state = _full_state()
    state["topology_proposal"] = {"plan_id": "x"}
    saveable = _make_saveable(state)
    assert "topology_proposal" not in saveable


# ── --resume rehydration ─────────────────────────────────────────────


def test_rehydrate_loaded_state_dict_bus() -> None:
    bus = ContextBus()
    bus.append("critical_finding", {"f": "race condition"}, source_stage="verify")
    state = {"context_bus": bus.snapshot()}
    out = _rehydrate_loaded_state(state)
    assert isinstance(out["context_bus"], ContextBus)
    assert out["context_bus"].snapshot() == bus.snapshot()


def test_rehydrate_loaded_state_missing_bus() -> None:
    out = _rehydrate_loaded_state({})
    assert isinstance(out["context_bus"], ContextBus)
    assert out["context_bus"].entry_count == 0


# ── Rollback (state_history) keeps the new keys ──────────────────────


def test_rollback_keeps_new_keys() -> None:
    from eng_loop.tools.state_history import rollback_to, save_snapshot

    with tempfile.TemporaryDirectory() as tmp:
        state = _full_state()
        paths = {"artifact_root": f"{tmp}/artifacts"}
        config = {"state_history": {"history_dir": f"{tmp}/history"}}
        save_snapshot(state, paths, "init", config)
        restored = rollback_to("verify", paths, config)

        assert restored is not None
        assert restored["recovery_attempts"] == 3
        assert restored["recovery_history"] == state["recovery_history"]
        assert restored["qa_results"] == state["qa_results"]
        assert restored["user_interactions"] == state["user_interactions"]
        assert restored["task_outcome"] == "done"
        assert isinstance(restored["context_bus"], ContextBus)
        assert restored["context_bus"].entry_count == 1


# ── task_outcome is a real channel (unannotated keys are dropped) ────


def test_pipeline_state_has_task_outcome_channel() -> None:
    import typing

    hints = typing.get_type_hints(PipelineState, include_extras=True)
    assert "task_outcome" in hints
    assert make_initial_state({}, {})["task_outcome"] is None

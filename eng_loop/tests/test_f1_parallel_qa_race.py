"""FASE 1.2 — Fan-out race (H15).

QA workers dispatched via Send used to return the FULL `stages` dict
(snapshot at dispatch + own result). The `_merge_dict` reducer applied the
workers' updates sequentially, so a worker's stale snapshot of a sibling's
entry overwrote the sibling's fresh result (done/verdict/output reverted to
pre-run values) — the join then read stale data and made wrong decisions
(false rollback, lost FAIL findings).

Fix: workers return ONLY their own stage entry — `_merge_dict` merges
per-stage fields, so sibling entries are never touched.

Tests:
1. Reducer: sequential merge of two partial updates preserves both results;
   (contrast) a full-dict snapshot write clobbers the sibling result.
2. Integration: 2 mocked workers, both PASS → after the join, BOTH stages are
   done=True (assertion independent of merge order).
3. Integration: 1 PASS + 1 FAIL → the join sees both real results and rolls
   back with fix_tasks from the correct stage.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import NodeRegistry, build_registry
from eng_loop.state import _merge_dict, make_initial_state, make_stage

DEFAULT_PASS = {
    "valid": True,
    "work_item_refined": "Refined work item description",
    "verdict": "PASS",
    "per_ac_evidence": [{"ac": "AC1", "evidence": "src/a.py:1"}],
    "gaps": [],
    "findings": [],
    "critical_findings": [],
    "implementation_summary": "Implemented the feature with unit tests; all tests pass.",
    "files_created": ["src/a.py", "tests/test_a.py"],
    "tests_passed": True,
    "blueprint": "B" * 60,
    "tasks": ["t1", "t2"],
    "complete": True,
}

QA_PASS = {
    "verdict": "PASS",
    "findings": [],
    "critical_findings": [],
    "test_count": 4,
    "tests_executed": 4,
    "passed": 4,
    "failed": 0,
    "coverage": 90,
    "exit_code": 0,
    "complete": True,
}

UNIT_FAIL = {
    "verdict": "FAIL",
    "severity": "critical",
    "findings": ["unit gap: token refresh not covered"],
    "critical_findings": ["unit critical: refresh race condition"],
    "test_count": 5,
    "tests_executed": 5,
    "passed": 3,
    "failed": 2,
    "coverage": 80,
    "exit_code": 1,
    "complete": True,
}


# ───────────────────────────────────────────────────────────────────
# 1. Reducer: partial updates are race-free
# ───────────────────────────────────────────────────────────────────


class TestPartialUpdateReducer:
    def test_partial_updates_preserve_both_results(self):
        base = {"qa-security": make_stage(), "qa-unit": make_stage()}
        worker_a = {"qa-security": {"done": True, "verdict": "PASS", "output": "A"}}
        worker_b = {"qa-unit": {"done": True, "verdict": "PASS", "output": "B"}}

        merged = _merge_dict(base, worker_a)
        merged = _merge_dict(merged, worker_b)

        assert merged["qa-security"]["done"] is True
        assert merged["qa-security"]["verdict"] == "PASS"
        assert merged["qa-unit"]["done"] is True
        assert merged["qa-unit"]["verdict"] == "PASS"
        # order must not matter
        merged_rev = _merge_dict(_merge_dict(base, worker_b), worker_a)
        assert merged_rev["qa-security"]["verdict"] == "PASS"
        assert merged_rev["qa-unit"]["verdict"] == "PASS"

    def test_full_dict_snapshot_clobbers_sibling(self):
        """Documents the H15 race the partial-update fix removes.

        Worker B returns the full stages dict: its snapshot of worker A's
        entry (taken at dispatch, before A ran) overwrites A's fresh result.
        """
        base = {"qa-security": make_stage(), "qa-unit": make_stage()}
        worker_a = {"qa-security": {"done": True, "verdict": "PASS", "output": "A"}}
        # B's full-dict update: own result + stale snapshot of A
        worker_b_full = {**base, "qa-unit": {"done": True, "verdict": "PASS", "output": "B"}}

        merged = _merge_dict(base, worker_a)
        merged = _merge_dict(merged, worker_b_full)

        assert merged["qa-security"]["done"] is False, "stale full-dict snapshot clobbers A's result"
        assert merged["qa-security"]["verdict"] == ""


# ───────────────────────────────────────────────────────────────────
# Harness (spied handlers + scripted run_agent, no LLM)
# ───────────────────────────────────────────────────────────────────


def _fake_run_agent(scripts: dict[str, list[dict[str, Any]]]):
    from eng_loop.tools.agent_runner import AgentResult

    queues = {k: list(v) for k, v in scripts.items()}

    def fake(model, tools, prompt, stage_id, output_schema=None, max_iterations=25, config=None, **kw):
        queue = queues.get(stage_id)
        if queue:
            data = queue.pop(0)
        elif stage_id in scripts:
            data = scripts[stage_id][-1]
        else:
            data = DEFAULT_PASS
        return AgentResult(data=dict(data), iterations=1, elapsed=0.01, tool_calls_made=1)

    return fake


def _make_state(tmp_path, done_except: frozenset[str]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "constraints": {},
        "essence": {"enabled": False},
        "lessons": {"enabled": False},
        "dynamic_graph": {"parallel_qa": True},
    }
    paths = {"project_root": str(tmp_path), "artifact_root": str(tmp_path)}
    state = make_initial_state(config, paths)
    state["complexity"] = "medium"
    state["work_type"] = "feature"
    state["ui_project"] = False
    state["work_item"] = "Add a testable feature"
    state["codebase_facts"] = {"complexity": "medium", "work_type": "feature", "ui_project": False}
    state["dynamic_plan"] = {"trigger": "none", "steps": []}
    for sid, s in state["stages"].items():
        if sid not in done_except:
            s["done"] = True
            s["output"] = json.dumps(
                {
                    "verdict": "PASS",
                    "tasks": ["t1"],
                    "blueprint": "B" * 60,
                    "per_ac_evidence": [{"ac": "AC1", "evidence": "src/a.py:1"}],
                }
            )
    return state


def _spied_registry(executed: list[str]) -> NodeRegistry:
    registry = build_registry(parallel_qa=True)
    spied = NodeRegistry()
    for spec in registry.all_specs():
        orig = spec.handler
        name = spec.node_name

        def spy(state, _orig=orig, _name=name):
            executed.append(_name)
            return _orig(state)

        spied.register(replace(spec, handler=spy))
    return spied


def _run_pipeline(
    tmp_path, done_except: frozenset[str], scripts: dict[str, list[dict[str, Any]]], join_captures: list | None = None
):
    import eng_loop.nodes.qa_parallel as qp

    executed: list[str] = []
    state = _make_state(tmp_path, done_except)

    orig_join = qp.qa_join_node

    def spied_join_recording(s):
        result = orig_join(s)
        if join_captures is not None:
            join_captures.append((s, result))
        return result

    with (
        patch("eng_loop.tools.agent_runner.run_agent", side_effect=_fake_run_agent(scripts)),
        patch.object(qp, "_get_active_qa_nodes", return_value=["qa-security", "qa-unit"]),
        patch.object(qp, "qa_join_node", spied_join_recording),
        patch("eng_loop.nodes.verification._check_e2e_prerequisites", return_value=None),
    ):
        builder = GraphBuilder(parallel_qa=True, registry=_spied_registry(executed))
        state_graph, _ = builder.build(state)
        compiled = state_graph.compile()
        final_state = compiled.invoke(state, config={"recursion_limit": 60})
    return executed, final_state


# ───────────────────────────────────────────────────────────────────
# 2. Two PASS workers → both results survive to the join
# ───────────────────────────────────────────────────────────────────


class TestBothWorkersPass:
    def test_both_done_after_join(self, tmp_path):
        executed, final = _run_pipeline(
            tmp_path,
            done_except=frozenset({"init", "verify", "qa.security", "qa.unit"}),
            scripts={
                "init": [dict(DEFAULT_PASS)],
                "verify": [dict(DEFAULT_PASS)],
                "qa.security": [dict(QA_PASS)],
                "qa.unit": [dict(QA_PASS)],
            },
        )

        # both workers' results survive regardless of merge order
        assert final["stages"]["qa.security"]["done"] is True
        assert final["stages"]["qa.security"]["verdict"] == "PASS"
        assert final["stages"]["qa.unit"]["done"] is True
        assert final["stages"]["qa.unit"]["verdict"] == "PASS"

        # all-pass → join routes to deploy, pipeline completes
        assert "deploy-prepare" in executed
        assert "post" in executed
        assert final["status"] != "blocked"


# ───────────────────────────────────────────────────────────────────
# 3. One PASS + one FAIL → join rolls back with the correct fix_tasks
# ───────────────────────────────────────────────────────────────────


class TestPassPlusFail:
    def test_join_sees_real_results_and_rolls_back(self, tmp_path):
        join_captures: list = []
        executed, final = _run_pipeline(
            tmp_path,
            done_except=frozenset({"init", "impl.code", "verify", "qa.security", "qa.unit"}),
            scripts={
                "init": [dict(DEFAULT_PASS)],
                "impl.code": [dict(DEFAULT_PASS)],
                "verify": [dict(DEFAULT_PASS)],
                "qa.security": [dict(QA_PASS)],
                "qa.unit": [dict(UNIT_FAIL)],
            },
            join_captures=join_captures,
        )

        assert join_captures, "qa-join never executed"
        first_state, first_cmd = join_captures[0]

        # The join sees BOTH workers' real results (the race fix)
        assert first_state["stages"]["qa.security"]["done"] is True
        assert first_state["stages"]["qa.security"]["verdict"] == "PASS"
        assert first_state["stages"]["qa.unit"]["verdict"] == "FAIL"

        # Rollback decision with fix_tasks from the FAILING stage
        assert first_cmd.goto == "impl-code"
        fix_tasks = first_cmd.update.get("fix_tasks", [])
        assert fix_tasks, "join must aggregate the FAIL findings into fix_tasks"
        assert all(t["source"] == "qa.unit" for t in fix_tasks)
        assert any("token refresh not covered" in t["gap"] for t in fix_tasks)

        # Pipeline is bounded by the fix-iteration limit, then blocked
        assert final["status"] == "blocked"
        assert final["fix_iteration"] == 3
        # The FAIL worker's result survives to the end (no stale clobber)
        assert final["stages"]["qa.unit"]["verdict"] == "FAIL"
        assert final["stages"]["qa.security"]["verdict"] == "PASS"

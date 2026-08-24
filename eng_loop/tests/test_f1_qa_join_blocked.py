"""FASE 1.1 — qa-join failure routing (C1 regression).

Before the fix, GraphBuilder registered a conditional edge on `qa-join` that
always returned "deploy-prepare". LangGraph evaluates declared edges in
parallel with a node's Command(goto=...), so on BLOCKED (goto __end__) and
critical FAIL (goto impl-code) the deploy-prepare node was ALSO scheduled —
deploying a blocked pipeline / racing the rollback.

These integration tests run the compiled parallel-QA graph end-to-end with
spied handlers (real node logic, no LLM: run_agent is scripted) and assert:
- QA BLOCKED → execution sequence does NOT contain deploy-prepare
- critical FAIL → impl-code re-executes exactly once for the single rollback
  decision and deploy-prepare never executes

The fan-out is pinned to a single QA worker (qa-security) so the join
aggregates a single writer's stages update — deterministic regardless of the
H15 fan-out merge race fixed in FASE 1.2.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import NodeRegistry, build_registry
from eng_loop.state import make_initial_state

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

BLOCKED_DATA = {
    "verdict": "BLOCKED",
    "blocked_reason": "Test infrastructure unavailable",
    "findings": [],
    "critical_findings": [],
    "complete": True,
}

CRITICAL_FAIL_DATA = {
    "verdict": "FAIL",
    "severity": "critical",
    "findings": ["SQL injection in /api/login"],
    "critical_findings": ["SQL injection in /api/login"],
    "evidence": "payload bypassed input validation",
    "complete": True,
}


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


def _run_pipeline(tmp_path, done_except: frozenset[str], scripts: dict[str, list[dict[str, Any]]]):
    import eng_loop.nodes.qa_parallel as qp

    executed: list[str] = []
    state = _make_state(tmp_path, done_except)

    orig_dispatch = qp.qa_dispatcher_node
    orig_join = qp.qa_join_node

    def spied_dispatch(s):
        executed.append("qa-dispatcher")
        return orig_dispatch(s)

    def spied_join(s):
        executed.append("qa-join")
        return orig_join(s)

    with (
        patch("eng_loop.tools.agent_runner.run_agent", side_effect=_fake_run_agent(scripts)),
        patch.object(qp, "_get_active_qa_nodes", return_value=["qa-security"]),
        patch("eng_loop.nodes.verification._parallel_dispatch_active", return_value=True),
        patch.object(qp, "qa_dispatcher_node", spied_dispatch),
        patch.object(qp, "qa_join_node", spied_join),
        patch("eng_loop.nodes.verification._check_e2e_prerequisites", return_value=None),
    ):
        builder = GraphBuilder(parallel_qa=True, registry=_spied_registry(executed))
        state_graph, _ = builder.build(state)
        compiled = state_graph.compile()
        final_state = compiled.invoke(state, config={"recursion_limit": 50})
    return executed, final_state


class TestQaJoinBlocked:
    def test_blocked_qa_never_deploys(self, tmp_path):
        executed, final = _run_pipeline(
            tmp_path,
            done_except=frozenset({"init", "verify", "qa.security"}),
            scripts={
                "init": [dict(DEFAULT_PASS)],
                "verify": [dict(DEFAULT_PASS)],
                "qa.security": [dict(BLOCKED_DATA)],
            },
        )

        assert executed.count("qa-join") == 1
        assert "deploy-prepare" not in executed, "BLOCKED pipeline must not schedule deploy-prepare"
        # impl-code only short-circuits on the first pass — no rollback was scheduled
        assert executed.count("impl-code") == 1
        assert executed[-1] == "qa-join"
        assert final["status"] == "blocked"
        assert final["stages"]["qa.security"]["verdict"] == "BLOCKED"


class TestQaJoinCriticalFail:
    def test_critical_fail_rolls_back_exactly_once(self, tmp_path):
        executed, final = _run_pipeline(
            tmp_path,
            done_except=frozenset({"init", "impl.code", "verify", "qa.security"}),
            scripts={
                "init": [dict(DEFAULT_PASS)],
                "impl.code": [dict(DEFAULT_PASS), dict(DEFAULT_PASS)],
                "verify": [dict(DEFAULT_PASS), dict(DEFAULT_PASS)],
                "qa.security": [dict(CRITICAL_FAIL_DATA), dict(BLOCKED_DATA)],
            },
        )

        assert "deploy-prepare" not in executed, "critical FAIL must not schedule deploy-prepare"
        assert executed.count("qa-join") == 2
        # first pass + exactly one rollback re-execution
        assert executed.count("impl-code") == 2

        join1 = executed.index("qa-join")
        impl_rollback = executed.index("impl-code", join1 + 1)
        join2 = executed.index("qa-join", join1 + 1)
        assert join1 < impl_rollback < join2, "rollback must route to impl-code before the next join"

        # second round: qa.security BLOCKED → join halts the pipeline
        assert final["status"] == "blocked"
        assert final["fix_iteration"] == 1

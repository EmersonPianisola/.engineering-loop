"""FASE 1.1 — verify self-retry routing (C1 regression).

The verify node self-retries on evidence-gate failure (goto="verify"). Before
the fix, a declared conditional edge out of verify resolved the loopback to
"impl-code" and LangGraph evaluated it in parallel with the Command —
scheduling impl-code alongside the self-retry (double execution, mitigated
only by the done short-circuit).

Integration test: run the compiled sequential graph with spied handlers and
scripted run_agent. verify's first run fails the evidence gate (invalid
verdict), its second run passes. Assert:
- verify executes exactly 2x, back-to-back
- impl-code does NOT execute between the two verify runs
- the pipeline still advances to completion
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

# Fails the evidence gate: verdict must be PASS or FAIL for verify
EVIDENCE_FAIL_DATA = {"verdict": "ERROR", "complete": True}


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


def _make_state(tmp_path) -> dict[str, Any]:
    config: dict[str, Any] = {
        "constraints": {},
        "essence": {"enabled": False},
        "lessons": {"enabled": False},
    }
    paths = {"project_root": str(tmp_path), "artifact_root": str(tmp_path)}
    state = make_initial_state(config, paths)
    state["complexity"] = "medium"
    state["work_type"] = "feature"
    state["ui_project"] = False
    state["work_item"] = "Add a testable feature"
    state["codebase_facts"] = {"complexity": "medium", "work_type": "feature", "ui_project": False}
    state["dynamic_plan"] = {"trigger": "none", "steps": []}
    # Everything except init (no done short-circuit) and verify (the target)
    # short-circuits through the sequential chain.
    for sid, s in state["stages"].items():
        if sid not in ("init", "verify"):
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
    registry = build_registry(parallel_qa=False)
    spied = NodeRegistry()
    for spec in registry.all_specs():
        orig = spec.handler
        name = spec.node_name

        def spy(state, _orig=orig, _name=name):
            executed.append(_name)
            return _orig(state)

        spied.register(replace(spec, handler=spy))
    return spied


class TestVerifySelfRetry:
    def test_evidence_fail_retries_without_impl_code(self, tmp_path):
        executed: list[str] = []
        state = _make_state(tmp_path)

        with (
            patch(
                "eng_loop.tools.agent_runner.run_agent",
                side_effect=_fake_run_agent(
                    {
                        "init": [dict(DEFAULT_PASS)],
                        "verify": [dict(EVIDENCE_FAIL_DATA), dict(DEFAULT_PASS)],
                    }
                ),
            ),
            patch("eng_loop.nodes.verification._check_e2e_prerequisites", return_value=None),
        ):
            builder = GraphBuilder(parallel_qa=False, registry=_spied_registry(executed))
            state_graph, _ = builder.build(state)
            compiled = state_graph.compile()
            final = compiled.invoke(state, config={"recursion_limit": 50})

        verify_indices = [i for i, n in enumerate(executed) if n == "verify"]
        assert len(verify_indices) == 2, f"verify must run exactly twice, sequence: {executed}"
        assert verify_indices[1] == verify_indices[0] + 1, "self-retry must be a direct loopback"

        between = executed[verify_indices[0] + 1 : verify_indices[1]]
        assert "impl-code" not in between, "impl-code must not run between the two verify executions"

        # First pass short-circuit only — no rollback scheduled
        assert executed.count("impl-code") <= 1
        assert final["stages"]["verify"]["done"] is True
        assert "post" in executed, "pipeline must advance to completion after the retry"
        assert final["status"] != "blocked"

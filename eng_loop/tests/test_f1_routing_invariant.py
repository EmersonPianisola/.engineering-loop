"""FASE 1.1 — Single source of routing invariants.

LangGraph 1.x evaluates declared outgoing edges IN PARALLEL with a node's
Command(goto=...). A node that owns routing via Command must therefore have
NO outgoing edges (fixed or conditional) registered on it, otherwise the
declared edge's target double-executes alongside the Command's goto.

Invariants tested here:
1. Every registered NodeSpec defaults to routing="command" (all handlers
   return Command).
2. For every compiled graph (deterministic x {small, medium, complex, ui},
   parallel_qa, and proposal path): no command-routed node has registered
   branches (conditional edges) or fixed edges.
3. Parity: for representative states (done / fresh / exhausted / fail), each
   handler's Command goto is a valid destination declared in the graph (or END).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from langgraph.types import Command, Send

from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import build_registry
from eng_loop.schemas import EdgeDefinition, GraphTopologyProposal, PhaseGroup
from eng_loop.state import make_initial_state
from eng_loop.tools.policy_resolver import authorize_topology

# ───────────────────────────────────────────────────────────────────
# State matrix (complexity x ui x work_type)
# ───────────────────────────────────────────────────────────────────

STATE_MATRIX = [
    {"complexity": "small", "ui_project": False, "work_type": "feature"},
    {"complexity": "medium", "ui_project": False, "work_type": "feature"},
    {"complexity": "complex", "ui_project": False, "work_type": "feature"},
    {"complexity": "complex", "ui_project": True, "work_type": "feature"},
]

# Nodes handled by dedicated tests (deterministic or meta-state dependent)
PARITY_EXCLUDED = {"init-setup", "dynamic-architect", "meta-executor"}


def _make_state(artifact_root: str, parallel_qa: bool = False, **overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {"constraints": {}, "essence": {"enabled": False}}
    if parallel_qa:
        config["dynamic_graph"] = {"parallel_qa": True}
    state = make_initial_state(config, {"project_root": ".", "artifact_root": artifact_root})
    state.update(overrides)
    state["config"] = config
    return state


def _command_routed_names(graph: Any, registry: Any) -> set[str]:
    names = {spec.node_name for spec in registry.all_specs() if spec.routing == "command"}
    # qa-dispatcher / qa-join are not in the registry but also own routing via Command
    names |= {"qa-dispatcher", "qa-join"}
    return names


# ───────────────────────────────────────────────────────────────────
# 1. NodeSpec.routing default
# ───────────────────────────────────────────────────────────────────


class TestRoutingField:
    def test_all_registered_specs_default_to_command(self):
        registry = build_registry()
        for spec in registry.all_specs():
            assert spec.routing == "command", f"{spec.id} must own routing via Command"

    def test_routing_field_accepts_edges_value(self):
        from eng_loop.node_registry import NodeSpec

        spec = NodeSpec(id="x", node_name="x", handler=lambda s: {}, phase="test", routing="edges")
        assert spec.routing == "edges"


# ───────────────────────────────────────────────────────────────────
# 2. Compiled graphs: no declared edges out of command-routed nodes
# ───────────────────────────────────────────────────────────────────


class TestNoDeclaredEdgesOnCommandNodes:
    @pytest.mark.parametrize("state_cfg", STATE_MATRIX, ids=lambda c: f"{c['complexity']}-ui{int(c['ui_project'])}")
    @pytest.mark.parametrize("parallel_qa", [False, True], ids=["seq-qa", "par-qa"])
    def test_deterministic_graphs(self, tmp_path, state_cfg: dict, parallel_qa: bool):
        state = _make_state(str(tmp_path), parallel_qa=parallel_qa, **state_cfg)
        builder = GraphBuilder(parallel_qa=parallel_qa)
        graph, _ = builder.build(state)
        registry = build_registry(parallel_qa=parallel_qa)
        command_nodes = _command_routed_names(graph, registry)

        # No conditional edges (branches) on command-routed nodes
        for node_name, branches in graph.branches.items():
            assert node_name not in command_nodes or not branches, (
                f"command-routed node {node_name!r} has registered branches: {[b.name for b in branches]}"
            )

        # No fixed edges out of command-routed nodes (except START entry)
        for edge in graph.edges:
            src, dst = edge
            if dst == "__start__":
                continue
            assert src == "__start__" or src not in command_nodes, (
                f"fixed edge {src!r} -> {dst!r} declared on command-routed node {src!r}"
            )

    def test_proposal_graph(self, tmp_path):
        state = _make_state(str(tmp_path), complexity="medium", ui_project=False, work_type="feature")
        proposal = GraphTopologyProposal(
            plan_id="f1-parity",
            work_type="feature",
            complexity="medium",
            required_stages=("init", "impl.design", "impl.code", "verify", "qa.static", "deploy.prepare", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.design", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.design", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="verify", edge_type="fixed"),
                EdgeDefinition(from_stage="verify", to_stage="qa.static", edge_type="fixed"),
                EdgeDefinition(from_stage="qa.static", to_stage="deploy.prepare", edge_type="fixed"),
                EdgeDefinition(from_stage="deploy.prepare", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="IMPL", stages=("impl.design", "impl.code")),
                PhaseGroup(name="VERIFY", stages=("verify", "qa.static")),
                PhaseGroup(name="DEPLOY", stages=("deploy.prepare", "post")),
            ),
            rationale="Parity test proposal",
        )
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        graph, _ = builder.build(state, authorized_topology=authorized)
        registry = build_registry()
        command_nodes = _command_routed_names(graph, registry)

        for node_name, branches in graph.branches.items():
            assert node_name not in command_nodes or not branches, (
                f"command-routed node {node_name!r} has branches in proposal graph"
            )
        for edge in graph.edges:
            src, dst = edge
            assert src == "__start__" or src not in command_nodes, (
                f"fixed edge {src!r} -> {dst!r} out of command-routed node in proposal graph"
            )

    def test_parallel_qa_join_has_no_branches(self, tmp_path):
        state = _make_state(str(tmp_path), parallel_qa=True, complexity="medium", ui_project=False, work_type="feature")
        builder = GraphBuilder(parallel_qa=True)
        graph, _ = builder.build(state)
        assert "qa-join" in graph.nodes
        assert not graph.branches.get("qa-join"), "qa-join must route solely via Command"
        assert not graph.branches.get("qa-dispatcher"), "qa-dispatcher must route solely via Command"


# ───────────────────────────────────────────────────────────────────
# 3. Parity: handler gotos are valid declared destinations
# ───────────────────────────────────────────────────────────────────

STAGE_FAIL_STATES = {"verify", "e2e.execute", "qa.security", "qa.static", "deploy.prepare", "smoke.test"}


class TestHandlerGotoParity:
    """Each handler's Command goto must be a node registered in the graph (or END).

    Representative states per stage:
    - done: stage already complete (short-circuit path)
    - fresh: stage runs and the (mocked) agent returns PASS data
    - exhausted: attempts >= max (blocked/non-convergence path)
    - fail: agent returns FAIL verdict (rollback path) — verifier/QA/deploy only
    """

    @pytest.mark.parametrize("state_cfg", STATE_MATRIX, ids=lambda c: f"{c['complexity']}-ui{int(c['ui_project'])}")
    def test_goto_parity(self, tmp_path, state_cfg: dict):
        state = _make_state(str(tmp_path), **state_cfg)
        builder = GraphBuilder(parallel_qa=False)
        graph, _ = builder.build(state)
        valid = set(graph.nodes.keys()) | {"__end__"}
        registry = build_registry(parallel_qa=False)

        name_to_spec = {spec.node_name: spec for spec in registry.all_specs()}
        active_node_names = [n for n in graph.nodes if n in name_to_spec and n not in PARITY_EXCLUDED]

        for node_name in active_node_names:
            spec = name_to_spec[node_name]
            stage_id = spec.id
            for scenario in ("done", "fresh", "exhausted", "fail"):
                if scenario == "fail" and stage_id not in STAGE_FAIL_STATES:
                    continue
                cmd = self._invoke_handler(spec, stage_id, scenario, state)
                gotos = cmd.goto if isinstance(cmd.goto, list) else [cmd.goto]
                for goto in gotos:
                    target = goto.node if isinstance(goto, Send) else goto
                    assert target in valid, f"{node_name} [{scenario}]: goto {target!r} not in graph destinations"

    def _invoke_handler(self, spec: Any, stage_id: str, scenario: str, base_state: dict) -> Command:
        stages = {sid: dict(s) for sid, s in base_state["stages"].items()}
        if scenario == "done":
            stages[stage_id]["done"] = True
        elif scenario == "exhausted":
            stages[stage_id]["attempts"] = 5  # above any per-stage max
        state = dict(base_state)
        state["stages"] = stages

        def fake_run_agent(model, tools, prompt, stage_id, output_schema=None, max_iterations=25, config=None, **kw):
            from eng_loop.tools.agent_runner import AgentResult

            if scenario == "fail":
                data = {
                    "complete": True,
                    "valid": True,
                    "verdict": "FAIL",
                    "findings": ["synthetic failure"],
                    "critical_findings": ["synthetic critical"],
                    "gaps": ["synthetic gap"],
                    "errors": ["synthetic error"],
                    "severity": "critical",
                }
            else:
                data = {
                    "complete": True,
                    "valid": True,
                    "verdict": "PASS",
                    "findings": [],
                    "critical_findings": [],
                    "gaps": [],
                    "errors": [],
                    "blueprint": "x" * 60,
                    "tasks": ["t1", "t2"],
                    "implementation_summary": "ok",
                    "tests_passed": True,
                }
            return AgentResult(data=data, iterations=1, elapsed=0.01, tool_calls_made=1)

        with (
            patch("eng_loop.tools.agent_runner.run_agent", side_effect=fake_run_agent),
            patch("eng_loop.nodes.verification._check_e2e_prerequisites", return_value=None),
        ):
            return spec.handler(state)

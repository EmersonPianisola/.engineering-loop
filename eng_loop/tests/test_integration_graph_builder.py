from __future__ import annotations

"""Integration tests for graph builder work type filtering.

Validates that the graph builder correctly filters stages based on work type,
while allowing the architect to override complexity-based filtering.
"""

from eng_loop.edge_rules import build_edge_rules
from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import build_registry
from eng_loop.schemas import (
    AuthorizedGraphTopology,
    EdgeDefinition,
    ExecutionPolicy,
    GraphTopologyProposal,
    PhaseGroup,
)
from eng_loop.tools.policy_resolver import authorize_topology


def _make_state(
    complexity: str = "small",
    ui_project: bool = False,
    work_type: str = "feature",
) -> dict:
    return {
        "complexity": complexity,
        "ui_project": ui_project,
        "work_type": work_type,
        "stages": {},
        "errors": [],
    }


class TestGraphBuilderWorkTypeFiltering:
    def test_documentation_work_type_excludes_impl_design(self):
        """Documentation tasks should not include impl.design."""
        proposal = GraphTopologyProposal(
            plan_id="doc-test",
            work_type="documentation",
            complexity="small",
            required_stages=("init", "impl.design", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.design", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.design", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.design", "impl.code")),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Documentation task",
        )
        state = _make_state(work_type="documentation")
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        # impl.design should be filtered out for documentation
        assert "impl.design" not in topology.active_nodes
        # impl.code should remain (it's the stage that actually writes files)
        assert "impl.code" in topology.active_nodes
        assert "init" in topology.active_nodes
        assert "post" in topology.active_nodes

    def test_documentation_work_type_excludes_verify(self):
        """Documentation tasks should not include verify."""
        proposal = GraphTopologyProposal(
            plan_id="doc-verify-test",
            work_type="documentation",
            complexity="small",
            required_stages=("init", "impl.code", "verify", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="verify", edge_type="fixed"),
                EdgeDefinition(from_stage="verify", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="VERIFY", stages=("verify",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Documentation task",
        )
        state = _make_state(work_type="documentation")
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        assert "verify" not in topology.active_nodes
        assert "impl.code" in topology.active_nodes

    def test_operational_work_type_excludes_impl_code(self):
        """Operational tasks should not include impl.code."""
        proposal = GraphTopologyProposal(
            plan_id="ops-test",
            work_type="operational",
            complexity="small",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Operational task",
        )
        state = _make_state(work_type="operational")
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        assert "impl.code" not in topology.active_nodes
        assert "init" in topology.active_nodes
        assert "post" in topology.active_nodes

    def test_feature_work_type_no_filtering(self):
        """Feature tasks should not be filtered."""
        proposal = GraphTopologyProposal(
            plan_id="feature-test",
            work_type="feature",
            complexity="small",
            required_stages=("init", "impl.design", "impl.code", "verify", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.design", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.design", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="verify", edge_type="fixed"),
                EdgeDefinition(from_stage="verify", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.design", "impl.code")),
                PhaseGroup(name="VERIFY", stages=("verify",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Feature task",
        )
        state = _make_state(work_type="feature")
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        assert "impl.design" in topology.active_nodes
        assert "impl.code" in topology.active_nodes
        assert "verify" in topology.active_nodes

    def test_architect_can_override_complexity(self):
        """Architect can include arch stages for small complexity."""
        proposal = GraphTopologyProposal(
            plan_id="override-test",
            work_type="feature",
            complexity="small",
            required_stages=(
                "init",
                "init.refine",
                "arch.requirements",  # Would be excluded for small by deterministic
                "impl.code",
                "post",
            ),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="init.refine", edge_type="fixed"),
                EdgeDefinition(from_stage="init.refine", to_stage="arch.requirements", edge_type="fixed"),
                EdgeDefinition(from_stage="arch.requirements", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init", "init.refine")),
                PhaseGroup(name="ARCH", stages=("arch.requirements",)),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Architect overrides complexity-based filtering",
        )
        state = _make_state(complexity="small", work_type="feature")
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        # Architect can override complexity — arch.requirements should be included
        assert "arch.requirements" in topology.active_nodes
        assert "init" in topology.active_nodes
        assert "impl.code" in topology.active_nodes


class TestGraphBuilderDeterministic:
    def test_deterministic_filters_by_complexity(self):
        """Deterministic builder filters by complexity."""
        state = _make_state(complexity="small")
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert "arch.requirements" not in topology.active_nodes
        assert "design.user-research" not in topology.active_nodes

    def test_deterministic_filters_by_ui_project(self):
        """Deterministic builder filters E2E for non-UI projects."""
        state = _make_state(complexity="large", ui_project=False)
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert "e2e.execute" not in topology.active_nodes
        assert "smoke.test" not in topology.active_nodes

    def test_deterministic_includes_e2e_for_ui(self):
        """Deterministic builder includes E2E for UI projects."""
        state = _make_state(complexity="large", ui_project=True)
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert "e2e.execute" in topology.active_nodes
        assert "smoke.test" in topology.active_nodes

    def test_deterministic_documentation_excludes_verify(self):
        """Deterministic builder excludes verify for documentation."""
        state = _make_state(complexity="small", work_type="documentation")
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert "verify" not in topology.active_nodes
        assert "impl.design" not in topology.active_nodes
        assert "impl.code" in topology.active_nodes


class TestGraphBuilderTopologyMetadata:
    def test_topology_records_active_nodes(self):
        """Topology metadata correctly tracks active nodes."""
        state = _make_state(complexity="small")
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert len(topology.active_nodes) > 0
        assert "init" in topology.active_nodes
        assert "post" in topology.active_nodes

    def test_topology_records_complexity(self):
        """Topology metadata records complexity."""
        state = _make_state(complexity="medium")
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert topology.complexity == "medium"

    def test_topology_records_ui_project(self):
        """Topology metadata records UI project flag."""
        state = _make_state(ui_project=True)
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        assert topology.ui_project is True

    def test_topology_to_dict(self):
        """Topology can be serialized to dict."""
        state = _make_state()
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        d = topology.to_dict()
        assert "active_nodes" in d
        assert "edges" in d
        assert "complexity" in d
        assert "ui_project" in d

    def test_topology_to_json(self):
        """Topology can be serialized to JSON."""
        state = _make_state()
        builder = GraphBuilder()
        _graph, topology = builder.build(state)

        json_str = topology.to_json()
        assert isinstance(json_str, str)
        import json

        parsed = json.loads(json_str)
        assert "active_nodes" in parsed

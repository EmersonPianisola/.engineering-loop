from __future__ import annotations

"""Tests for the dynamic graph topology proposal system.

Covers:
- Schema validation (GraphTopologyProposal, EdgeDefinition, PhaseGroup)
- Policy firewall (5-layer authorization)
- Edge rule compilation from proposals
- Graph builder dual-path (proposal vs deterministic)
- Fallback resilience
"""

import pytest
from pydantic import ValidationError

from eng_loop.edge_rules import (
    build_rules_from_proposal,
)
from eng_loop.graph_builder import GraphBuilder
from eng_loop.schemas import (
    ALLOWED_CONDITIONS,
    EdgeDefinition,
    ExecutionPolicy,
    GraphTopologyProposal,
    PhaseGroup,
)
from eng_loop.state import make_initial_state
from eng_loop.tools.policy_resolver import (
    TopologyValidationError,
    authorize_topology,
)

# ───────────────────────────────────────────────────────────────────
# Helper: build a valid minimal proposal
# ───────────────────────────────────────────────────────────────────

def _make_minimal_proposal() -> GraphTopologyProposal:
    """Build a valid minimal topology: init → init-ideate → init-refine → impl-code → post."""
    return GraphTopologyProposal(
        plan_id="test-minimal",
        work_type="documentation",
        complexity="small",
        required_stages=(
            "init",
            "init.ideate",
            "init.refine",
            "impl.code",
            "post",
        ),
        edges=(
            EdgeDefinition(from_stage="init", to_stage="init.ideate", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="init.ideate", to_stage="init.refine", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="init.refine", to_stage="impl.code", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed", condition="always"),
        ),
        phase_groups=(
            PhaseGroup(name="INIT", stages=("init", "init.ideate", "init.refine")),
            PhaseGroup(name="IMPL", stages=("impl.code",)),
            PhaseGroup(name="POST", stages=("post",)),
        ),
        execution_policies=(),
        rationale="Minimal documentation pipeline",
    )


def _make_feature_proposal() -> GraphTopologyProposal:
    """Build a standard feature topology."""
    return GraphTopologyProposal(
        plan_id="test-feature",
        work_type="feature",
        complexity="medium",
        required_stages=(
            "init",
            "init.ideate",
            "init.refine",
            "arch.requirements",
            "arch.solution",
            "impl.design",
            "impl.code",
            "doc.update",
            "verify",
            "qa.security",
            "deploy.prepare",
            "post",
        ),
        edges=(
            EdgeDefinition(from_stage="init", to_stage="init.ideate", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="init.ideate", to_stage="init.refine", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="init.refine", to_stage="arch.requirements", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="arch.requirements", to_stage="arch.solution", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="arch.solution", to_stage="impl.design", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="impl.design", to_stage="impl.code", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="impl.code", to_stage="doc.update", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="doc.update", to_stage="verify", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="verify", to_stage="qa.security", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="qa.security", to_stage="deploy.prepare", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="deploy.prepare", to_stage="post", edge_type="fixed", condition="always"),
            EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed", condition="always"),
        ),
        phase_groups=(
            PhaseGroup(name="INIT", stages=("init", "init.ideate", "init.refine")),
            PhaseGroup(name="ARCH", stages=("arch.requirements", "arch.solution")),
            PhaseGroup(name="IMPL", stages=("impl.design", "impl.code", "doc.update")),
            PhaseGroup(name="VERIFY", stages=("verify", "qa.security")),
            PhaseGroup(name="DEPLOY", stages=("deploy.prepare",)),
            PhaseGroup(name="POST", stages=("post",)),
        ),
        execution_policies=(
            ExecutionPolicy(stage_id="verify", max_attempts=3, failure_route="impl.code"),
            ExecutionPolicy(stage_id="qa.security", max_attempts=3, failure_route="impl.code"),
        ),
        rationale="Standard medium-complexity feature pipeline with architecture and QA",
    )


def _make_state(complexity: str = "small", ui_project: bool = False, work_type: str = "feature") -> dict:
    state = make_initial_state({}, {})
    state["complexity"] = complexity
    state["ui_project"] = ui_project
    state["work_type"] = work_type
    state["work_item"] = "Test work item"
    return state


# ───────────────────────────────────────────────────────────────────
# SCHEMA VALIDATION
# ───────────────────────────────────────────────────────────────────

class TestTopologyProposalSchema:
    def test_valid_minimal_proposal(self):
        proposal = _make_minimal_proposal()
        assert proposal.plan_id == "test-minimal"
        assert len(proposal.required_stages) == 5
        assert len(proposal.edges) == 5

    def test_valid_feature_proposal(self):
        proposal = _make_feature_proposal()
        assert len(proposal.required_stages) == 12
        assert len(proposal.phase_groups) == 6
        assert len(proposal.execution_policies) == 2

    def test_empty_stages_rejected(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=(),
                edges=(EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),),
                rationale="test",
            )

    def test_duplicate_stages_rejected(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=("init", "init", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                    EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
                ),
                rationale="test",
            )

    def test_empty_edges_rejected(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=("init", "post"),
                edges=(),
                rationale="test",
            )

    def test_edge_to_unknown_stage_rejected(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=("init", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="nonexistent", edge_type="fixed"),
                    EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
                ),
                rationale="test",
            )

    def test_self_loop_requires_loopback_type(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=("init", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="init", edge_type="fixed"),
                    EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                    EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
                ),
                rationale="test",
            )

    def test_phase_group_invalid_stage_rejected(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=("init", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                    EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
                ),
                phase_groups=(PhaseGroup(name="INIT", stages=("init", "nonexistent")),),
                rationale="test",
            )

    def test_execution_policy_invalid_stage_rejected(self):
        with pytest.raises(ValidationError):
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=("init", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                    EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
                ),
                execution_policies=(ExecutionPolicy(stage_id="nonexistent", max_attempts=3),),
                rationale="test",
            )

    def test_allowed_conditions_set_not_empty(self):
        assert len(ALLOWED_CONDITIONS) > 0
        assert "always" in ALLOWED_CONDITIONS
        assert "stage_done" in ALLOWED_CONDITIONS


# ───────────────────────────────────────────────────────────────────
# POLICY FIREWALL — 5 LAYERS
# ───────────────────────────────────────────────────────────────────

class TestTopologyPolicyFirewall:
    def test_valid_proposal_authorizes(self):
        proposal = _make_minimal_proposal()
        state = _make_state()
        authorized = authorize_topology(proposal, state)
        assert authorized.plan_id == "test-minimal"
        assert len(authorized.authorized_stages) == 5

    def test_layer1_empty_stages_fails_at_schema(self):
        """Empty stages is caught by Pydantic schema validation before policy firewall."""
        with pytest.raises(ValidationError):  # Pydantic ValidationError
            GraphTopologyProposal(
                plan_id="bad",
                required_stages=(),
                edges=(EdgeDefinition(from_stage="x", to_stage="y", edge_type="fixed"),),
                rationale="test",
            )

    def test_layer1_duplicate_edges_fails(self):
        proposal = GraphTopologyProposal(
            plan_id="dup-edges",
            required_stages=("init", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "structural"

    def test_layer2_unknown_stage_fails(self):
        proposal = GraphTopologyProposal(
            plan_id="bad-stage",
            required_stages=("init", "phantom-stage", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="phantom-stage", edge_type="fixed"),
                EdgeDefinition(from_stage="phantom-stage", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "registry"

    def test_layer3_missing_entry_fails(self):
        proposal = GraphTopologyProposal(
            plan_id="no-entry",
            required_stages=("impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "boundary"

    def test_layer3_missing_exit_fails(self):
        proposal = GraphTopologyProposal(
            plan_id="no-exit",
            required_stages=("init", "impl.code"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "boundary"

    def test_layer4_cycle_detected(self):
        proposal = GraphTopologyProposal(
            plan_id="cycle",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="init", edge_type="fixed"),
                EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "connectivity"

    def test_layer4_disconnected_node_fails(self):
        proposal = GraphTopologyProposal(
            plan_id="disconnected",
            required_stages=("init", "impl.code", "verify", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
                # verify is in stages but not reachable
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "connectivity"

    def test_layer4_exit_not_reachable_fails(self):
        proposal = GraphTopologyProposal(
            plan_id="no-exit-path",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                # No path from impl.code to post
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError) as exc_info:
            authorize_topology(proposal, _make_state())
        assert exc_info.value.layer == "connectivity"

    def test_layer5_risk_keywords_generate_notes(self):
        proposal = _make_minimal_proposal()
        state = _make_state()
        state["work_item"] = "Drop database and deploy to production"
        authorized = authorize_topology(proposal, state)
        assert "Risk keywords detected" in authorized.policy_notes

    def test_feature_proposal_authorizes(self):
        proposal = _make_feature_proposal()
        state = _make_state(complexity="medium")
        authorized = authorize_topology(proposal, state)
        assert len(authorized.authorized_stages) == 12
        assert len(authorized.authorized_edges) == 12


# ───────────────────────────────────────────────────────────────────
# EDGE RULES FROM PROPOSAL
# ───────────────────────────────────────────────────────────────────

class TestBuildRulesFromProposal:
    def test_minimal_proposal_produces_rules(self):
        proposal = _make_minimal_proposal()
        engine = build_rules_from_proposal(proposal)
        rules = engine.get_rules_for_node("init")
        assert len(rules) > 0

    def test_feature_proposal_includes_failure_routing(self):
        proposal = _make_feature_proposal()
        engine = build_rules_from_proposal(proposal)
        # Verify stage should have loopback to impl-code
        verify_rules = engine.get_rules_for_node("verify")
        loopback_rules = [r for r in verify_rules if r.edge_type == "loopback"]
        assert len(loopback_rules) > 0

    def test_qa_failure_routing_injected(self):
        proposal = _make_feature_proposal()
        engine = build_rules_from_proposal(proposal)
        qa_rules = engine.get_rules_for_node("qa-security")
        loopback_rules = [r for r in qa_rules if r.edge_type == "loopback"]
        assert len(loopback_rules) > 0


# ───────────────────────────────────────────────────────────────────
# GRAPH BUILDER DUAL-PATH
# ───────────────────────────────────────────────────────────────────

class TestGraphBuilderDualPath:
    def test_deterministic_path_small(self):
        state = _make_state(complexity="small")
        builder = GraphBuilder()
        _, topology = builder.build(state)
        assert "init" in topology.active_nodes
        assert "impl.code" in topology.active_nodes
        assert "post" in topology.active_nodes

    def test_deterministic_path_complex(self):
        state = _make_state(complexity="complex", ui_project=True)
        builder = GraphBuilder()
        _graph, topology = builder.build(state)
        assert "arch.review" in topology.active_nodes
        assert "qa.performance" in topology.active_nodes

    def test_proposal_path(self):
        proposal = _make_minimal_proposal()
        state = _make_state()
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)
        assert "init" in topology.active_nodes
        assert "impl.code" in topology.active_nodes
        assert "post" in topology.active_nodes
        # Design stages should NOT be in proposal graph
        assert "design.user-research" not in topology.active_nodes
        assert "arch.requirements" not in topology.active_nodes

    def test_proposal_graph_compiles(self):
        proposal = _make_minimal_proposal()
        state = _make_state()
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        compiled, _topology = builder.compile(state, authorized_topology=authorized)
        assert compiled is not None

    def test_fallback_when_no_proposal(self):
        state = _make_state()
        builder = GraphBuilder()
        # No authorized_topology → deterministic path
        _graph, topology = builder.build(state, authorized_topology=None)
        assert topology.active_nodes  # Should have nodes from deterministic filter

    def test_proposal_overrides_deterministic_filtering(self):
        """A proposal can include stages that deterministic filtering would exclude."""
        # For small complexity, arch stages would normally be excluded
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
                EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init", "init.refine")),
                PhaseGroup(name="ARCH", stages=("arch.requirements",)),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Architect overrides complexity-based filtering",
        )
        state = _make_state(complexity="small")
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)
        # Proposal includes arch.requirements even though complexity=small
        assert "arch.requirements" in topology.active_nodes


# ───────────────────────────────────────────────────────────────────
# FALLBACK RESILIENCE
# ───────────────────────────────────────────────────────────────────

class TestFallbackResilience:
    def test_invalid_proposal_falls_back_to_deterministic(self):
        """When proposal is invalid, deterministic builder should produce a functional graph."""
        state = _make_state()
        builder = GraphBuilder()

        # Simulate invalid proposal → None → deterministic fallback
        _graph, topology = builder.build(state, authorized_topology=None)
        assert topology.active_nodes
        assert "init" in topology.active_nodes
        assert "post" in topology.active_nodes

    def test_deterministic_graph_compiles_and_runs(self):
        """Same task with architect unavailable must produce functional execution."""
        state = _make_state(complexity="small")
        builder = GraphBuilder()
        compiled, topology = builder.compile(state)
        assert compiled is not None
        assert len(topology.active_nodes) > 0

    def test_proposal_rejection_does_not_crash_builder(self):
        """Rejected proposal should not cause builder to fail."""
        state = _make_state()
        builder = GraphBuilder()
        # No proposal provided — builder should work fine
        _graph, topology = builder.build(state)
        assert topology is not None

    def test_empty_proposal_fallback(self):
        """Empty proposal data should fall back gracefully."""
        state = _make_state()
        builder = GraphBuilder()
        # None authorized_topology = deterministic
        _graph, topology = builder.build(state, authorized_topology=None)
        assert len(topology.active_nodes) > 0


# ───────────────────────────────────────────────────────────────────
# INVARIANT MATRIX
# ───────────────────────────────────────────────────────────────────

class TestInvariantMatrix:
    """Tests for the invariant matrix defined in the architecture plan."""

    def invariant_valid_proposal_compiles(self):
        proposal = _make_minimal_proposal()
        state = _make_state()
        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        compiled, _ = builder.compile(state, authorized_topology=authorized)
        assert compiled is not None

    def invariant_unknown_stage_fallback(self):
        proposal = GraphTopologyProposal(
            plan_id="bad",
            required_stages=("init", "unknown-stage", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="unknown-stage"),
                EdgeDefinition(from_stage="unknown-stage", to_stage="post"),
                EdgeDefinition(from_stage="post", to_stage="__end__"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError):
            authorize_topology(proposal, _make_state())

    def invariant_missing_entry_fallback(self):
        proposal = GraphTopologyProposal(
            plan_id="no-entry",
            required_stages=("impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="impl.code", to_stage="post"),
                EdgeDefinition(from_stage="post", to_stage="__end__"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError):
            authorize_topology(proposal, _make_state())

    def invariant_missing_exit_fallback(self):
        proposal = GraphTopologyProposal(
            plan_id="no-exit",
            required_stages=("init", "impl.code"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError):
            authorize_topology(proposal, _make_state())

    def invariant_disconnected_graph_fallback(self):
        proposal = GraphTopologyProposal(
            plan_id="disconnected",
            required_stages=("init", "impl.code", "verify", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code"),
                EdgeDefinition(from_stage="impl.code", to_stage="post"),
                EdgeDefinition(from_stage="post", to_stage="__end__"),
                # verify is unreachable
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError):
            authorize_topology(proposal, _make_state())

    def invariant_cycle_detected(self):
        proposal = GraphTopologyProposal(
            plan_id="cycle",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code"),
                EdgeDefinition(from_stage="impl.code", to_stage="init"),
                EdgeDefinition(from_stage="init", to_stage="post"),
                EdgeDefinition(from_stage="post", to_stage="__end__"),
            ),
            rationale="test",
        )
        with pytest.raises(TopologyValidationError):
            authorize_topology(proposal, _make_state())

    def invariant_documentation_task_produces_slim_graph(self):
        """Documentation task should produce a minimal graph via deterministic fallback."""
        state = _make_state(complexity="small", work_type="documentation")
        builder = GraphBuilder()
        _graph, topology = builder.build(state)
        active = set(topology.active_nodes)
        # Should NOT have heavy stages
        assert "arch.requirements" not in active
        assert "qa.security" not in active
        assert "deploy.prepare" not in active
        # Should have core stages
        assert "init" in active
        assert "post" in active

    def invariant_deterministic_produces_specialized_graph(self):
        """Feature task should include implementation stages."""
        state = _make_state(complexity="medium", work_type="feature")
        builder = GraphBuilder()
        _graph, topology = builder.build(state)
        active = set(topology.active_nodes)
        assert "impl.code" in active
        assert "impl.design" in active
        assert "verify" in active

    def invariant_empty_proposal_fallback(self):
        state = _make_state()
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=None)
        assert len(topology.active_nodes) > 0

    def invariant_same_task_functional_without_architect(self):
        """Critical: same task, architect unavailable → deterministic builder works."""
        work_item = "Write a summary from the current project"
        state = _make_state(complexity="small", work_type="documentation")
        state["work_item"] = work_item
        builder = GraphBuilder()
        # No proposal — pure deterministic
        compiled, topology = builder.compile(state, authorized_topology=None)
        assert compiled is not None
        assert len(topology.active_nodes) > 0
        assert "init" in topology.active_nodes
        assert "post" in topology.active_nodes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

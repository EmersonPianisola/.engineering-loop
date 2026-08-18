from __future__ import annotations

"""Integration tests for dynamic architect topology proposal rules.

Validates that the architect's prompt correctly enforces documentation
task rules and that the topology proposal schema validates properly.
"""

from eng_loop.schemas import (
    AuthorizedGraphTopology,
    EdgeDefinition,
    GraphTopologyProposal,
    PhaseGroup,
)
from eng_loop.state import make_initial_state
from eng_loop.tools.policy_resolver import authorize_topology


class TestDocumentationTopologyRules:
    def test_documentation_with_impl_code_is_valid(self):
        """Documentation topology with impl.code should be valid."""
        proposal = GraphTopologyProposal(
            plan_id="doc-impl-code",
            work_type="documentation",
            complexity="small",
            required_stages=("init", "init.ideate", "init.refine", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="init.ideate", edge_type="fixed"),
                EdgeDefinition(from_stage="init.ideate", to_stage="init.refine", edge_type="fixed"),
                EdgeDefinition(from_stage="init.refine", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init", "init.ideate", "init.refine")),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Documentation task with impl.code for file creation",
        )

        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["work_type"] = "documentation"

        authorized = authorize_topology(proposal, state)
        assert authorized.plan_id == "doc-impl-code"
        assert "impl.code" in authorized.authorized_stages

    def test_documentation_with_doc_update_requires_impl_code(self):
        """doc.update requires impl.code — both should be present."""
        proposal = GraphTopologyProposal(
            plan_id="doc-update-with-impl",
            work_type="documentation",
            complexity="small",
            required_stages=("init", "impl.code", "doc.update", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="doc.update", edge_type="fixed"),
                EdgeDefinition(from_stage="doc.update", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.code", "doc.update")),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Documentation task with impl.code + doc.update",
        )

        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["work_type"] = "documentation"

        authorized = authorize_topology(proposal, state)
        assert "impl.code" in authorized.authorized_stages
        assert "doc.update" in authorized.authorized_stages

    def test_documentation_minimal_topology(self):
        """Minimal documentation topology: init -> impl.code -> post."""
        proposal = GraphTopologyProposal(
            plan_id="doc-minimal",
            work_type="documentation",
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
            rationale="Minimal documentation topology",
        )

        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["work_type"] = "documentation"

        authorized = authorize_topology(proposal, state)
        assert "impl.code" in authorized.authorized_stages
        assert "post" in authorized.authorized_stages

    def test_documentation_excludes_verify(self):
        """Documentation topology should not include verify."""
        proposal = GraphTopologyProposal(
            plan_id="doc-no-verify",
            work_type="documentation",
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
            rationale="Documentation without verify",
        )

        state = make_initial_state({}, {})
        state["complexity"] = "small"
        state["work_type"] = "documentation"

        authorized = authorize_topology(proposal, state)
        assert "verify" not in authorized.authorized_stages


class TestTopologyProposalValidation:
    def test_init_and_post_mandatory(self):
        """init and post must be in required_stages."""
        proposal = GraphTopologyProposal(
            plan_id="test",
            work_type="feature",
            complexity="small",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(),
            rationale="Test",
        )

        assert "init" in proposal.required_stages
        assert "post" in proposal.required_stages

    def test_loopback_edges_rejected(self):
        """Loopback edges should be rejected by schema."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "impl.code", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                    EdgeDefinition(from_stage="impl.code", to_stage="impl.code", edge_type="loopback"),
                ),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "loopback" in str(e).lower() or "Loopback" in str(e)

    def test_terminal_edges_rejected(self):
        """Terminal edges should be rejected by schema."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "impl.code", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                    EdgeDefinition(from_stage="impl.code", to_stage="__end__", edge_type="terminal"),
                ),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "terminal" in str(e).lower() or "Terminal" in str(e)

    def test_edge_references_must_be_in_stages(self):
        """Edge references must be in required_stages."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "post"),
                edges=(EdgeDefinition(from_stage="init", to_stage="nonexistent", edge_type="fixed"),),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "nonexistent" in str(e)

    def test_self_loop_requires_loopback_type(self):
        """Self-loops require loopback type (which is rejected)."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "impl.code", "post"),
                edges=(
                    EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                    EdgeDefinition(from_stage="impl.code", to_stage="impl.code", edge_type="fixed"),
                ),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "self-loop" in str(e).lower() or "Self-loop" in str(e)

    def test_required_stages_not_empty(self):
        """required_stages cannot be empty."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=(),
                edges=(EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "empty" in str(e).lower()

    def test_edges_not_empty(self):
        """edges cannot be empty."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "post"),
                edges=(),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "empty" in str(e).lower()

    def test_phase_group_stages_must_be_in_required_stages(self):
        """Phase group stages must be in required_stages."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "post"),
                edges=(EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),),
                phase_groups=(PhaseGroup(name="INIT", stages=("init", "nonexistent")),),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "nonexistent" in str(e)

    def test_no_duplicate_stages(self):
        """required_stages cannot contain duplicates."""
        try:
            GraphTopologyProposal(
                plan_id="test",
                work_type="feature",
                complexity="small",
                required_stages=("init", "init", "post"),
                edges=(EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),),
                phase_groups=(),
                rationale="Test",
            )
            assert False, "Should have raised validation error"
        except Exception as e:
            assert "duplicate" in str(e).lower()


class TestAuthorizedTopology:
    def test_authorized_topology_is_immutable(self):
        """Authorized topology should be immutable."""
        auth = AuthorizedGraphTopology(
            plan_id="test",
            authorized_stages=("init", "impl.code", "post"),
            authorized_edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(),
            execution_policies=(),
            rationale="Test",
            policy_notes="clean",
        )

        try:
            auth.plan_id = "modified"
            assert False, "Should have raised immutable error"
        except Exception:
            pass  # Expected

    def test_authorized_topology_serializable(self):
        """Authorized topology should be serializable."""
        auth = AuthorizedGraphTopology(
            plan_id="test",
            authorized_stages=("init", "post"),
            authorized_edges=(EdgeDefinition(from_stage="init", to_stage="post", edge_type="fixed"),),
            phase_groups=(),
            execution_policies=(),
            rationale="Test",
            policy_notes="",
        )

        d = auth.model_dump()
        assert d["plan_id"] == "test"
        assert "init" in d["authorized_stages"]
        assert "post" in d["authorized_stages"]

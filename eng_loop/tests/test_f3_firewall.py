"""F3.6 — Topology firewall (L4/L5).

- L4: a self-loop loopback edge (which L1 explicitly allows) must not be
  rejected as a false cycle — self-edges reroute on failure, they never fork.
- L5: UI-only stages in a non-UI project are now FATAL (those stages can
  never activate, so the pipeline would block forever).
"""

from __future__ import annotations

import pytest

from eng_loop.schemas import EdgeDefinition, GraphTopologyProposal
from eng_loop.state import make_initial_state
from eng_loop.tools.policy_resolver import TopologyValidationError, authorize_topology


def _self_loop_proposal() -> GraphTopologyProposal:
    # model_construct: the raw LLM-proposal schema forbids loopback edges, but
    # the firewall must still be safe against them (L1 allows the self-loop
    # loopback specifically).
    return GraphTopologyProposal.model_construct(
        plan_id="self-loop",
        work_type="feature",
        complexity="small",
        required_stages=("init", "impl.code", "post"),
        edges=(
            EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
            EdgeDefinition(from_stage="impl.code", to_stage="impl.code", edge_type="loopback"),
            EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
        ),
        phase_groups=(),
        execution_policies=(),
        rationale="self-loop loopback proposal",
    )


def test_self_loop_loopback_passes_firewall() -> None:
    state = make_initial_state({}, {})
    authorized = authorize_topology(_self_loop_proposal(), state)
    assert authorized.plan_id == "self-loop"


def _ui_proposal() -> GraphTopologyProposal:
    return GraphTopologyProposal(
        plan_id="ui-stages",
        work_type="feature",
        complexity="medium",
        required_stages=("init", "impl.code", "e2e.execute", "post"),
        edges=(
            EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
            EdgeDefinition(from_stage="impl.code", to_stage="e2e.execute", edge_type="fixed"),
            EdgeDefinition(from_stage="e2e.execute", to_stage="post", edge_type="fixed"),
            EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
        ),
        rationale="UI feature pipeline",
    )


def test_ui_only_stage_non_ui_project_is_fatal() -> None:
    state = make_initial_state({}, {})
    state["ui_project"] = False
    with pytest.raises(TopologyValidationError) as exc_info:
        authorize_topology(_ui_proposal(), state)
    assert exc_info.value.layer == "semantic"
    assert "e2e.execute" in exc_info.value.message


def test_ui_only_stage_ui_project_authorizes() -> None:
    state = make_initial_state({}, {})
    state["ui_project"] = True
    authorized = authorize_topology(_ui_proposal(), state)
    assert authorized.plan_id == "ui-stages"

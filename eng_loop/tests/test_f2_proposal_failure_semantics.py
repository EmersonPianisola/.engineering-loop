"""F2.4 — H6/H7: proposal-path failure semantics.

- stage_done / stage_failed are per-stage predicates closed over the edge's
  from_stage (before: stage_done == `status != blocked`, stage_failed was
  dead `False`).
- Unknown conditions fail CLOSED (before: fail-open `True`).
- _route sorts by priority desc — loopback (10) beats happy-path (0).
"""

from __future__ import annotations

import logging

import pytest

from eng_loop.edge_rules import EdgeRule, _get_condition_predicate, build_rules_from_proposal
from eng_loop.graph_builder import GraphBuilder
from eng_loop.schemas import EdgeDefinition, GraphTopologyProposal

ACTIVE = {"init", "impl-design", "impl-code", "verify", "qa-static"}


def _proposal() -> GraphTopologyProposal:
    return GraphTopologyProposal(
        plan_id="test",
        work_type="feature",
        complexity="medium",
        required_stages=("init", "impl.design", "impl.code", "verify", "qa.static"),
        edges=(
            EdgeDefinition(
                from_stage="verify",
                to_stage="qa.static",
                edge_type="conditional",
                condition="stage_done",
            ),
        ),
        rationale="test",
    )


class TestConditionPredicates:
    def test_stage_done_requires_done_flag(self) -> None:
        p = _get_condition_predicate("stage_done", "verify")
        assert p({"stages": {"verify": {"done": True}}}) is True
        # Regression: the old predicate was `status != "blocked"` — a failed
        # (running) stage passed it and routed forward.
        assert p({"stages": {"verify": {"done": False}}, "status": "running"}) is False
        assert p({"stages": {}, "status": "running"}) is False

    def test_stage_failed_fires_when_not_done_and_not_blocked(self) -> None:
        p = _get_condition_predicate("stage_failed", "verify")
        assert p({"stages": {"verify": {"done": False}}, "status": "running"}) is True
        assert p({"stages": {"verify": {"done": True}}, "status": "running"}) is False
        assert p({"stages": {"verify": {"done": False}}, "status": "blocked"}) is False

    def test_unknown_condition_fails_closed(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="eng_loop.edge_rules"):
            p = _get_condition_predicate("totally_unknown")
        assert p({"status": "running"}) is False
        assert any("failing closed" in r.getMessage() for r in caplog.records)

    def test_stage_condition_without_stage_fails_closed(self) -> None:
        p = _get_condition_predicate("stage_done")
        assert p({"stages": {"verify": {"done": True}}}) is False


class TestProposalFailureRouting:
    def test_failed_verify_routes_to_loopback(self) -> None:
        engine = build_rules_from_proposal(_proposal())
        state = {"status": "running", "stages": {"verify": {"done": False, "attempts": 1}}}
        next_nodes = engine.get_next_nodes("verify", ACTIVE, state)
        assert "impl-code" in next_nodes  # injected loopback fires
        assert "qa-static" not in next_nodes  # stage_done must NOT fire for a failed stage

    def test_done_verify_routes_forward(self) -> None:
        engine = build_rules_from_proposal(_proposal())
        state = {"status": "running", "stages": {"verify": {"done": True}}}
        next_nodes = engine.get_next_nodes("verify", ACTIVE, state)
        assert "qa-static" in next_nodes
        assert "impl-code" not in next_nodes

    def test_blocked_verify_routes_to_end(self) -> None:
        engine = build_rules_from_proposal(_proposal())
        state = {"status": "blocked", "stages": {"verify": {"done": False}}}
        next_nodes = engine.get_next_nodes("verify", ACTIVE, state)
        assert "__end__" in next_nodes
        assert "impl-code" not in next_nodes  # loopback suppressed when blocked


class TestRoutePriority:
    def test_loopback_beats_happy_path(self) -> None:
        state = {"status": "running", "stages": {}}
        happy = EdgeRule(
            from_node="verify",
            to_node="qa-static",
            condition=lambda s: True,
            edge_type="conditional",
            priority=0,
        )
        loopback = EdgeRule(
            from_node="verify",
            to_node="impl-code",
            condition=lambda s: True,
            edge_type="loopback",
            priority=10,
        )
        # Happy path listed FIRST — before the fix, first match won and the
        # loopback never fired.
        assert GraphBuilder()._route([happy, loopback], state) == "impl-code"

    def test_happy_path_wins_when_loopback_not_matching(self) -> None:
        state = {"status": "running", "stages": {}}
        happy = EdgeRule(
            from_node="verify",
            to_node="qa-static",
            condition=lambda s: True,
            edge_type="conditional",
            priority=0,
        )
        loopback = EdgeRule(
            from_node="verify",
            to_node="impl-code",
            condition=lambda s: False,
            edge_type="loopback",
            priority=10,
        )
        assert GraphBuilder()._route([happy, loopback], state) == "qa-static"

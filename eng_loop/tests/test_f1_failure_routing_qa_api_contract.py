"""FASE 1.3 — Failure routing for hyphenated QA stage ids (qa.api-contract).

Before the fix, _inject_failure_routing derived stage_key from the node name
via a full hyphen->dot replace: "qa-api-contract" -> "qa.api.contract", which
is not a stage id. The injected loopback condition
`_stage_done(s, "qa.api.contract")` was therefore ALWAYS False and the
loopback fired even for a completed stage.

Now the loopback condition closes over the canonical dotted id from
proposal.required_stages.
"""

from __future__ import annotations

from typing import Any

from eng_loop.edge_rules import EdgeRule, build_rules_from_proposal
from eng_loop.schemas import EdgeDefinition, GraphTopologyProposal


def _proposal() -> GraphTopologyProposal:
    return GraphTopologyProposal(
        plan_id="f1-api-contract",
        work_type="feature",
        complexity="medium",
        required_stages=(
            "init",
            "impl.code",
            "verify",
            "qa.security",
            "qa.api-contract",
            "qa.human.flow",
            "deploy.prepare",
            "post",
        ),
        edges=(
            EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
            EdgeDefinition(from_stage="impl.code", to_stage="verify", edge_type="fixed"),
            EdgeDefinition(from_stage="verify", to_stage="qa.security", edge_type="fixed"),
            EdgeDefinition(from_stage="qa.security", to_stage="qa.api-contract", edge_type="fixed"),
            EdgeDefinition(from_stage="qa.api-contract", to_stage="qa.human.flow", edge_type="fixed"),
            EdgeDefinition(from_stage="qa.human.flow", to_stage="deploy.prepare", edge_type="fixed"),
            EdgeDefinition(from_stage="deploy.prepare", to_stage="post", edge_type="fixed"),
            EdgeDefinition(from_stage="post", to_stage="__end__", edge_type="fixed"),
        ),
        rationale="failure-routing test",
    )


def _loopback_rule(node_name: str) -> EdgeRule | None:
    engine = build_rules_from_proposal(_proposal())
    for rule in engine.get_rules_for_node(node_name):
        if rule.edge_type == "loopback":
            return rule
    return None


def _state(done_ids: tuple[str, ...] = (), blocked: bool = False) -> dict[str, Any]:
    return {
        "status": "blocked" if blocked else "running",
        "stages": {
            sid: {"done": sid in done_ids, "attempts": 1} for sid in ("qa.security", "qa.api-contract", "qa.human.flow")
        },
    }


class TestQaApiContractLoopback:
    def test_loopback_is_injected(self):
        rule = _loopback_rule("qa-api-contract")
        assert rule is not None
        assert rule.to_node == "impl-code"

    def test_done_stage_does_not_loopback(self):
        rule = _loopback_rule("qa-api-contract")
        assert rule is not None
        assert rule.evaluate(_state(done_ids=("qa.api-contract",))) is False

    def test_failed_stage_loops_back(self):
        rule = _loopback_rule("qa-api-contract")
        assert rule is not None
        assert rule.evaluate(_state()) is True

    def test_blocked_state_does_not_loopback(self):
        rule = _loopback_rule("qa-api-contract")
        assert rule is not None
        assert rule.evaluate(_state(blocked=True)) is False

    def test_condition_reads_canonical_key_only(self):
        # Regression for the pre-fix stage_key "qa.api.contract": a state where
        # ONLY the ghost key is done must NOT satisfy the condition.
        rule = _loopback_rule("qa-api-contract")
        assert rule is not None
        state = _state()
        state["stages"]["qa.api.contract"] = {"done": True, "attempts": 1}
        assert rule.evaluate(state) is True

    def test_multi_dot_stage_uses_canonical_id(self):
        rule = _loopback_rule("qa-human-flow")
        assert rule is not None
        assert rule.evaluate(_state(done_ids=("qa.human.flow",))) is False
        assert rule.evaluate(_state()) is True

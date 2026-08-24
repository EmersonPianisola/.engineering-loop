"""FASE 1.3 — qa-join rollback scope and heuristic key lookup.

Before the fix:
- the join looked up stages via `qa_node.replace("-", ".", 1)`, so
  "qa-human-flow" -> "qa.human-flow" (unknown) and the heuristic stage was
  always read as a phantom empty stage: the confidence check never fired and
  the stage became a phantom FAIL;
- the rollback target was the hardcoded node name "qa-performance", which is
  not a STAGE_ORDER id, so rollback_to_stage fell to its old dangerous
  default and reset EVERYTHING from impl.code to post.

Now the target is the first critically-failed QA stage (canonical dotted id)
and the reset is limited to impl.code -> target.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import eng_loop.nodes.qa_parallel as qp
from eng_loop.nodes.qa_parallel import qa_join_node

ACTIVE_NODES = ["qa-security", "qa-api-contract", "qa-human-flow"]


def _stage(done: bool, output: dict[str, Any] | None = None, verdict: str = "", status: str = "") -> dict[str, Any]:
    return {
        "done": done,
        "attempts": 1,
        "status": status,
        "verdict": verdict,
        "output": json.dumps(output) if output is not None else "",
    }


def _state(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stages: dict[str, dict[str, Any]] = {
        "impl.code": _stage(True),
        "doc.update": _stage(True),
        "verify": _stage(True),
        "qa.security": _stage(
            results["qa.security"]["verdict"] != "FAIL",
            results["qa.security"],
            verdict=results["qa.security"]["verdict"],
        ),
        "qa.api-contract": _stage(
            results["qa.api-contract"]["verdict"] != "FAIL",
            results["qa.api-contract"],
            verdict=results["qa.api-contract"]["verdict"],
        ),
        "qa.human.flow": _stage(
            results["qa.human.flow"]["verdict"] != "FAIL",
            results["qa.human.flow"],
            verdict=results["qa.human.flow"]["verdict"],
        ),
        "deploy.prepare": _stage(True),
        "post": _stage(True),
    }
    return {
        "stages": stages,
        "complexity": "medium",
        "ui_project": False,
        "config": {"constraints": {"max_fix_iterations": 3}, "qa_policy": {}},
        "fix_iteration": 0,
        "iteration": 10,
    }


def _run_join(results: dict[str, dict[str, Any]]):
    state = _state(results)
    with patch.object(qp, "_get_active_qa_nodes", return_value=ACTIVE_NODES):
        return qa_join_node(state)


PASS_SEC = {"verdict": "PASS", "findings": [], "critical_findings": []}
PASS_API = {"verdict": "PASS", "findings": [], "critical_findings": []}
PASS_FLOW = {"verdict": "PASS", "friction_score": 1.0, "confidence": 0.9, "persona_name": "Persona"}


class TestQaJoinRollbackScope:
    def test_critical_fail_resets_only_impl_code_chain_to_failing_stage(self):
        cmd = _run_join(
            {
                "qa.security": {
                    "verdict": "FAIL",
                    "severity": "critical",
                    "findings": ["SQL injection"],
                    "critical_findings": ["SQL injection"],
                },
                "qa.api-contract": PASS_API,
                "qa.human.flow": PASS_FLOW,
            }
        )
        assert cmd.goto == "impl-code"
        reset = cmd.update["stages"]
        # chain impl.code -> qa.security reset
        assert reset["impl.code"]["done"] is False
        assert reset["verify"]["done"] is False
        assert reset["qa.security"]["done"] is False
        # stages after the target untouched
        assert reset["qa.api-contract"]["done"] is True
        assert reset["qa.human.flow"]["done"] is True
        assert reset["deploy.prepare"]["done"] is True
        assert reset["post"]["done"] is True
        # the failing stage is the source of the fix tasks
        assert all(ft["source"] == "qa.security" for ft in cmd.update["fix_tasks"])

    def test_friction_exceeded_rolls_back_to_human_flow(self):
        cmd = _run_join(
            {
                "qa.security": PASS_SEC,
                "qa.api-contract": PASS_API,
                "qa.human.flow": {
                    "verdict": "FAIL",
                    "friction_score": 8.0,
                    "confidence": 0.9,
                    "persona_name": "Persona",
                },
            }
        )
        assert cmd.goto == "impl-code"
        reset = cmd.update["stages"]
        assert reset["qa.security"]["done"] is False  # in chain
        assert reset["qa.human.flow"]["done"] is False  # target
        assert reset["deploy.prepare"]["done"] is True  # untouched
        assert any(ft["source"] == "qa.human.flow" for ft in cmd.update["fix_tasks"])

    def test_low_confidence_heuristic_halts_instead_of_phantom_fail(self):
        # Regression (FASE 1.2 bug surfaced in 1.3): with the phantom lookup
        # the confidence check never fired; now it does and HALTs the pipeline
        # (low confidence = unreliable heuristic, not a code defect).
        cmd = _run_join(
            {
                "qa.security": PASS_SEC,
                "qa.api-contract": PASS_API,
                "qa.human.flow": {
                    "verdict": "PASS",
                    "friction_score": 1.0,
                    "confidence": 0.3,
                    "persona_name": "Persona",
                },
            }
        )
        assert cmd.goto == "__end__"
        assert cmd.update["status"] == "blocked"

    def test_all_pass_routes_to_deploy(self):
        cmd = _run_join({"qa.security": PASS_SEC, "qa.api-contract": PASS_API, "qa.human.flow": PASS_FLOW})
        assert cmd.goto == "deploy-prepare"

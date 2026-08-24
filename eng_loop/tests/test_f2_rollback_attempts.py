"""F2.2 — H2: rollback preserves cumulative attempts.

make_stage()/rollback_to_stage zero `attempts`, which used to disarm the
anti-loop guard in the contract gate forever. total_attempts is cumulative
and the guard considers it.
"""

from __future__ import annotations

from eng_loop.state import make_stage, rollback_to_stage
from eng_loop.tools.contract_gate import check_contract
from eng_loop.tools.fix_applier import _selective_rollback


class TestCumulativeAttempts:
    def test_selective_rollback_accumulates_total_attempts(self) -> None:
        stages = {"impl.code": {**make_stage(), "attempts": 2, "done": True, "status": "done"}}
        result = _selective_rollback({"stages": stages}, ["impl.code"])
        new_stage = result["stages"]["impl.code"]
        assert new_stage["attempts"] == 0  # local counter resets
        assert new_stage["total_attempts"] == 2  # cumulative preserved

    def test_selective_rollback_accumulates_over_cycles(self) -> None:
        stages = {"impl.code": {**make_stage(), "attempts": 2, "total_attempts": 3, "done": True}}
        result = _selective_rollback({"stages": stages}, ["impl.code"])
        assert result["stages"]["impl.code"]["total_attempts"] == 5  # 3 + 2

    def test_rollback_to_stage_accumulates_total_attempts(self) -> None:
        stages = {
            "impl.code": {**make_stage(), "attempts": 3, "done": True},
            "doc.update": {**make_stage(), "attempts": 1, "done": True},
            "verify": {**make_stage(), "attempts": 1, "done": True},
        }
        result = rollback_to_stage(stages, target_stage="verify", reset_from="impl.code")
        assert result["impl.code"]["attempts"] == 0
        assert result["impl.code"]["total_attempts"] == 3
        assert result["verify"]["total_attempts"] == 1


class TestContractGateCumulative:
    def test_blocks_after_cumulative_exhaustion(self) -> None:
        # Source exhausted in a PREVIOUS cycle: `attempts` was reset by the
        # rollback, but total_attempts carries the history.
        state = {
            "config": {"constraints": {"max_impl_code_attempts": 2}},
            "stages": {"impl.code": {**make_stage(), "attempts": 0, "total_attempts": 5}},
        }
        action, update = check_contract("impl-code", "doc-update", {"files_created": []}, state)
        assert action == "block"
        assert "attempts" in update["blocking_condition"]
        assert any("max attempts" in e for e in update["errors"])

    def test_allows_when_within_budget(self) -> None:
        state = {
            "config": {"constraints": {"max_impl_code_attempts": 5}},
            "stages": {"impl.code": {**make_stage(), "attempts": 1, "total_attempts": 1}},
        }
        action, _ = check_contract("impl-code", "doc-update", {"files_created": []}, state)
        assert action == "retry_source"

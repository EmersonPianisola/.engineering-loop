"""FASE 1.3 — Stage ID normalization and rollback fail-safety.

Covers:
- to_stage_id: the three accepted notations (dotted canonical, single-hyphen
  node name, multi-hyphen node name) and unknown inputs -> None.
- rollback_to_stage fail-safe: an unknown target/reset_from (after
  normalization) returns the stages UNCHANGED instead of the old dangerous
  defaults (start_idx=0 / end_idx=len-1 wiped everything).
- _selective_rollback: node names are normalized; all-invalid targets fall
  back to the impl.code -> current_stage chain instead of a silent no-op.
"""

from __future__ import annotations

from typing import Any

from eng_loop.state import STAGE_ORDER, init_stages, rollback_to_stage, to_stage_id
from eng_loop.tools.fix_applier import _selective_rollback


class TestToStageId:
    def test_canonical_dotted_ids_as_is(self):
        for sid in STAGE_ORDER:
            assert to_stage_id(sid) == sid

    def test_single_hyphen_node_names(self):
        assert to_stage_id("impl-code") == "impl.code"
        assert to_stage_id("deploy-prepare") == "deploy.prepare"
        assert to_stage_id("e2e-execute") == "e2e.execute"
        assert to_stage_id("smoke-test") == "smoke.test"

    def test_multi_hyphen_node_names(self):
        assert to_stage_id("qa-human-flow") == "qa.human.flow"
        assert to_stage_id("qa-human-ux") == "qa.human.ux"

    def test_first_hyphen_only_for_hyphenated_last_segment(self):
        # a full hyphen->dot replace would yield "qa.api.contract" (unknown)
        assert to_stage_id("qa-api-contract") == "qa.api-contract"

    def test_unknown_inputs_return_none(self):
        assert to_stage_id("qa.api.contract") is None
        assert to_stage_id("nonexistent") is None
        assert to_stage_id("ghost-stage") is None
        assert to_stage_id("") is None
        assert to_stage_id(None) is None


class TestRollbackFailSafe:
    def test_unknown_target_returns_stages_unchanged(self):
        stages = init_stages()
        stages["impl.code"]["done"] = True
        stages["verify"]["done"] = True
        result = rollback_to_stage(stages, target_stage="ghost-stage")
        assert result is not stages
        assert result["impl.code"]["done"] is True
        assert result["verify"]["done"] is True

    def test_unknown_reset_from_returns_stages_unchanged(self):
        stages = init_stages()
        stages["verify"]["done"] = True
        result = rollback_to_stage(stages, target_stage="verify", reset_from="ghost-stage")
        assert result["verify"]["done"] is True
        assert result["impl.code"]["done"] is False

    def test_node_names_are_normalized(self):
        # regression guard: hyphen node names are accepted (normalized),
        # not treated as unknown
        stages = init_stages()
        stages["impl.code"]["done"] = True
        stages["verify"]["done"] = True
        stages["qa.security"]["done"] = True
        stages["qa.api-contract"]["done"] = True
        result = rollback_to_stage(stages, "qa-security", reset_from="impl-code")
        assert result["impl.code"]["done"] is False
        assert result["verify"]["done"] is False
        assert result["qa.security"]["done"] is False
        # stage after the target untouched
        assert result["qa.api-contract"]["done"] is True

    def test_blocked_stages_never_reset(self):
        stages = init_stages()
        stages["impl.code"]["done"] = True
        stages["impl.code"]["status"] = "blocked"
        stages["verify"]["done"] = True
        result = rollback_to_stage(stages, "verify", "impl.code")
        assert result["impl.code"]["status"] == "blocked"
        assert result["impl.code"]["done"] is True
        assert result["verify"]["done"] is False


class TestSelectiveRollbackNormalization:
    @staticmethod
    def _state() -> dict[str, Any]:
        return {
            "current_stage": "qa-security",
            "stages": {
                "impl.code": {"done": True, "attempts": 3, "status": ""},
                "verify": {"done": True, "attempts": 1, "status": ""},
                "qa.security": {"done": False, "attempts": 2, "status": ""},
                "qa.api-contract": {"done": True, "attempts": 1, "status": ""},
            },
            "fix_tasks": [
                {"source": "qa-security", "gap": "g1"},
                {"source": "qa.security", "gap": "g2"},
                {"source": "verify", "gap": "g3"},
            ],
        }

    def test_node_names_are_normalized(self):
        result = _selective_rollback(self._state(), ["qa-security"])
        assert result["stages"]["qa.security"]["attempts"] == 0
        # selective: no chain reset
        assert result["stages"]["impl.code"]["done"] is True
        # fix_tasks sourced from the rolled-back stage are dropped under BOTH
        # the node name and the canonical id
        assert [ft["source"] for ft in result["fix_tasks"]] == ["verify"]

    def test_all_invalid_falls_back_to_chain(self, caplog):
        result = _selective_rollback(self._state(), ["ghost-stage", "another.ghost"])
        # chain impl.code -> current stage ("qa-security" -> qa.security)
        assert result["stages"]["impl.code"]["done"] is False
        assert result["stages"]["verify"]["done"] is False
        assert result["stages"]["qa.security"]["attempts"] == 0
        # stage after the target untouched
        assert result["stages"]["qa.api-contract"]["done"] is True
        assert any("falling back to chain rollback" in r.message for r in caplog.records)

    def test_mixed_valid_and_invalid_only_resets_valid(self, caplog):
        result = _selective_rollback(self._state(), ["qa-security", "ghost-stage"])
        assert result["stages"]["qa.security"]["attempts"] == 0
        # selective: the valid target prevents the chain fallback
        assert result["stages"]["impl.code"]["done"] is True
        assert any("discarded" in r.message for r in caplog.records)

    def test_all_invalid_and_unnormalizable_current_stage_is_noop(self, caplog):
        state = self._state()
        state["current_stage"] = "totally-unknown"
        result = _selective_rollback(state, ["ghost-stage"])
        assert result["stages"]["impl.code"]["done"] is True
        assert result["stages"]["qa.security"]["attempts"] == 2
        assert any("not normalizable" in r.message for r in caplog.records)

from __future__ import annotations

"""FASE 3A — Context slice, tier, consolidator gap tests."""

from eng_loop.tools.context_consolidator import build_handoff_summary, deduplicate_stage_artifacts
from eng_loop.tools.context_slice import CONTEXT_SLICE_RULES, build_context_slice


class TestContextSlice:
    def _state(self, artifacts=None):
        return {
            "work_item": "Implement auth",
            "stage_artifacts": artifacts or {"blueprint": "# Blueprint\nPlan for auth implementation"},
            "handoffs": {"init": "validated"},
            "decisions": [],
            "stages": {},
            "context_tiers": {},
        }

    def test_impl_code_slice(self):
        s = self._state()
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}
        result = build_context_slice("impl.code", s, paths, config)
        assert "# Context for stage: impl.code" in result

    def test_verify_slice(self):
        s = self._state()
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}
        result = build_context_slice("verify", s, paths, config)
        assert "# Context for stage: verify" in result

    def test_empty_artifacts(self):
        s = self._state(artifacts={})
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}
        result = build_context_slice("impl.code", s, paths, config)
        assert "# Context for stage: impl.code" in result

    def test_init_slice_no_artifacts(self):
        s = self._state()
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}
        result = build_context_slice("init", s, paths, config)
        assert "# Context for stage: init" in result

    def test_rules_exist_for_all_stages(self):
        from eng_loop.state import STAGE_ORDER
        for stage_id in STAGE_ORDER:
            assert stage_id in CONTEXT_SLICE_RULES, f"Missing rules for {stage_id}"


class TestContextConsolidator:
    def test_handoff_summary(self):
        r = build_handoff_summary("impl.code", {"implementation_summary": "Auth", "files_created": ["a.py"]}, ["Use OAuth2"])
        assert isinstance(r, str)
        assert len(r) > 0

    def test_handoff_empty(self):
        r = build_handoff_summary("verify", {}, [])
        assert isinstance(r, str)

    def test_deduplicate(self):
        a = {"impl.design": "bp v1", "impl.code": "s v1", "verify": "r v1"}
        d, _ = deduplicate_stage_artifacts(a)
        assert isinstance(d, dict)

    def test_deduplicate_removes_empty(self):
        a = {"impl.design": "c", "verify": ""}
        d, _ = deduplicate_stage_artifacts(a)
        assert "" not in d.values()

    def test_with_decisions(self):
        r = build_handoff_summary("arch.solution", {"architecture_output": "MS", "decisions": ["gRPC"]}, ["gRPC"])
        assert isinstance(r, str)


class TestHandoffs:
    def test_populated(self):
        s = {"handoffs": {}, "work_item": "T", "stages": {}, "stage_artifacts": {}}
        s["handoffs"]["init"] = build_handoff_summary("init", {"valid": True}, [])
        assert "init" in s["handoffs"]
        assert len(s["handoffs"]["init"]) > 0

    def test_multiple(self):
        s = {"handoffs": {}, "work_item": "T", "stages": {}, "stage_artifacts": {}}
        s["handoffs"]["init"] = build_handoff_summary("init", {"valid": True}, [])
        s["handoffs"]["impl.design"] = build_handoff_summary("impl.design", {"blueprint": "p"}, [])
        assert len(s["handoffs"]) == 2

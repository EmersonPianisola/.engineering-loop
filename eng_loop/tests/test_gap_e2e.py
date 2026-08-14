from __future__ import annotations

"""FASE 10 — End-to-end integration gap tests with mock LLM."""

import tempfile
from unittest.mock import MagicMock

from eng_loop.edge_rules import build_edge_rules
from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import build_registry
from eng_loop.state import make_initial_state, restore_snapshot


def _mr(data, error=None):
    m = MagicMock()
    m.data = data
    m.error = error
    m.iterations = 1
    m.elapsed = 0.5
    m.tool_calls_made = 2
    return m


def _fs(complexity="small", ui=False, wt="feature"):
    s = make_initial_state({}, {})
    s["work_item"] = "Implement feature"
    s["complexity"] = complexity
    s["ui_project"] = ui
    s["work_type"] = wt
    s["config"] = {
        "agent": {"max_agent_iterations": 5},
        "constraints": {"max_init_ideate_attempts": 3, "max_impl_code_attempts": 3, "max_verify_attempts": 3},
        "lessons": {"enabled": False},
    }
    s["paths"] = {"project_root": "/tmp/t", "artifact_root": "/tmp/t/.eng/a", "framework_stage_root": "", "framework_skill_root": ""}
    s["decisions"] = []
    s["errors"] = []
    s["handoffs"] = {}
    s["stage_artifacts"] = {}
    s["iteration"] = 0
    return s


class TestSmallFeatureFlow:
    def test_graph(self):
        reg = build_registry()
        s = _fs(complexity="small")
        builder = GraphBuilder(registry=reg)
        graph, topology = builder.build(s)
        nodes = list(graph.nodes)
        assert "init" in nodes
        assert "impl-code" in nodes
        assert "verify" in nodes
        assert "post" in nodes
        assert "design-user-research" not in nodes

    def test_routing(self):
        e = build_edge_rules()
        s = _fs(complexity="small")
        s["stages"]["init.refine"] = {"done": True, "attempts": 1}
        r = e.resolve({"init-refine", "impl-design", "arch-requirements"}, s)
        assert any(x.to_node == "impl-design" for x in r)


class TestMediumFeatureFlow:
    def test_includes_arch(self):
        reg = build_registry()
        s = _fs(complexity="medium")
        builder = GraphBuilder(registry=reg)
        graph, topology = builder.build(s)
        nodes = list(graph.nodes)
        assert "arch-requirements" in nodes
        assert "arch-solution" in nodes
        assert "qa-security" in nodes

    def test_arch_to_impl(self):
        e = build_edge_rules()
        s = _fs(complexity="medium")
        s["stages"]["arch.solution"] = {"done": True, "attempts": 1}
        r = e.resolve({"arch-solution", "impl-design", "arch-review"}, s)
        assert any(x.to_node == "impl-design" for x in r)


class TestDocumentationFlow:
    def test_excludes_stages(self):
        from eng_loop.tools.autosizing import DOCUMENTATION_EXCLUDED_STAGES
        from eng_loop.tools.next_active import _is_active
        s = _fs(wt="documentation")
        for sid in DOCUMENTATION_EXCLUDED_STAGES:
            assert not _is_active(sid, s)

    def test_includes_core(self):
        from eng_loop.tools.next_active import _is_active
        s = _fs(wt="documentation")
        assert _is_active("init", s)
        assert _is_active("impl.code", s)
        assert _is_active("post", s)


class TestOperationalFlow:
    def test_excludes_impl(self):
        from eng_loop.tools.autosizing import OPERATIONAL_EXCLUDED_STAGES
        from eng_loop.tools.next_active import _is_active
        s = _fs(wt="operational")
        for sid in OPERATIONAL_EXCLUDED_STAGES:
            assert not _is_active(sid, s)


class TestLoopbackFlow:
    def test_verify_fail(self):
        e = build_edge_rules()
        s = _fs()
        s["stages"]["verify"] = {"done": False, "attempts": 1}
        r = e.resolve({"verify", "impl-code"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)


class TestBlockedFlow:
    def test_terminates(self):
        e = build_edge_rules()
        s = _fs()
        s["status"] = "blocked"
        r = e.resolve({"init", "__end__"}, s)
        assert any(x.to_node == "__end__" for x in r)

    def test_impl_blocked(self):
        e = build_edge_rules()
        s = _fs()
        s["status"] = "blocked"
        r = e.resolve({"impl-code", "__end__"}, s)
        assert any(x.to_node == "__end__" for x in r)


class TestGraphBypass:
    def test_skips_bdd(self):
        from eng_loop.tools.next_active import _is_active
        s = _fs(complexity="small")
        assert not _is_active("init.bdd", s)

    def test_bypass_routing(self):
        e = build_edge_rules()
        s = _fs(complexity="small")
        s["stages"]["init.ideate"] = {"done": True, "attempts": 1}
        r = e.resolve_with_bypass({"init-ideate", "init-refine", "__start__"}, s)
        bp = [x for x in r if x.edge_type == "bypass"]
        assert any(x.from_node == "init-ideate" and x.to_node == "init-refine" for x in bp)


class TestStatePersistence:
    def test_save_restore(self):
        from eng_loop.tools.state_history import save_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            s = _fs(complexity="medium")
            s["stages"]["init"] = {"done": True, "attempts": 1}
            paths = {"artifact_root": tmp}
            p = save_snapshot(s, paths, "init")
            r = restore_snapshot(str(p))
            assert r["complexity"] == "medium"
            assert r["stages"]["init"]["done"]

    def test_roundtrip(self):
        from eng_loop.tools.state_history import save_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            s = _fs()
            s["decisions"] = ["D1", "D2"]
            s["handoffs"] = {"init": "validated"}
            paths = {"artifact_root": tmp}
            p = save_snapshot(s, paths, "init")
            r = restore_snapshot(str(p))
            assert r["decisions"] == ["D1", "D2"]
            assert r["handoffs"]["init"] == "validated"


class TestHUDIntegration:
    def test_receives_events(self):
        from rich.console import Console

        from eng_loop.tools.hud import HUDRenderer
        c = Console(force_terminal=True)
        r = HUDRenderer(console=c)
        r.log("INFO", "test")
        assert len(r.action_log.lines) == 1

    def test_stage_tracking(self):
        from rich.console import Console

        from eng_loop.tools.hud import HUDRenderer
        c = Console(force_terminal=True)
        r = HUDRenderer(console=c)
        r.set_current_stage("init")
        assert r._current_stage == "init"
        r.clear_current_stage()
        assert r._current_stage == ""


class TestContextHandoff:
    def test_data_flows(self):
        from eng_loop.tools.context_consolidator import build_handoff_summary
        h = build_handoff_summary("init", {"valid": True, "work_item_refined": "R"}, [])
        assert isinstance(h, str)
        assert len(h) > 0

    def test_accumulates(self):
        from eng_loop.tools.context_consolidator import build_handoff_summary
        hs = {}
        hs["init"] = build_handoff_summary("init", {"valid": True}, [])
        hs["impl.design"] = build_handoff_summary("impl.design", {"blueprint": "p"}, [])
        hs["impl.code"] = build_handoff_summary("impl.code", {"summary": "d"}, [])
        assert len(hs) == 3

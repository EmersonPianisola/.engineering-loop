from __future__ import annotations

"""FASE 2D — Routing gap scenarios: loopback, work_type, large+UI, bypass."""

from eng_loop.edge_rules import build_edge_rules


def _ms(complexity="small", ui=False, status="", stages=None, wt="feature"):
    s = {"complexity": complexity, "ui_project": ui, "stages": stages or {}}
    if status:
        s["status"] = status
    if wt != "feature":
        s["work_type"] = wt
    return s


class TestLoopbackRouting:
    def test_verify_fail(self):
        engine = build_edge_rules()
        s = _ms(stages={"verify": {"done": False, "attempts": 1}})
        r = engine.resolve({"verify", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)

    def test_e2e_fail(self):
        engine = build_edge_rules()
        s = _ms(complexity="medium", ui=True, stages={"e2e.execute": {"done": False, "attempts": 1}})
        r = engine.resolve({"e2e-execute", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)

    def test_qa_security_fail(self):
        engine = build_edge_rules()
        s = _ms(complexity="medium", stages={"qa.security": {"done": False, "attempts": 1}})
        r = engine.resolve({"qa-security", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)

    def test_qa_api_fail(self):
        engine = build_edge_rules()
        s = _ms(complexity="complex", stages={"qa.api-contract": {"done": False, "attempts": 1}})
        r = engine.resolve({"qa-api-contract", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)

    def test_qa_perf_fail(self):
        engine = build_edge_rules()
        s = _ms(complexity="complex", stages={"qa.performance": {"done": False, "attempts": 1}})
        r = engine.resolve({"qa-performance", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)

    def test_deploy_fail(self):
        engine = build_edge_rules()
        s = _ms(stages={"deploy.prepare": {"done": False, "attempts": 1}})
        r = engine.resolve({"deploy-prepare", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)

    def test_smoke_fail(self):
        engine = build_edge_rules()
        s = _ms(complexity="medium", ui=True, stages={"smoke.test": {"done": False, "attempts": 1}})
        r = engine.resolve({"smoke-test", "impl-code", "__end__"}, s)
        lb = [x for x in r if x.edge_type == "loopback"]
        assert any(x.to_node == "impl-code" for x in lb)


class TestWorkTypeRouting:
    def test_documentation(self):
        from eng_loop.tools.autosizing import DOCUMENTATION_EXCLUDED_STAGES
        from eng_loop.tools.next_active import _is_active
        s = _ms(wt="documentation")
        assert _is_active("init", s)
        assert _is_active("impl.code", s)
        assert _is_active("post", s)
        for sid in DOCUMENTATION_EXCLUDED_STAGES:
            assert not _is_active(sid, s), f"{sid} excluded for doc"

    def test_operational(self):
        from eng_loop.tools.autosizing import OPERATIONAL_EXCLUDED_STAGES
        from eng_loop.tools.next_active import _is_active
        s = _ms(wt="operational")
        assert _is_active("init", s)
        for sid in OPERATIONAL_EXCLUDED_STAGES:
            assert not _is_active(sid, s), f"{sid} excluded for ops"

    def test_bugfix(self):
        from eng_loop.tools.next_active import _is_active
        s = _ms(wt="bugfix")
        for sid in ["design.user-research", "design.personas", "design.info-arch", "design.interaction", "design.design-system", "design.visual-design"]:
            assert not _is_active(sid, s), f"{sid} excluded for bugfix"
        assert _is_active("impl.code", s)
        assert _is_active("verify", s)


class TestLargeUIFlow:
    def test_all_nodes_active(self):
        from eng_loop.tools.next_active import _is_active
        s = _ms(complexity="complex", ui=True)
        for sid in ["init", "init.ideate", "init.bdd", "init.refine", "design.user-research", "design.personas", "design.info-arch", "design.interaction", "design.design-system", "design.visual-design", "arch.requirements", "arch.solution", "arch.review", "impl.design", "impl.code", "doc.update", "verify", "e2e.execute", "qa.security", "qa.api-contract", "qa.performance", "deploy.prepare", "smoke.test", "doc.decisions", "doc.project", "post"]:
            assert _is_active(sid, s), f"{sid} should be active for complex+UI"

    def test_verify_to_e2e(self):
        engine = build_edge_rules()
        s = _ms(complexity="large", ui=True, stages={"verify": {"done": True, "attempts": 1}})
        r = engine.resolve({"verify", "e2e-execute", "qa-security", "deploy-prepare"}, s)
        assert any(x.to_node == "e2e-execute" for x in r)

    def test_e2e_to_qa(self):
        engine = build_edge_rules()
        s = _ms(complexity="large", ui=True, stages={"e2e.execute": {"done": True, "attempts": 1}})
        r = engine.resolve({"e2e-execute", "qa-security", "deploy-prepare"}, s)
        assert any(x.to_node == "qa-security" for x in r)

    def test_deploy_to_smoke(self):
        engine = build_edge_rules()
        s = _ms(complexity="large", ui=True, stages={"deploy.prepare": {"done": True, "attempts": 1}})
        r = engine.resolve({"deploy-prepare", "smoke-test", "doc-decisions", "post"}, s)
        assert any(x.to_node == "smoke-test" for x in r)


class TestBypassRouting:
    def test_bypass_init_bdd_small(self):
        engine = build_edge_rules()
        s = _ms(stages={"init.ideate": {"done": True, "attempts": 1}})
        r = engine.resolve_with_bypass({"init-ideate", "init-refine", "__start__"}, s)
        bp = [x for x in r if x.edge_type == "bypass"]
        assert any(x.from_node == "init-ideate" and x.to_node == "init-refine" for x in bp)

    def test_bypass_design_small(self):
        engine = build_edge_rules()
        s = _ms(stages={"init.refine": {"done": True, "attempts": 1}})
        r = engine.resolve({"init-refine", "impl-design"}, s)
        assert any(x.to_node == "impl-design" for x in r)

    def test_bypass_arch_review_small(self):
        engine = build_edge_rules()
        s = _ms(stages={"arch.solution": {"done": True, "attempts": 1}})
        r = engine.resolve({"arch-solution", "impl-design"}, s)
        assert any(x.to_node == "impl-design" for x in r)

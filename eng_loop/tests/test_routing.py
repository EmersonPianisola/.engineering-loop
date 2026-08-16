from __future__ import annotations

"""Tests for edge rule conditions and routing logic."""

from eng_loop.edge_rules import (
    EdgeRule,
    EdgeRulesEngine,
    _complexity_at_least,
    _complexity_is,
    _is_blocked,
    _is_ui_project,
    _stage_done,
    _stage_failed,
    build_edge_rules,
)

# ============================================================
# EDGE RULE HELPERS
# ============================================================


class TestStageDone:
    def test_stage_done_true(self):
        state = {"stages": {"init": {"done": True}}}
        assert _stage_done(state, "init") is True

    def test_stage_done_false(self):
        state = {"stages": {"init": {"done": False}}}
        assert _stage_done(state, "init") is False

    def test_stage_missing(self):
        state = {"stages": {}}
        assert _stage_done(state, "init") is False


class TestStageFailed:
    def test_stage_failed(self):
        state = {"stages": {"verify": {"done": False, "attempts": 3}}}
        assert _stage_failed(state, "verify") is True

    def test_stage_done_not_failed(self):
        state = {"stages": {"verify": {"done": True, "attempts": 1}}}
        assert _stage_failed(state, "verify") is False

    def test_stage_no_attempts(self):
        state = {"stages": {"verify": {"done": False, "attempts": 0}}}
        assert _stage_failed(state, "verify") is False


class TestComplexityConditions:
    def test_complexity_is(self):
        assert _complexity_is({"complexity": "small"}, "small") is True
        assert _complexity_is({"complexity": "small"}, "medium") is False
        assert _complexity_is({"complexity": "complex"}, "complex") is True

    def test_complexity_at_least(self):
        assert _complexity_at_least({"complexity": "complex"}, "medium") is True
        assert _complexity_at_least({"complexity": "small"}, "medium") is False
        assert _complexity_at_least({"complexity": "medium"}, "medium") is True

    def test_default_complexity(self):
        assert _complexity_is({}, "small") is True
        assert _complexity_at_least({}, "small") is True


class TestUIProject:
    def test_ui_project_true(self):
        assert _is_ui_project({"ui_project": True}) is True

    def test_ui_project_false(self):
        assert _is_ui_project({"ui_project": False}) is False

    def test_ui_project_missing(self):
        assert _is_ui_project({}) is False


class TestIsBlocked:
    def test_blocked(self):
        assert _is_blocked({"status": "blocked"}) is True

    def test_not_blocked(self):
        assert _is_blocked({"status": "running"}) is False

    def test_no_status(self):
        assert _is_blocked({}) is False


# ============================================================
# EDGE RULE ENGINE
# ============================================================


class TestEdgeRule:
    def test_fixed_rule_matches(self):
        rule = EdgeRule(from_node="init", to_node="init-ideate", edge_type="fixed")
        assert rule.matches("init") is True
        assert rule.matches("other") is False

    def test_wildcard_matches(self):
        rule = EdgeRule(from_node="*", to_node="__end__", edge_type="fixed")
        assert rule.matches("any-node") is True

    def test_evaluate_no_condition(self):
        rule = EdgeRule(from_node="init", to_node="post", edge_type="fixed")
        assert rule.evaluate({}) is True

    def test_evaluate_with_condition(self):
        rule = EdgeRule(
            from_node="init",
            to_node="post",
            condition=lambda s: s.get("done", False),
        )
        assert rule.evaluate({"done": True}) is True
        assert rule.evaluate({"done": False}) is False


class TestEdgeRulesEngine:
    def test_add_fixed(self):
        engine = EdgeRulesEngine()
        engine.add_fixed("a", "b", "description")
        assert len(engine._rules) == 1

    def test_add_conditional(self):
        engine = EdgeRulesEngine()
        engine.add_conditional("a", "b", lambda s: True, description="test")
        assert len(engine._rules) == 1
        assert engine._rules[0].edge_type == "conditional"

    def test_add_loopback(self):
        engine = EdgeRulesEngine()
        engine.add_loopback("verify", "impl-code", lambda s: True, "retry")
        assert engine._rules[0].edge_type == "loopback"
        assert engine._rules[0].priority == 10

    def test_resolve_filters_by_active_nodes(self):
        engine = EdgeRulesEngine()
        engine.add_fixed("init", "impl-code")
        engine.add_fixed("init", "arch-requirements")
        active = {"init", "impl-code"}
        state = {}
        resolved = engine.resolve(active, state)
        assert len(resolved) == 1
        assert resolved[0].to_node == "impl-code"

    def test_get_next_nodes(self):
        engine = EdgeRulesEngine()
        engine.add_fixed("init", "impl-code")
        engine.add_fixed("init", "verify")
        next_nodes = engine.get_next_nodes("init", {"init", "impl-code", "verify"}, {})
        assert "impl-code" in next_nodes
        assert "verify" in next_nodes

    def test_get_applicable_rules(self):
        engine = EdgeRulesEngine()
        engine.add_conditional("init", "impl-code", lambda s: s.get("small", False))
        engine.add_conditional("init", "arch", lambda s: s.get("large", False))
        applicable = engine.get_applicable_rules({"init", "impl-code", "arch"})
        assert len(applicable) == 2


class TestBuildEdgeRules:
    def test_entry_point_exists(self):
        engine = build_edge_rules()
        rules = engine.get_rules_for_node("__start__")
        assert any(r.to_node == "init-setup" for r in rules)

    def test_init_has_two_paths(self):
        engine = build_edge_rules()
        rules = engine.get_rules_for_node("init")
        assert any(r.to_node == "init-ideate" for r in rules)
        assert any(r.to_node == "__end__" for r in rules)

    def test_post_ends(self):
        engine = build_edge_rules()
        rules = engine.get_rules_for_node("post")
        assert any(r.to_node == "__end__" for r in rules)

    def test_verify_loopback(self):
        engine = build_edge_rules()
        rules = engine.get_rules_for_node("verify")
        loopbacks = [r for r in rules if r.edge_type == "loopback"]
        assert any(r.to_node == "impl-code" for r in loopbacks)

    def test_parallel_qa_flag(self):
        engine_seq = build_edge_rules(parallel_qa=False)
        build_edge_rules(parallel_qa=True)
        # Sequential should have QA loopback rules
        qa_rules_seq = engine_seq.get_rules_for_node("qa-security")
        assert len(qa_rules_seq) > 0


# ============================================================
# ROUTING SCENARIOS
# ============================================================


class TestRoutingScenarios:
    def test_small_complexity_flow(self):
        engine = build_edge_rules()
        state = {
            "complexity": "small",
            "ui_project": False,
            "stages": {
                "init": {"done": True, "attempts": 1},
                "init.refine": {"done": True, "attempts": 1},
            },
        }
        active = {
            "init",
            "init-ideate",
            "init-refine",
            "impl-design",
            "impl-code",
            "verify",
            "deploy-prepare",
            "post",
            "__end__",
        }
        resolved = engine.resolve(active, state)
        assert len(resolved) > 0

    def test_medium_complexity_flow(self):
        engine = build_edge_rules()
        state = {
            "complexity": "medium",
            "ui_project": False,
            "stages": {
                "init": {"done": True},
                "init.refine": {"done": True},
            },
        }
        active = {
            "init",
            "init-refine",
            "arch-requirements",
            "arch-solution",
            "impl-design",
            "impl-code",
            "verify",
            "qa-security",
            "deploy-prepare",
            "post",
            "__end__",
        }
        resolved = engine.resolve(active, state)
        assert len(resolved) > 0

    def test_blocked_terminates(self):
        engine = build_edge_rules()
        state = {"status": "blocked"}
        active = {"init", "__end__"}
        resolved = engine.resolve(active, state)
        assert any(r.to_node == "__end__" for r in resolved)

    def test_complex_complexity_flow(self):
        engine = build_edge_rules()
        state = {
            "complexity": "complex",
            "ui_project": True,
            "stages": {
                "arch.solution": {"done": True},
            },
        }
        active = {"arch-solution", "arch-review", "impl-design", "__end__"}
        resolved = engine.resolve(active, state)
        assert any(r.to_node == "arch-review" for r in resolved)

    def test_bypass_inactive_nodes(self):
        engine = build_edge_rules()
        state = {
            "complexity": "small",
            "ui_project": False,
            "stages": {
                "init": {"done": True},
                "init.ideate": {"done": True},
            },
        }
        # init-bdd is inactive for small, should be bypassed
        active = {"init", "init-ideate", "init-refine"}
        resolved = engine.resolve_with_bypass(active | {"__start__"}, state)
        bypass_rules = [r for r in resolved if r.edge_type == "bypass"]
        # init-ideate should bypass init-bdd to reach init-refine
        assert any(r.from_node == "init-ideate" and r.to_node == "init-refine" for r in bypass_rules)

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class EdgeRule:
    """Declarative rule for connecting nodes in the dynamic graph."""
    from_node: str
    to_node: str
    condition: Callable[[dict[str, Any]], bool] | None = None
    edge_type: str = "fixed"
    priority: int = 0
    description: str = ""

    def matches(self, from_node_id: str) -> bool:
        return self.from_node == "*" or self.from_node == from_node_id

    def evaluate(self, state: dict[str, Any]) -> bool:
        if self.condition is None:
            return True
        return self.condition(state)


class EdgeRulesEngine:
    """Resolves edges between active nodes based on rules and state."""

    def __init__(self):
        self._rules: list[EdgeRule] = []

    def add(self, rule: EdgeRule) -> None:
        self._rules.append(rule)

    def add_fixed(self, from_node: str, to_node: str, description: str = "") -> None:
        self.add(EdgeRule(
            from_node=from_node, to_node=to_node,
            edge_type="fixed", description=description,
        ))

    def add_conditional(
        self,
        from_node: str,
        to_node: str,
        condition: Callable[[dict[str, Any]], bool],
        edge_type: str = "conditional",
        description: str = "",
    ) -> None:
        self.add(EdgeRule(
            from_node=from_node, to_node=to_node,
            condition=condition, edge_type=edge_type, description=description,
        ))

    def add_loopback(
        self,
        from_node: str,
        to_node: str,
        condition: Callable[[dict[str, Any]], bool],
        description: str = "",
    ) -> None:
        self.add(EdgeRule(
            from_node=from_node, to_node=to_node,
            condition=condition, edge_type="loopback", priority=10,
            description=description,
        ))

    def resolve(
        self,
        active_node_ids: set[str],
        state: dict[str, Any],
    ) -> list[EdgeRule]:
        """Return only the rules applicable to the active nodes and current state."""
        result = []
        for rule in self._rules:
            if rule.from_node not in active_node_ids and rule.from_node != "*":
                continue
            if rule.to_node not in active_node_ids and rule.to_node not in ("__end__",):
                continue
            if rule.evaluate(state):
                result.append(rule)
        return result

    def get_applicable_rules(
        self,
        active_node_ids: set[str],
    ) -> list[EdgeRule]:
        """Return rules with valid source/target nodes, WITHOUT evaluating conditions.

        Used for building conditional edges — all possible targets must be declared
        upfront so the branch lookup succeeds at runtime, regardless of which
        condition evaluates to True.
        """
        result = []
        for rule in self._rules:
            if rule.from_node not in active_node_ids and rule.from_node != "*":
                continue
            if rule.to_node not in active_node_ids and rule.to_node not in ("__end__",):
                continue
            result.append(rule)
        return result

    def get_next_nodes(
        self,
        from_node: str,
        active_node_ids: set[str],
        state: dict[str, Any],
    ) -> list[str]:
        """Get the next node(s) for a given source node."""
        next_nodes = []
        for rule in self._rules:
            if not rule.matches(from_node):
                continue
            if rule.to_node not in active_node_ids and rule.to_node != "__end__":
                continue
            if rule.evaluate(state):
                next_nodes.append(rule.to_node)
        return next_nodes

    def get_rules_for_node(self, from_node: str) -> list[EdgeRule]:
        return [r for r in self._rules if r.matches(from_node)]

    def resolve_with_bypass(
        self,
        active_node_ids: set[str],
        state: dict[str, Any],
    ) -> list[EdgeRule]:
        """Resolve rules, bypassing inactive intermediate nodes.

        When a rule targets an inactive node, follows the chain of outgoing
        rules from that node until reaching an active target or __end__.
        Returns the resolved rules with inactive intermediaries skipped.

        Loopback edges (fail → retry) are NEVER bypassed — they are failure
        recovery paths, not forward-progress edges. If a loopback target is
        inactive, the rule is dropped entirely.

        Example: init-ideate -> init-bdd -> init-refine
        If init-bdd is inactive, resolves to: init-ideate -> init-refine
        """
        resolved = []
        visited_bypasses: set[tuple[str, str]] = set()

        for rule in self._rules:
            # Skip rules whose source is not active (and not wildcard)
            if rule.from_node not in active_node_ids and rule.from_node != "*":
                continue

            target = rule.to_node

            # If target is active or __end__, keep as-is
            if target in active_node_ids or target == "__end__":
                resolved.append(rule)
                continue

            # Loopback edges target inactive node — drop them entirely.
            # They are fail-recovery paths; if the recovery target is gone,
            # the stage should fall through to __end__ or another path.
            if rule.edge_type == "loopback":
                continue

            # Target is inactive — bypass it using only forward-progress edges
            bypass_target = self._find_bypass_target(
                target, active_node_ids, state, visited=set(),
                allow_loopback=False,
            )

            if bypass_target and (bypass_target in active_node_ids or bypass_target == "__end__"):
                new_rule = EdgeRule(
                    from_node=rule.from_node,
                    to_node=bypass_target,
                    condition=rule.condition,
                    edge_type="bypass",
                    priority=rule.priority,
                    description=f"BYPASS: {rule.description} (skipped inactive {target})",
                )
                bypass_key = (rule.from_node, bypass_target)
                if bypass_key not in visited_bypasses:
                    resolved.append(new_rule)
                    visited_bypasses.add(bypass_key)

        return resolved

    def _find_bypass_target(
        self,
        inactive_node: str,
        active_node_ids: set[str],
        state: dict[str, Any],
        visited: set[str] | None = None,
        allow_loopback: bool = False,
    ) -> str | None:
        """Follow outgoing rules from an inactive node to find the next active target.

        Recursively traverses inactive nodes until an active one is found.
        Only follows forward-progress edges (fixed, conditional, bypass).
        Loopback edges are excluded unless allow_loopback=True.
        Returns None if no path to an active node exists.
        """
        if visited is None:
            visited = set()

        if inactive_node in visited:
            return None  # Prevent infinite loops
        visited.add(inactive_node)

        # Get outgoing rules from this inactive node
        outgoing = self.get_rules_for_node(inactive_node)
        if not outgoing:
            return None

        # Filter out loopback edges unless explicitly allowed
        if not allow_loopback:
            outgoing = [r for r in outgoing if r.edge_type != "loopback"]

        # Prefer fixed edges, then conditional edges that evaluate to True
        for rule in sorted(outgoing, key=lambda r: (0 if r.edge_type == "fixed" else 1, -r.priority)):
            target = rule.to_node

            if target in active_node_ids or target == "__end__":
                return target

            # Target is also inactive — recurse
            if rule.condition is None or rule.evaluate(state):
                result = self._find_bypass_target(
                    target, active_node_ids, state, visited, allow_loopback,
                )
                if result:
                    return result

        return None


def _stage_done(state: dict[str, Any], stage_id: str) -> bool:
    stages = state.get("stages", {})
    return stages.get(stage_id, {}).get("done", False)


def _stage_failed(state: dict[str, Any], stage_id: str) -> bool:
    stages = state.get("stages", {})
    stage = stages.get(stage_id, {})
    return stage.get("done", False) is False and stage.get("attempts", 0) > 0


def _complexity_is(state: dict[str, Any], level: str) -> bool:
    return state.get("complexity", "small") == level


def _complexity_at_least(state: dict[str, Any], level: str) -> bool:
    order = {"small": 0, "medium": 1, "large": 2, "complex": 3}
    return order.get(state.get("complexity", "small"), 0) >= order.get(level, 0)


def _is_ui_project(state: dict[str, Any]) -> bool:
    return state.get("ui_project", False)


def _is_blocked(state: dict[str, Any]) -> bool:
    return state.get("status") == "blocked"


def build_edge_rules(parallel_qa: bool = False) -> EdgeRulesEngine:
    """Build the complete set of edge rules for the engineering loop graph."""
    engine = EdgeRulesEngine()

    # --- Entry point ---
    engine.add_fixed("__start__", "init", description="Entry point")

    # --- INIT chain ---
    engine.add_conditional(
        "init", "init-ideate",
        condition=lambda s: not _is_blocked(s),
        description="Init validated, proceed to ideation",
    )
    engine.add_conditional(
        "init", "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Init blocked, terminate",
    )

    engine.add_fixed("init-ideate", "init-bdd", description="Ideation → BDD")
    engine.add_fixed("init-bdd", "init-refine", description="BDD → Refine")

    # Init-refine → next phase based on complexity
    engine.add_conditional(
        "init-refine", "arch-requirements",
        condition=lambda s: _stage_done(s, "init.refine") and _complexity_at_least(s, "medium"),
        description="Medium+ complexity → architecture",
    )
    engine.add_conditional(
        "init-refine", "impl-design",
        condition=lambda s: _stage_done(s, "init.refine") and not _complexity_at_least(s, "medium"),
        description="Small complexity → implementation",
    )

    # --- DESIGN chain ---
    engine.add_fixed("design-user-research", "design-personas", description="Research → Personas")
    engine.add_fixed("design-personas", "design-info-arch", description="Personas → Info Arch")
    engine.add_fixed("design-info-arch", "design-interaction", description="Info Arch → Interaction")
    engine.add_fixed("design-interaction", "design-design-system", description="Interaction → Design System")
    engine.add_fixed("design-design-system", "design-visual-design", description="Design System → Visual")

    # Design complete → next phase
    engine.add_conditional(
        "design-visual-design", "arch-requirements",
        condition=lambda s: _stage_done(s, "design.visual-design") and _complexity_at_least(s, "medium"),
        description="Design done, medium+ → architecture",
    )
    engine.add_conditional(
        "design-visual-design", "impl-design",
        condition=lambda s: _stage_done(s, "design.visual-design") and not _complexity_at_least(s, "medium"),
        description="Design done, small → implementation",
    )

    # --- ARCHITECTURE chain ---
    engine.add_fixed("arch-requirements", "arch-solution", description="Requirements → Solution")

    # Arch-solution → review (complex) or impl
    engine.add_conditional(
        "arch-solution", "arch-review",
        condition=lambda s: _stage_done(s, "arch.solution") and _complexity_is(s, "complex"),
        description="Complex → architecture review",
    )
    engine.add_conditional(
        "arch-solution", "impl-design",
        condition=lambda s: _stage_done(s, "arch.solution") and not _complexity_is(s, "complex"),
        description="Not complex → implementation",
    )

    engine.add_fixed("arch-review", "impl-design", description="Review → Implementation")

    # --- IMPLEMENTATION chain ---
    engine.add_fixed("impl-design", "impl-code", description="Design → Code")
    engine.add_fixed("impl-code", "doc-update", description="Code → Doc Update")
    engine.add_fixed("doc-update", "verify", description="Doc Update → Verify")

    # --- VERIFICATION ---
    # Verify PASS → next based on context
    engine.add_loopback(
        "verify", "impl-code",
        condition=lambda s: not _stage_done(s, "verify"),
        description="Verify FAIL → retry impl.code",
    )
    engine.add_conditional(
        "verify", "e2e-execute",
        condition=lambda s: _stage_done(s, "verify") and _is_ui_project(s),
        description="Verify PASS, UI project → E2E",
    )
    engine.add_conditional(
        "verify", "qa-security",
        condition=lambda s: _stage_done(s, "verify") and not _is_ui_project(s) and _complexity_at_least(s, "medium"),
        description="Verify PASS, medium+ → QA security",
    )
    engine.add_conditional(
        "verify", "deploy-prepare",
        condition=lambda s: _stage_done(s, "verify") and not _is_ui_project(s) and not _complexity_at_least(s, "medium"),
        description="Verify PASS, small → deploy",
    )

    # --- E2E ---
    engine.add_loopback(
        "e2e-execute", "impl-code",
        condition=lambda s: not _stage_done(s, "e2e.execute"),
        description="E2E FAIL → retry impl.code",
    )
    engine.add_conditional(
        "e2e-execute", "qa-security",
        condition=lambda s: _stage_done(s, "e2e.execute") and _complexity_at_least(s, "medium"),
        description="E2E PASS, medium+ → QA security",
    )
    engine.add_conditional(
        "e2e-execute", "deploy-prepare",
        condition=lambda s: _stage_done(s, "e2e.execute") and not _complexity_at_least(s, "medium"),
        description="E2E PASS, small → deploy",
    )

    # --- QA chain ---
    if parallel_qa:
        # Fan-out: all QA stages run in parallel after verify/e2e
        # Fan-in: qa-join aggregates results
        pass  # Handled by GraphBuilder with Send commands
    else:
        # Sequential QA (current behavior)
        # QA Security
        engine.add_loopback(
            "qa-security", "impl-code",
            condition=lambda s: not _stage_done(s, "qa.security"),
            description="QA Security FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-security", "qa-api-contract",
            condition=lambda s: _stage_done(s, "qa.security") and _complexity_at_least(s, "medium"),
            description="QA Security PASS, medium+ → API contract",
        )
        engine.add_conditional(
            "qa-security", "deploy-prepare",
            condition=lambda s: _stage_done(s, "qa.security") and not _complexity_at_least(s, "medium"),
            description="QA Security PASS, small → deploy",
        )

        # QA API Contract
        engine.add_loopback(
            "qa-api-contract", "impl-code",
            condition=lambda s: not _stage_done(s, "qa.api-contract"),
            description="QA API Contract FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-api-contract", "qa-performance",
            condition=lambda s: _stage_done(s, "qa.api-contract") and _complexity_is(s, "complex"),
            description="QA API PASS, complex → performance",
        )
        engine.add_conditional(
            "qa-api-contract", "deploy-prepare",
            condition=lambda s: _stage_done(s, "qa.api-contract") and not _complexity_is(s, "complex"),
            description="QA API PASS, not complex → deploy",
        )

        # QA Performance
        engine.add_loopback(
            "qa-performance", "impl-code",
            condition=lambda s: not _stage_done(s, "qa.performance"),
            description="QA Performance FAIL → retry impl.code",
        )
        engine.add_fixed("qa-performance", "deploy-prepare", description="QA Performance → Deploy")

    # --- DEPLOY ---
    engine.add_loopback(
        "deploy-prepare", "impl-code",
        condition=lambda s: not _stage_done(s, "deploy.prepare"),
        description="Deploy FAIL → retry impl.code",
    )
    engine.add_conditional(
        "deploy-prepare", "smoke-test",
        condition=lambda s: _stage_done(s, "deploy.prepare") and _is_ui_project(s),
        description="Deploy PASS, UI → smoke test",
    )
    engine.add_conditional(
        "deploy-prepare", "doc-decisions",
        condition=lambda s: _stage_done(s, "deploy.prepare") and not _is_ui_project(s) and _complexity_at_least(s, "medium"),
        description="Deploy PASS, medium+ → doc decisions",
    )
    engine.add_conditional(
        "deploy-prepare", "post",
        condition=lambda s: _stage_done(s, "deploy.prepare") and not _is_ui_project(s) and not _complexity_at_least(s, "medium"),
        description="Deploy PASS, small → post",
    )

    # --- SMOKE TEST ---
    engine.add_loopback(
        "smoke-test", "impl-code",
        condition=lambda s: not _stage_done(s, "smoke.test"),
        description="Smoke FAIL → retry impl.code",
    )
    engine.add_conditional(
        "smoke-test", "doc-decisions",
        condition=lambda s: _stage_done(s, "smoke.test") and _complexity_at_least(s, "medium"),
        description="Smoke PASS, medium+ → doc decisions",
    )
    engine.add_conditional(
        "smoke-test", "post",
        condition=lambda s: _stage_done(s, "smoke.test") and not _complexity_at_least(s, "medium"),
        description="Smoke PASS, small → post",
    )

    # --- DOCUMENTATION ---
    engine.add_fixed("doc-decisions", "doc-project", description="Decisions → Project docs")
    engine.add_fixed("doc-project", "post", description="Project docs → Post")

    # --- POST ---
    engine.add_fixed("post", "__end__", description="Post → End")

    return engine

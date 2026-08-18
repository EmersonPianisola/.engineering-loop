from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eng_loop.schemas import GraphTopologyProposal


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
        self.add(
            EdgeRule(
                from_node=from_node,
                to_node=to_node,
                edge_type="fixed",
                description=description,
            )
        )

    def add_conditional(
        self,
        from_node: str,
        to_node: str,
        condition: Callable[[dict[str, Any]], bool],
        edge_type: str = "conditional",
        description: str = "",
    ) -> None:
        self.add(
            EdgeRule(
                from_node=from_node,
                to_node=to_node,
                condition=condition,
                edge_type=edge_type,
                description=description,
            )
        )

    def add_loopback(
        self,
        from_node: str,
        to_node: str,
        condition: Callable[[dict[str, Any]], bool],
        description: str = "",
    ) -> None:
        self.add(
            EdgeRule(
                from_node=from_node,
                to_node=to_node,
                condition=condition,
                edge_type="loopback",
                priority=10,
                description=description,
            )
        )

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
                target,
                active_node_ids,
                state,
                visited=set(),
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
                    target,
                    active_node_ids,
                    state,
                    visited,
                    allow_loopback,
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


def _blueprint_valid(state: dict[str, Any]) -> bool:
    """Check that impl.design produced a valid blueprint (has tasks + sufficient length).
    Used by edge rules to prevent impl-code from running before contract is satisfied."""
    stages = state.get("stages", {})
    design_stage = stages.get("impl.design", {})
    output_str = design_stage.get("output", "")
    if not output_str:
        return False
    # Parse the output to check for tasks and blueprint length
    import ast
    import json

    try:
        output_data = json.loads(output_str) if isinstance(output_str, str) else output_str
    except (json.JSONDecodeError, TypeError):
        # Try Python dict repr (single quotes)
        try:
            output_data = ast.literal_eval(output_str) if isinstance(output_str, str) else output_str
        except (ValueError, SyntaxError, TypeError):
            return False
    if not isinstance(output_data, dict):
        return False
    tasks = output_data.get("tasks", [])
    blueprint = output_data.get("blueprint", "")
    return bool(tasks) and len(blueprint) >= 50


def build_edge_rules(parallel_qa: bool = False) -> EdgeRulesEngine:
    """Build the complete set of edge rules for the engineering loop graph."""
    engine = EdgeRulesEngine()

    # --- Entry point: setup → dynamic architect → init ---
    engine.add_fixed("__start__", "init-setup", description="Entry → deterministic setup")
    engine.add_fixed("init-setup", "dynamic-architect", description="Setup → dynamic architect gate")

    # Dynamic architect routing
    engine.add_conditional(
        "dynamic-architect",
        "meta-executor",
        condition=lambda s: (
            (s.get("dynamic_plan") or {}).get("trigger") == "augment" and (s.get("dynamic_plan") or {}).get("steps")
        ),
        description="Blueprint augment → meta executor",
    )
    engine.add_conditional(
        "dynamic-architect",
        "init",
        condition=lambda s: (
            not s.get("dynamic_plan")
            or (s.get("dynamic_plan") or {}).get("trigger") != "augment"
            or not (s.get("dynamic_plan") or {}).get("steps")
        ),
        description="No augmentation → normal pipeline",
    )

    # Meta executor routing
    engine.add_loopback(
        "meta-executor",
        "meta-executor",
        condition=lambda s: s.get("dynamic_runtime", {}).get("status") == "running",
        description="Meta executor self-loop (retry/advance step)",
    )
    engine.add_conditional(
        "meta-executor",
        "init",
        condition=lambda s: s.get("dynamic_runtime", {}).get("status") == "completed",
        description="All dynamic steps done → pipeline",
    )
    engine.add_conditional(
        "meta-executor",
        "__end__",
        condition=lambda s: s.get("dynamic_runtime", {}).get("status") == "blocked",
        edge_type="terminal",
        description="Dynamic step exhausted → terminate",
    )

    # --- INIT chain ---
    engine.add_conditional(
        "init",
        "init-ideate",
        condition=lambda s: not _is_blocked(s),
        description="Init validated, proceed to ideation",
    )
    engine.add_conditional(
        "init",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Init blocked, terminate",
    )

    engine.add_fixed("init-ideate", "init-bdd", description="Ideation → BDD")
    engine.add_fixed("init-bdd", "init-refine", description="BDD → Refine")

    # Init-refine → next phase based on complexity
    engine.add_conditional(
        "init-refine",
        "arch-requirements",
        condition=lambda s: _stage_done(s, "init.refine") and _complexity_at_least(s, "medium"),
        description="Medium+ complexity → architecture",
    )
    engine.add_conditional(
        "init-refine",
        "impl-design",
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
        "design-visual-design",
        "arch-requirements",
        condition=lambda s: _stage_done(s, "design.visual-design") and _complexity_at_least(s, "medium"),
        description="Design done, medium+ → architecture",
    )
    engine.add_conditional(
        "design-visual-design",
        "impl-design",
        condition=lambda s: _stage_done(s, "design.visual-design") and not _complexity_at_least(s, "medium"),
        description="Design done, small → implementation",
    )

    # --- ARCHITECTURE chain ---
    engine.add_fixed("arch-requirements", "arch-solution", description="Requirements → Solution")

    # Arch-solution → review (complex) or impl
    engine.add_conditional(
        "arch-solution",
        "arch-review",
        condition=lambda s: _stage_done(s, "arch.solution") and _complexity_is(s, "complex"),
        description="Complex → architecture review",
    )
    engine.add_conditional(
        "arch-solution",
        "impl-design",
        condition=lambda s: _stage_done(s, "arch.solution") and not _complexity_is(s, "complex"),
        description="Not complex → implementation",
    )

    engine.add_fixed("arch-review", "impl-design", description="Review → Implementation")

    # --- IMPLEMENTATION chain ---
    # impl-design → impl-code: conditional on valid blueprint + not blocked
    # Prevents fixed edge from racing with contract gate retry/block
    engine.add_conditional(
        "impl-design",
        "impl-code",
        condition=lambda s: _stage_done(s, "impl.design") and _blueprint_valid(s) and not _is_blocked(s),
        description="Design → Code (blueprint valid)",
    )
    engine.add_conditional(
        "impl-design",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Design BLOCKED → terminate",
    )

    # impl-code → doc-update: conditional on not blocked.
    # If impl.code exhausted attempts and set status=blocked, route to __end__.
    engine.add_conditional(
        "impl-code",
        "doc-update",
        condition=lambda s: not _is_blocked(s),
        description="Code PASS → Doc Update",
    )
    engine.add_conditional(
        "impl-code",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Code BLOCKED → terminate",
    )

    # doc-update → verify: same gate
    engine.add_conditional(
        "doc-update",
        "verify",
        condition=lambda s: not _is_blocked(s),
        description="Doc Update → Verify",
    )
    engine.add_conditional(
        "doc-update",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Doc Update BLOCKED → terminate",
    )

    # --- VERIFICATION ---
    # Verify FAIL → retry impl.code (loopback, highest priority)
    engine.add_loopback(
        "verify",
        "impl-code",
        condition=lambda s: not _stage_done(s, "verify") and not _is_blocked(s),
        description="Verify FAIL → retry impl.code",
    )
    # Blocked pipeline → terminate
    engine.add_conditional(
        "verify",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Verify BLOCKED → terminate",
    )
    # Verify PASS → qa.static (base of QA pyramid)
    engine.add_conditional(
        "verify",
        "qa-static",
        condition=lambda s: _stage_done(s, "verify") and not _is_blocked(s),
        description="Verify PASS → Static Analysis (QA pyramid base)",
    )

    # --- QA: Static Analysis ---
    engine.add_loopback(
        "qa-static",
        "impl-code",
        condition=lambda s: not _stage_done(s, "qa.static") and not _is_blocked(s),
        description="QA Static FAIL → retry impl.code",
    )
    engine.add_conditional(
        "qa-static",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="QA Static BLOCKED → terminate",
    )
    engine.add_conditional(
        "qa-static",
        "qa-unit",
        condition=lambda s: _stage_done(s, "qa.static") and not _is_blocked(s),
        description="QA Static PASS → Unit Testing",
    )

    # --- QA: Unit Testing ---
    engine.add_loopback(
        "qa-unit",
        "impl-code",
        condition=lambda s: not _stage_done(s, "qa.unit") and not _is_blocked(s),
        description="QA Unit FAIL → retry impl.code",
    )
    engine.add_conditional(
        "qa-unit",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="QA Unit BLOCKED → terminate",
    )
    engine.add_conditional(
        "qa-unit",
        "qa-integration",
        condition=lambda s: _stage_done(s, "qa.unit") and _complexity_at_least(s, "medium") and not _is_blocked(s),
        description="QA Unit PASS, medium+ → Integration",
    )
    engine.add_conditional(
        "qa-unit",
        "e2e-execute",
        condition=lambda s: _stage_done(s, "qa.unit") and not _complexity_at_least(s, "medium") and not _is_blocked(s),
        description="QA Unit PASS, small → E2E",
    )

    # --- QA: Integration ---
    engine.add_loopback(
        "qa-integration",
        "impl-code",
        condition=lambda s: not _stage_done(s, "qa.integration") and not _is_blocked(s),
        description="QA Integration FAIL → retry impl.code",
    )
    engine.add_conditional(
        "qa-integration",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="QA Integration BLOCKED → terminate",
    )
    engine.add_conditional(
        "qa-integration",
        "e2e-execute",
        condition=lambda s: _stage_done(s, "qa.integration") and not _is_blocked(s),
        description="QA Integration PASS → E2E",
    )

    # --- E2E (now after integration) ---
    engine.add_loopback(
        "e2e-execute",
        "impl-code",
        condition=lambda s: not _stage_done(s, "e2e.execute") and not _is_blocked(s),
        description="E2E FAIL → retry impl.code",
    )
    engine.add_conditional(
        "e2e-execute",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="E2E BLOCKED → terminate",
    )
    engine.add_conditional(
        "e2e-execute",
        "qa-security",
        condition=lambda s: _stage_done(s, "e2e.execute") and _complexity_at_least(s, "medium") and not _is_blocked(s),
        description="E2E PASS, medium+ → QA security",
    )
    engine.add_conditional(
        "e2e-execute",
        "qa-human-flow",
        condition=lambda s: (
            _stage_done(s, "e2e.execute") and not _complexity_at_least(s, "medium") and not _is_blocked(s)
        ),
        description="E2E PASS, small → human flow",
    )

    # --- QA chain (post-E2E) ---
    if parallel_qa:
        # Parallel QA: dispatcher → [Send qa-security, Send qa-api, ...] → join
        # Edges are added by GraphBuilder._add_parallel_qa(), NOT here.
        # We only add the verify/e2e → deploy fallback for small complexity.
        engine.add_conditional(
            "verify",
            "deploy-prepare",
            condition=lambda s: (
                _stage_done(s, "verify") and not _complexity_at_least(s, "medium") and not _is_blocked(s)
            ),
            description="Verify PASS, small → deploy (parallel QA mode)",
        )
        engine.add_conditional(
            "e2e-execute",
            "deploy-prepare",
            condition=lambda s: (
                _stage_done(s, "e2e.execute") and not _complexity_at_least(s, "medium") and not _is_blocked(s)
            ),
            description="E2E PASS, small → deploy (parallel QA mode)",
        )
    else:
        # Sequential QA (post-E2E)
        # QA Security
        engine.add_loopback(
            "qa-security",
            "impl-code",
            condition=lambda s: not _stage_done(s, "qa.security") and not _is_blocked(s),
            description="QA Security FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-security",
            "__end__",
            condition=_is_blocked,
            edge_type="terminal",
            description="QA Security BLOCKED → terminate",
        )
        engine.add_conditional(
            "qa-security",
            "qa-performance",
            condition=lambda s: _stage_done(s, "qa.security") and _complexity_is(s, "complex") and not _is_blocked(s),
            description="QA Security PASS, complex → performance",
        )
        engine.add_conditional(
            "qa-security",
            "qa-human-flow",
            condition=lambda s: (
                _stage_done(s, "qa.security") and not _complexity_is(s, "complex") and not _is_blocked(s)
            ),
            description="QA Security PASS, not complex → human flow",
        )

        # QA API Contract (DEPRECATED — alias for qa.integration)
        engine.add_loopback(
            "qa-api-contract",
            "impl-code",
            condition=lambda s: not _stage_done(s, "qa.api-contract") and not _is_blocked(s),
            description="QA API Contract FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-api-contract",
            "__end__",
            condition=_is_blocked,
            edge_type="terminal",
            description="QA API Contract BLOCKED → terminate",
        )
        engine.add_conditional(
            "qa-api-contract",
            "qa-performance",
            condition=lambda s: (
                _stage_done(s, "qa.api-contract") and _complexity_is(s, "complex") and not _is_blocked(s)
            ),
            description="QA API PASS, complex → performance",
        )
        engine.add_conditional(
            "qa-api-contract",
            "deploy-prepare",
            condition=lambda s: (
                _stage_done(s, "qa.api-contract") and not _complexity_is(s, "complex") and not _is_blocked(s)
            ),
            description="QA API PASS, not complex → deploy",
        )

        # QA Performance
        engine.add_loopback(
            "qa-performance",
            "impl-code",
            condition=lambda s: not _stage_done(s, "qa.performance") and not _is_blocked(s),
            description="QA Performance FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-performance",
            "__end__",
            condition=_is_blocked,
            edge_type="terminal",
            description="QA Performance BLOCKED → terminate",
        )
        engine.add_conditional(
            "qa-performance",
            "qa-human-flow",
            condition=lambda s: _stage_done(s, "qa.performance") and not _is_blocked(s),
            description="QA Performance PASS → human flow",
        )

        # QA Human Flow
        engine.add_loopback(
            "qa-human-flow",
            "impl-code",
            condition=lambda s: not _stage_done(s, "qa.human.flow") and not _is_blocked(s),
            description="QA Human Flow FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-human-flow",
            "__end__",
            condition=_is_blocked,
            edge_type="terminal",
            description="QA Human Flow BLOCKED → terminate",
        )
        engine.add_conditional(
            "qa-human-flow",
            "qa-human-ux",
            condition=lambda s: _stage_done(s, "qa.human.flow") and _is_ui_project(s) and not _is_blocked(s),
            description="QA Human Flow PASS, UI → UX audit",
        )
        engine.add_conditional(
            "qa-human-flow",
            "deploy-prepare",
            condition=lambda s: _stage_done(s, "qa.human.flow") and not _is_ui_project(s) and not _is_blocked(s),
            description="QA Human Flow PASS, non-UI → deploy",
        )

        # QA Human UX
        engine.add_loopback(
            "qa-human-ux",
            "impl-code",
            condition=lambda s: not _stage_done(s, "qa.human.ux") and not _is_blocked(s),
            description="QA Human UX FAIL → retry impl.code",
        )
        engine.add_conditional(
            "qa-human-ux",
            "__end__",
            condition=_is_blocked,
            edge_type="terminal",
            description="QA Human UX BLOCKED → terminate",
        )
        engine.add_conditional(
            "qa-human-ux",
            "deploy-prepare",
            condition=lambda s: _stage_done(s, "qa.human.ux") and not _is_blocked(s),
            description="QA Human UX PASS → deploy",
        )

    # --- DEPLOY ---
    engine.add_loopback(
        "deploy-prepare",
        "impl-code",
        condition=lambda s: not _stage_done(s, "deploy.prepare") and not _is_blocked(s),
        description="Deploy FAIL → retry impl.code",
    )
    engine.add_conditional(
        "deploy-prepare",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Deploy BLOCKED → terminate",
    )
    engine.add_conditional(
        "deploy-prepare",
        "smoke-test",
        condition=lambda s: _stage_done(s, "deploy.prepare") and _is_ui_project(s) and not _is_blocked(s),
        description="Deploy PASS, UI → smoke test",
    )
    engine.add_conditional(
        "deploy-prepare",
        "doc-decisions",
        condition=lambda s: (
            _stage_done(s, "deploy.prepare")
            and not _is_ui_project(s)
            and _complexity_at_least(s, "medium")
            and not _is_blocked(s)
        ),
        description="Deploy PASS, medium+ → doc decisions",
    )
    engine.add_conditional(
        "deploy-prepare",
        "post",
        condition=lambda s: (
            _stage_done(s, "deploy.prepare")
            and not _is_ui_project(s)
            and not _complexity_at_least(s, "medium")
            and not _is_blocked(s)
        ),
        description="Deploy PASS, small → post",
    )

    # --- SMOKE TEST ---
    engine.add_loopback(
        "smoke-test",
        "impl-code",
        condition=lambda s: not _stage_done(s, "smoke.test") and not _is_blocked(s),
        description="Smoke FAIL → retry impl.code",
    )
    engine.add_conditional(
        "smoke-test",
        "__end__",
        condition=_is_blocked,
        edge_type="terminal",
        description="Smoke BLOCKED → terminate",
    )
    engine.add_conditional(
        "smoke-test",
        "doc-decisions",
        condition=lambda s: _stage_done(s, "smoke.test") and _complexity_at_least(s, "medium") and not _is_blocked(s),
        description="Smoke PASS, medium+ → doc decisions",
    )
    engine.add_conditional(
        "smoke-test",
        "post",
        condition=lambda s: (
            _stage_done(s, "smoke.test") and not _complexity_at_least(s, "medium") and not _is_blocked(s)
        ),
        description="Smoke PASS, small → post",
    )

    # --- DOCUMENTATION ---
    engine.add_fixed("doc-decisions", "doc-project", description="Decisions → Project docs")
    engine.add_fixed("doc-project", "post", description="Project docs → Post")

    # --- POST ---
    engine.add_fixed("post", "__end__", description="Post → End")

    return engine


# ───────────────────────────────────────────────────────────────────
# Condition predicates — allowed conditions mapped to state predicates
# These are the ONLY conditions the LLM can reference in edge definitions.
# ───────────────────────────────────────────────────────────────────


def _get_condition_predicate(condition: str) -> Callable[[dict[str, Any]], bool]:
    """Translate an allowed condition identifier into a state predicate function."""

    predicates = {
        "always": lambda s: True,
        "stage_done": lambda s: s.get("status") != "blocked",
        "stage_failed": lambda s: False,  # Populated per-stage in build_rules_from_proposal
        "stage_blocked": lambda s: s.get("status") == "blocked",
        "complexity_at_least_medium": lambda s: _complexity_at_least(s, "medium"),
        "complexity_at_least_large": lambda s: _complexity_at_least(s, "large"),
        "complexity_is_complex": lambda s: _complexity_is(s, "complex"),
        "complexity_is_small": lambda s: not _complexity_at_least(s, "medium"),
        "is_ui_project": lambda s: s.get("ui_project", False),
        "not_ui_project": lambda s: not s.get("ui_project", False),
    }
    return predicates.get(condition, lambda s: True)


def build_rules_from_proposal(
    proposal: GraphTopologyProposal,
    parallel_qa: bool = False,
) -> EdgeRulesEngine:
    """Convert an authorized GraphTopologyProposal into EdgeRule objects.

    Takes the declarative proposal and produces executable edge rules.
    Standard failure-routing patterns (loopback, terminal) are injected
    automatically for verification/QA/deploy stages — the architect
    doesn't need to redefine operational behavior.
    """
    engine = EdgeRulesEngine()
    stage_set = set(proposal.required_stages)

    # Entry point: init-setup is ALWAYS the entry (registered by graph builder)
    engine.add_fixed("__start__", "init-setup", description="Entry → deterministic setup")

    # Meta nodes (dynamic-architect, meta-executor) are always registered by builder
    # Add architect routing regardless of whether it's in the proposal
    engine.add_conditional(
        "init-setup",
        "dynamic-architect",
        condition=lambda s: True,
        description="Setup → architect gate",
    )
    engine.add_conditional(
        "dynamic-architect",
        "init",
        condition=lambda s: (
            not s.get("dynamic_plan")
            or (s.get("dynamic_plan") or {}).get("trigger") != "augment"
            or not (s.get("dynamic_plan") or {}).get("steps")
        ),
        description="No augmentation → pipeline",
    )
    engine.add_conditional(
        "dynamic-architect",
        "meta-executor",
        condition=lambda s: (
            (s.get("dynamic_plan") or {}).get("trigger") == "augment" and (s.get("dynamic_plan") or {}).get("steps")
        ),
        description="Augment → meta executor",
    )
    engine.add_loopback(
        "meta-executor",
        "meta-executor",
        condition=lambda s: s.get("dynamic_runtime", {}).get("status") == "running",
        description="Meta executor self-loop",
    )
    engine.add_conditional(
        "meta-executor",
        "init",
        condition=lambda s: s.get("dynamic_runtime", {}).get("status") == "completed",
        description="Dynamic steps done → pipeline",
    )
    engine.add_conditional(
        "meta-executor",
        "__end__",
        condition=lambda s: s.get("dynamic_runtime", {}).get("status") == "blocked",
        edge_type="terminal",
        description="Dynamic step blocked → terminate",
    )

    # Compile proposed edges
    for edge in proposal.edges:
        from_name = edge.from_stage.replace(".", "-").replace("_", "-")
        to_name = edge.to_stage.replace(".", "-").replace("_", "-")

        if from_name in ("__start__", "__end__"):
            from_name = edge.from_stage
        if to_name in ("__start__", "__end__"):
            to_name = edge.to_stage

        if edge.edge_type == "fixed":
            engine.add_fixed(from_name, to_name, description=edge.description)
        elif edge.edge_type == "loopback":
            predicate = _get_condition_predicate(edge.condition)
            engine.add_loopback(from_name, to_name, condition=predicate, description=edge.description)
        elif edge.edge_type == "terminal":
            predicate = _get_condition_predicate(edge.condition)
            engine.add_conditional(
                from_name,
                to_name,
                condition=predicate,
                edge_type="terminal",
                description=edge.description,
            )
        else:  # conditional
            predicate = _get_condition_predicate(edge.condition)
            engine.add_conditional(
                from_name,
                to_name,
                condition=predicate,
                description=edge.description,
            )

    # Inject standard failure-routing for stages that need it
    # These are operational policies, not topology decisions
    _inject_failure_routing(engine, stage_set, proposal)

    return engine


def _inject_failure_routing(
    engine: EdgeRulesEngine,
    stage_set: set[str],
    proposal: GraphTopologyProposal,
) -> None:
    """Inject standard loopback/terminal edges for verification, QA, and deploy stages.

    The architect proposes the happy-path topology. Failure routing is
    an operational concern handled by the framework, not the LLM.

    Uses metadata-driven approach: any stage whose node name starts with
    'qa-' or is a known verification/deploy stage gets automatic failure routing.
    """
    # Build a lookup of execution policies from the proposal
    policy_map = {}
    for pol in proposal.execution_policies:
        policy_map[pol.stage_id] = pol

    # Build normalized set: both dot and hyphen notation
    normalized_set = set()
    for s in stage_set:
        normalized_set.add(s)
        normalized_set.add(s.replace(".", "-").replace("_", "-"))

    # Core failure routing stages (always apply)
    core_failure_stages = {
        "verify": {"stage_key": "verify"},
        "e2e-execute": {"stage_key": "e2e.execute"},
        "deploy-prepare": {"stage_key": "deploy.prepare"},
        "smoke-test": {"stage_key": "smoke.test"},
    }

    # Discover QA stages dynamically from the normalized set
    qa_failure_stages = {}
    for node_name in normalized_set:
        if node_name.startswith("qa-"):
            stage_key = node_name.replace("-", ".")
            qa_failure_stages[node_name] = {"stage_key": stage_key}

    all_failure_stages = {**core_failure_stages, **qa_failure_stages}

    for node_name, info in all_failure_stages.items():
        if node_name not in normalized_set:
            continue

        stage_key = info["stage_key"]
        loopback_target = "impl-code"

        # Check if a custom failure route was specified in the policy
        policy = policy_map.get(stage_key)
        if policy and policy.failure_route:
            loopback_target = policy.failure_route.replace(".", "-").replace("_", "-")

        if loopback_target in normalized_set:
            engine.add_loopback(
                node_name,
                loopback_target,
                condition=lambda s, sk=stage_key: not _stage_done(s, sk) and not _is_blocked(s),
                description=f"{node_name} FAIL → retry {loopback_target}",
            )

        # Terminal edge for blocked state
        engine.add_conditional(
            node_name,
            "__end__",
            condition=_is_blocked,
            edge_type="terminal",
            description=f"{node_name} BLOCKED → terminate",
        )

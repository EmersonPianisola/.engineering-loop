from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from eng_loop.edge_rules import EdgeRule, EdgeRulesEngine, build_edge_rules
from eng_loop.node_registry import NodeRegistry, NodeSpec, build_registry
from eng_loop.state import PipelineState
from eng_loop.tools.contract_gate import CONTRACT_RULES, with_contract_gate
from eng_loop.tools.progress import trace_node
from eng_loop.tools.trace_logger import trace as _trace

if TYPE_CHECKING:
    from eng_loop.schemas import AuthorizedGraphTopology

logger = logging.getLogger(__name__)


class TopologyCompilationError(Exception):
    """Raised when graph topology cannot be compiled (missing forward target, etc.)."""


def _get_contract_sources() -> set[str]:
    """Return the set of node names that have outgoing contract rules."""
    return {rule.source for rule in CONTRACT_RULES}


class GraphTopology:
    """Metadata about the dynamically constructed graph."""

    def __init__(self):
        self.active_nodes: list[str] = []
        self.edges: list[dict[str, str]] = []
        self.parallel_groups: dict[str, list[str]] = {}
        self.complexity: str = "small"
        self.ui_project: bool = False
        self.total_available: int = 0
        self.nodes_included: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_nodes": self.active_nodes,
            "edges": self.edges,
            "parallel_groups": self.parallel_groups,
            "complexity": self.complexity,
            "ui_project": self.ui_project,
            "total_available": self.total_available,
            "nodes_included": self.nodes_included,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class GraphBuilder:
    """Dynamically builds a LangGraph StateGraph based on work item context."""

    def __init__(
        self,
        registry: NodeRegistry | None = None,
        rules: EdgeRulesEngine | None = None,
        parallel_qa: bool = False,
    ):
        self.registry = registry or build_registry(parallel_qa=parallel_qa)
        self.rules = rules or build_edge_rules(parallel_qa=parallel_qa)
        self.parallel_qa = parallel_qa

    def build(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
        authorized_topology: AuthorizedGraphTopology | None = None,
    ) -> tuple[StateGraph, GraphTopology]:
        """Build graph — dual-path compilation.

        If authorized_topology is provided, builds from the architect's proposal.
        Otherwise, falls back to deterministic filtering + hardcoded edge rules.
        """
        if authorized_topology:
            return self._build_from_proposal(authorized_topology, state)
        return self._build_deterministic(state, config)

    def _build_deterministic(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> tuple[StateGraph, GraphTopology]:
        """Fallback: deterministic graph from registry filter + hardcoded rules."""
        complexity = state.get("complexity", "small")
        ui_project = state.get("ui_project", False)
        tags = state.get("tags", [])
        work_type = state.get("work_type", "feature")
        config = config or {}

        active_specs = self.registry.filter(
            complexity=complexity,
            ui_project=ui_project,
            tags=tags,
            work_type=work_type,
        )
        active_node_names = {s.node_name for s in active_specs}

        topology = GraphTopology()
        topology.complexity = complexity
        topology.ui_project = ui_project
        topology.total_available = len(self.registry)
        topology.nodes_included = len(active_specs)
        topology.active_nodes = [s.id for s in active_specs]

        builder = StateGraph(PipelineState)

        # Register meta nodes (always active, not filtered by complexity)
        META_NODE_NAMES = {"dynamic-architect", "meta-executor"}
        for spec in self.registry.all_specs():
            if spec.node_name in META_NODE_NAMES:
                handler = trace_node(spec.id)(spec.handler)
                builder.add_node(spec.node_name, handler)
                active_node_names.add(spec.node_name)
                logger.info("  Meta node registered: %s (%s)", spec.node_name, spec.description)

        # Register active nodes (skip meta nodes — already registered above)
        for spec in active_specs:
            if spec.node_name in META_NODE_NAMES:
                continue
            handler = trace_node(spec.id)(spec.handler)
            # Apply contract gate for nodes that have outgoing contract rules
            if spec.node_name in _get_contract_sources():
                handler = with_contract_gate(spec.node_name)(handler)
            builder.add_node(spec.node_name, handler)
            logger.info("  Node registered: %s (%s)", spec.node_name, spec.description)

        # Build synthetic state: ALL stages done=True for rule resolution
        # This ensures forward-edge conditions (e.g., _stage_done) evaluate
        # based on build-time config, not runtime state.
        # Must include ALL registry stages (not just active) because
        # resolve_with_bypass follows chains through inactive nodes.
        synthetic_state = dict(state)
        synthetic_stages = dict(state.get("stages", {}))
        for spec in self.registry.all_specs():
            sid = spec.id
            if sid not in synthetic_stages:
                synthetic_stages[sid] = {}
            synthetic_stages[sid]["done"] = True
            # Provide minimal output for impl.design so _blueprint_valid passes
            if sid == "impl.design":
                synthetic_stages[sid]["output"] = json.dumps(
                    {
                        "tasks": [{"id": 1, "description": "t"}],
                        "blueprint": "x" * 100,
                    }
                )
        synthetic_state["stages"] = synthetic_stages
        synthetic_state["status"] = "running"

        bypassed_rules = self.rules.resolve_with_bypass(active_node_names | {"__start__"}, synthetic_state)
        self._add_edges(builder, bypassed_rules, active_node_names, synthetic_state, topology)

        if self.parallel_qa:
            self._add_parallel_qa(builder, active_specs, active_node_names, state, topology)

        logger.info(
            "Graph built (deterministic): %d/%d nodes active (complexity=%s, ui=%s)",
            len(active_specs),
            len(self.registry),
            complexity,
            ui_project,
        )

        return builder, topology

    def _build_from_proposal(
        self,
        authorized: AuthorizedGraphTopology,
        state: dict[str, Any],
    ) -> tuple[StateGraph, GraphTopology]:
        """Build graph from an authorized topology proposal.

        The proposal has passed all 5 layers of policy validation.
        This method is purely a compiler: authorized topology → executable graph.

        IMPORTANT: The architect can override complexity-based filtering (it knows
        better than heuristics). But work_type filtering is enforced — a documentation
        task should not include impl.design, verify, deploy, etc.
        """
        from eng_loop.edge_rules import build_rules_from_proposal
        from eng_loop.tools.autosizing import (
            DOCUMENTATION_EXCLUDED_STAGES,
            OPERATIONAL_EXCLUDED_STAGES,
            VALIDATION_EXCLUDED_STAGES,
        )

        complexity = state.get("complexity", "small")
        ui_project = state.get("ui_project", False)
        work_type = state.get("work_type", "feature")

        topology = GraphTopology()
        topology.complexity = complexity
        topology.ui_project = ui_project
        topology.total_available = len(self.registry)

        # Filter authorized stages: only enforce work_type constraints.
        # The architect can override complexity-based filtering — it has more context.
        # But work_type is structural: documentation tasks don't need impl.design/verify/deploy.
        excluded_for_work_type = set()
        if work_type == "documentation":
            excluded_for_work_type = set(DOCUMENTATION_EXCLUDED_STAGES)
        elif work_type == "validation":
            excluded_for_work_type = set(VALIDATION_EXCLUDED_STAGES)
        elif work_type == "operational":
            excluded_for_work_type = set(OPERATIONAL_EXCLUDED_STAGES)
        elif work_type == "bugfix":
            excluded_for_work_type = {
                "design.user-research",
                "design.personas",
                "design.info-arch",
                "design.interaction",
                "design.design-system",
                "design.visual-design",
            }

        filtered_stages = []
        for stage_id in authorized.authorized_stages:
            if stage_id in excluded_for_work_type:
                logger.warning(
                    "  [proposal] Skipping stage '%s': excluded for work_type=%s",
                    stage_id,
                    work_type,
                )
            else:
                filtered_stages.append(stage_id)

        topology.active_nodes = filtered_stages
        topology.nodes_included = len(filtered_stages)

        builder = StateGraph(PipelineState)

        # Build node name set from authorized stages
        stage_id_to_name = {}
        for spec in self.registry.all_specs():
            stage_id_to_name[spec.id] = spec.node_name

        # Register all authorized nodes
        META_NODE_NAMES = {"dynamic-architect", "meta-executor"}
        active_node_names = set()

        # Always register init-setup (deterministic entry point)
        setup_spec = self.registry.get("init.setup")
        if setup_spec:
            handler = trace_node(setup_spec.id)(setup_spec.handler)
            builder.add_node(setup_spec.node_name, handler)
            active_node_names.add(setup_spec.node_name)
            logger.info("  [proposal] Entry node: %s", setup_spec.node_name)

        # First: always register meta nodes (they handle runtime augmentation)
        for spec in self.registry.all_specs():
            if spec.node_name in META_NODE_NAMES:
                handler = trace_node(spec.id)(spec.handler)
                builder.add_node(spec.node_name, handler)
                active_node_names.add(spec.node_name)
                logger.info("  [proposal] Meta node: %s", spec.node_name)

        # Then: register filtered authorized stages
        for stage_id in filtered_stages:
            spec = self.registry.get(stage_id)
            if not spec:
                logger.warning("  [proposal] Stage '%s' not in registry, skipping", stage_id)
                continue
            if spec.node_name in META_NODE_NAMES:
                continue  # Already registered

            handler = trace_node(spec.id)(spec.handler)
            if spec.node_name in _get_contract_sources():
                handler = with_contract_gate(spec.node_name)(handler)
            builder.add_node(spec.node_name, handler)
            active_node_names.add(spec.node_name)
            logger.info("  [proposal] Node: %s (%s)", spec.node_name, spec.description)

        # Build edges from proposal
        # Reconstruct a temporary proposal object for build_rules_from_proposal
        from eng_loop.schemas import GraphTopologyProposal

        temp_proposal = GraphTopologyProposal(
            plan_id=authorized.plan_id,
            work_type=state.get("work_type", "feature"),
            complexity=state.get("complexity", "small"),
            required_stages=authorized.authorized_stages,
            edges=authorized.authorized_edges,
            phase_groups=authorized.phase_groups,
            execution_policies=authorized.execution_policies,
            rationale=authorized.rationale,
        )

        proposal_rules = build_rules_from_proposal(temp_proposal, self.parallel_qa)
        bypassed = proposal_rules.resolve_with_bypass(active_node_names | {"__start__"}, state)
        self._add_edges(builder, bypassed, active_node_names, state, topology)

        if authorized.policy_notes:
            logger.info("  [proposal] Policy notes: %s", authorized.policy_notes)

        logger.info(
            "Graph built (proposal %s): %d nodes",
            authorized.plan_id,
            len(active_node_names),
        )

        return builder, topology

    def compile(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
        checkpointer: Any | None = None,
        interrupt_before: list[str] | None = None,
        authorized_topology: AuthorizedGraphTopology | None = None,
    ) -> tuple[Any, GraphTopology]:
        # Single source of truth: nodes read the effective parallel-QA mode from
        # state config for routing decisions (e.g. verify → qa-dispatcher). It
        # must match the wiring this builder produces (self.parallel_qa).
        state.setdefault("config", {}).setdefault("dynamic_graph", {})["parallel_qa"] = self.parallel_qa
        builder, topology = self.build(state, config, authorized_topology)
        kwargs: dict[str, Any] = {}
        if checkpointer:
            kwargs["checkpointer"] = checkpointer
        elif interrupt_before:
            kwargs["checkpointer"] = MemorySaver()
        if interrupt_before:
            kwargs["interrupt_before"] = interrupt_before
        compiled = builder.compile(**kwargs)
        return compiled, topology

    # ── Failure routing table (new in strict routing refactor) ────────────
    # Maps stage node names to their rollback target.
    # Stages not listed have no failure route (only terminal / self-retry).
    FAILURE_ROUTES: dict[str, str] = {
        "verify": "impl-code",
        "e2e-execute": "impl-code",
        "deploy-prepare": "impl-code",
        "smoke-test": "impl-code",
        "arch.review": "arch-requirements",
    }

    def _failure_target(self, node_name: str) -> str | None:
        """Return the rollback target for a stage, or None if none."""
        return self.FAILURE_ROUTES.get(node_name)

    def _resolve_forward_target(
        self,
        node_name: str,
        rules: list[EdgeRule],
        active_names: set[str],
        state: dict[str, Any],
    ) -> str | None:
        """Resolve the forward (happy-path) target for a node.

        For proposal paths: the authorized edge from the node.
        For deterministic paths: the edge whose condition evaluates True
        (with bypass of inactive intermediaries).

        Uses a synthetic state where all active stages are done=True
        so forward targets depend only on known build-time config
        (complexity, ui_project, work_type), not runtime state.

        Returns None if no forward target found — this is a compilation error.
        """
        from_node = node_name

        # Build synthetic state: all active stages done=True, status=running
        # This lets us evaluate complexity/ui_project/work_type conditions
        # without depending on runtime stage completion.
        synthetic = dict(state)
        stages = synthetic.get("stages", {})
        # Ensure the current node's stage is done (it's the source of the outgoing rule)
        current_stage_key = node_name.replace("-", ".")
        if current_stage_key not in stages:
            stages[current_stage_key] = {"done": True}
        stages[current_stage_key]["done"] = True
        for sid in stages:
            stages[sid]["done"] = True
            # Provide a minimal output for impl.design so _blueprint_valid passes
            if sid == "impl.design":
                stages[sid]["output"] = json.dumps(
                    {
                        "tasks": [{"id": 1, "description": "task1"}],
                        "blueprint": "x" * 100,
                    }
                )
        synthetic["status"] = "running"

        # Filter rules that originate from this node
        outgoing = [r for r in rules if r.from_node == from_node or r.from_node == "*"]

        # Look for forward-progress edges (not loopback, not terminal)
        # Higher priority first — loopbacks beat forward edges
        for rule in sorted(outgoing, key=lambda r: r.priority, reverse=True):
            if rule.edge_type == "loopback":
                continue
            if rule.edge_type == "terminal":
                continue

            to_name = self._to_node_name(rule.to_node)
            # For conditional rules, check if the condition evaluates
            if rule.condition is None:
                # Fixed edge — just check if target is active
                if to_name in active_names or to_name == "__end__":
                    return to_name
            else:
                # Conditional edge — evaluate the condition against synthetic state
                if rule.evaluate(synthetic):
                    if to_name in active_names or to_name == "__end__":
                        return to_name

        # No forward target found — return None (will cause compilation error)
        return None

    def _add_edges(
        self,
        builder: StateGraph,
        rules: list[EdgeRule],
        active_names: set[str],
        state: dict[str, Any],
        topology: GraphTopology,
    ) -> None:
        """Register graph edges using unified routing.

        ALL nodes receive declared edges (no more "command" exclusion).
        Routing is determined by edge condition evaluators, not by handler return type.

        Each stage node gets ONE conditional edge with destinations:
        - __end__ (terminal: status=blocked/waiting)
        - failure_target (rollback: verdict=FAIL)
        - self (retry: not done, verdict != FAIL)
        - forward_target (forward: done)

        The unified evaluator (_route_unified) selects the right destination.
        """
        # Track which nodes have forward targets for validation
        unregistered: set[str] = set()

        # ── 1. Register entry edge from START ──────────────────────────
        start_rules = [r for r in rules if r.from_node == "__start__"]
        for rule in start_rules:
            to_name = self._to_node_name(rule.to_node)
            if to_name in active_names:
                builder.add_edge(START, to_name)
                topology.edges.append(
                    {
                        "from": "__start__",
                        "to": rule.to_node,
                        "type": "fixed",
                    }
                )

        # ── 2. Register unified conditional edge for each stage node ────
        # Exclude meta nodes — they get special edges in _add_meta_node_edges
        META_NODE_NAMES = {"dynamic-architect", "meta-executor"}
        for node_name in active_names:
            if node_name in ("__start__", "__end__") or node_name in META_NODE_NAMES:
                continue

            failure_target = self._failure_target(node_name)
            forward_target = self._resolve_forward_target(node_name, rules, active_names, state)

            if forward_target is None:
                unregistered.add(node_name)
                continue

            # Build destinations dict for LangGraph branch lookup
            destinations: dict[str, Any] = {
                "__end__": END,
                node_name: node_name,  # self-retry
            }
            if failure_target and failure_target in active_names:
                destinations[failure_target] = failure_target
            destinations[forward_target] = forward_target

            # Register the unified conditional edge
            # Close over forward_target and failure_target via default args
            builder.add_conditional_edges(
                node_name,
                lambda s, nn=node_name, ft=forward_target, fbt=failure_target: self._route_unified(
                    nn,
                    s,
                    terminal_cond=lambda s: s.get("status") in ("blocked", "waiting_for_input"),
                    failure_target=fbt,
                    forward_target=ft,
                ),
                destinations,
            )

            # Record edge in topology
            topology.edges.append(
                {
                    "from": node_name,
                    "to": forward_target,
                    "type": "forward",
                }
            )
            topology.edges.append(
                {
                    "from": node_name,
                    "to": "__end__",
                    "type": "terminal",
                }
            )
            if failure_target and failure_target in active_names:
                topology.edges.append(
                    {
                        "from": node_name,
                        "to": failure_target,
                        "type": "rollback",
                    }
                )

        # ── 3. Register meta-node specific edges (dynamic-architect, etc.) ──
        self._add_meta_node_edges(builder, active_names, rules, state, topology)

        # ── 4. Register parallel QA edges ──────────────────────────────
        if self.parallel_qa:
            self._add_parallel_qa_new(builder, active_names, rules, state, topology)

        # ── 5. Validate: every node (except post/__end__) must have forward target ──
        if unregistered:
            stage_names_in_graph = sorted(active_names)
            raise TopologyCompilationError(
                f"Graph compilation failed: {len(unregistered)} node(s) have no forward target.\n"
                f"Nodes without forward: {unregistered}\n"
                f"Active nodes: {stage_names_in_graph}\n"
                f"Ensure the topology proposal or deterministic rules provide a forward edge for each stage."
            )

        # ── 6. Register post → __end__ ─────────────────────────────────
        if "post" in active_names:
            builder.add_edge("post", END)
            topology.edges.append(
                {
                    "from": "post",
                    "to": "__end__",
                    "type": "fixed",
                }
            )

    def _add_meta_node_edges(
        self,
        builder: StateGraph,
        active_names: set[str],
        rules: list[EdgeRule],
        state: dict[str, Any],
        topology: GraphTopology,
    ) -> None:
        """Register edges for meta nodes (dynamic-architect, meta-executor).

        These nodes have special routing that doesn't follow the standard pattern.
        """
        # dynamic-architect → meta-executor (if augment) OR init (if no augment)
        if "dynamic-architect" in active_names:
            builder.add_conditional_edges(
                "dynamic-architect",
                lambda s: (
                    (
                        (s.get("dynamic_plan") or {}).get("trigger") == "augment"
                        and (s.get("dynamic_plan") or {}).get("steps")
                    )
                    and "meta-executor"
                    or "init"
                ),
                ["meta-executor", "init"],
            )
            topology.edges.append(
                {
                    "from": "dynamic-architect",
                    "to": "meta-executor",
                    "type": "conditional",
                    "description": "Augment → meta executor",
                }
            )
            topology.edges.append(
                {
                    "from": "dynamic-architect",
                    "to": "init",
                    "type": "conditional",
                    "description": "No augmentation → pipeline",
                }
            )

        # meta-executor: self-loop (running) → init (completed) → __end__ (blocked)
        if "meta-executor" in active_names:
            builder.add_conditional_edges(
                "meta-executor",
                lambda s: (
                    "__end__"
                    if s.get("dynamic_runtime", {}).get("status") in ("blocked",)
                    else "init"
                    if s.get("dynamic_runtime", {}).get("status") == "completed"
                    else "meta-executor"
                ),
                {"meta-executor": "meta-executor", "init": "init", "__end__": END},
            )
            topology.edges.append(
                {
                    "from": "meta-executor",
                    "to": "meta-executor",
                    "type": "conditional",
                    "description": "Self-loop (running)",
                }
            )
            topology.edges.append(
                {
                    "from": "meta-executor",
                    "to": "init",
                    "type": "conditional",
                    "description": "All dynamic steps done → pipeline",
                }
            )
            topology.edges.append(
                {
                    "from": "meta-executor",
                    "to": "__end__",
                    "type": "conditional",
                    "description": "Dynamic step blocked → terminate",
                }
            )

    def _add_parallel_qa_new(
        self,
        builder: StateGraph,
        active_names: set[str],
        rules: list[EdgeRule],
        state: dict[str, Any],
        topology: GraphTopology,
    ) -> None:
        """Register fan-out/fan-in edges for parallel QA using static edges.

        The dispatcher fans out to all active QA workers (static edges).
        Each worker has a fixed edge to qa-join.
        No Command/Send remains — routing is purely edge-based.
        """
        from eng_loop.nodes.qa_parallel import _get_active_qa_nodes

        qa_nodes = _get_active_qa_nodes(state)
        if len(qa_nodes) < 2:
            return

        # Find upstream: e2e-execute (preferred) or verify
        upstream_nodes = []
        if "e2e-execute" in active_names:
            upstream_nodes.append("e2e-execute")
        elif "verify" in active_names:
            upstream_nodes.append("verify")

        if not upstream_nodes:
            return

        # Register qa-dispatcher and qa-join as nodes
        from eng_loop.nodes.qa_parallel import qa_dispatcher_node, qa_join_node

        builder.add_node("qa-dispatcher", qa_dispatcher_node)
        builder.add_node("qa-join", qa_join_node)
        active_names.add("qa-dispatcher")
        active_names.add("qa-join")

        # Fan-out: upstream → qa-dispatcher (static edge)
        for upstream in upstream_nodes:
            builder.add_edge(upstream, "qa-dispatcher")
            topology.edges.append(
                {
                    "from": upstream,
                    "to": "qa-dispatcher",
                    "type": "fixed",
                }
            )

        # Fan-out: qa-dispatcher → each QA worker (static edges)
        for qa_node in qa_nodes:
            builder.add_edge("qa-dispatcher", qa_node)
            topology.edges.append(
                {
                    "from": "qa-dispatcher",
                    "to": qa_node,
                    "type": "fixed",
                }
            )

        # Fan-in: each QA worker → qa-join (static edges)
        for qa_node in qa_nodes:
            builder.add_edge(qa_node, "qa-join")
            topology.edges.append(
                {
                    "from": qa_node,
                    "to": "qa-join",
                    "type": "fixed",
                }
            )

        # qa-join → deploy-prepare or impl-code (conditional)
        builder.add_conditional_edges(
            "qa-join",
            lambda s: self._route_qa_join(s),
            {"deploy-prepare": "deploy-prepare", "impl-code": "impl-code", "__end__": END},
        )
        topology.edges.append(
            {
                "from": "qa-join",
                "to": "deploy-prepare",
                "type": "conditional",
                "description": "PASS → deploy",
            }
        )
        topology.edges.append(
            {
                "from": "qa-join",
                "to": "impl-code",
                "type": "conditional",
                "description": "ROLLBACK → impl-code",
            }
        )
        topology.edges.append(
            {
                "from": "qa-join",
                "to": "__end__",
                "type": "conditional",
                "description": "BLOCKED → end",
            }
        )

    def _route_qa_join(self, state: dict[str, Any]) -> str:
        """Route from qa-join based on aggregated QA results.

        Returns: "deploy-prepare", "impl-code", or "__end__".
        """

        stages = state.get("stages", {})
        qa_results = state.get("qa_results", {})

        # Decision may be pre-computed by qa_join_node
        decision = qa_results.get("join", {}).get("decision", "")

        if not decision:
            # Fallback: compute from individual QA stage verdicts
            any_blocked = False
            any_critical_fail = False

            for stage_id, stage_data in stages.items():
                if not stage_id.startswith("qa."):
                    continue
                status = stage_data.get("status", "")
                verdict = stage_data.get("verdict", "")

                if status == "blocked" or verdict == "BLOCKED":
                    any_blocked = True
                    continue

                if verdict == "FAIL":
                    any_critical_fail = True

            if any_blocked:
                return "__end__"
            if any_critical_fail:
                return "impl-code"
            return "deploy-prepare"

        if decision == "rollback":
            return "impl-code"
        if decision == "blocked":
            return "__end__"
        return "deploy-prepare"

    def _route_unified(
        self,
        node_name: str,
        state: dict[str, Any],
        terminal_cond: Callable[[dict[str, Any]], bool],
        failure_target: str | None = None,
        forward_target: str | None = None,
    ) -> str:
        """Unified routing evaluator for all stage nodes.

        Priority order (mutually exclusive by construction):
        20  terminal:    status in (blocked, waiting_for_input) → __end__
        10  rollback:    verdict == "FAIL" → failure target
        10  self-retry:  not done and verdict != "FAIL" → self
        0   forward:     done → forward target
        """
        # Priority 20: Terminal
        if terminal_cond(state):
            _trace.route_decision(
                function="_route_unified",
                decision="__end__",
                reason=f"terminal: status={state.get('status')}",
                state_snippet={"node": node_name, "status": state.get("status")},
            )
            return "__end__"

        # Priority 10: Rollback (verdict == FAIL)
        if failure_target:
            stages = state.get("stages", {})
            stage_data = stages.get(node_name.replace("-", "."), {})
            verdict = stage_data.get("verdict", "")
            if verdict == "FAIL":
                _trace.route_decision(
                    function="_route_unified",
                    decision=failure_target,
                    reason="rollback: verdict=FAIL",
                    state_snippet={"node": node_name, "verdict": verdict},
                )
                return failure_target

        # Self-retry: not done and verdict != FAIL
        stages = state.get("stages", {})
        stage_data = stages.get(node_name.replace("-", "."), {})
        done = stage_data.get("done", False)
        verdict = stage_data.get("verdict", "")

        if not done and verdict != "FAIL":
            _trace.route_decision(
                function="_route_unified",
                decision=node_name,
                reason=f"self-retry: done={done}, verdict={verdict!r}",
                state_snippet={"node": node_name, "done": done, "verdict": verdict},
            )
            return node_name

        # Forward: done
        if forward_target:
            _trace.route_decision(
                function="_route_unified",
                decision=forward_target,
                reason="forward: done=True",
                state_snippet={"node": node_name, "done": True},
            )
            return forward_target

        # Default: terminal (safety net)
        _trace.route_decision(
            function="_route_unified",
            decision="__end__",
            reason="no route matched (safety terminal)",
            state_snippet={"node": node_name},
        )
        return "__end__"

    def _add_parallel_qa(
        self,
        builder: StateGraph,
        active_specs: list[NodeSpec],
        active_names: set[str],
        state: dict[str, Any],
        topology: GraphTopology,
    ) -> None:
        """Add fan-out/fan-in for QA stages using LangGraph Send.

        Supports multiple parallel groups:
        - qa-post-e2e: security + performance (after E2E)
        - qa-human: human.flow + human.ux (after security/performance)

        IMPORTANT: qa-dispatcher and qa-join are NOT in the registry.
        They are added here directly. No fixed edges are declared for the
        fan-out/fan-in: upstream and worker nodes route to the dispatcher and
        join via Command (see routing invariant in _add_edges).
        """
        from eng_loop.nodes.qa_parallel import (
            PARALLEL_GROUPS,
            qa_dispatcher_node,
            qa_join_node,
        )

        qa_specs = [s for s in active_specs if s.parallel_group == "qa"]
        if len(qa_specs) < 2:
            return

        qa_node_names = [s.node_name for s in qa_specs]
        topology.parallel_groups["qa"] = qa_node_names

        # Add dispatcher and join nodes directly (not via registry)
        builder.add_node("qa-dispatcher", qa_dispatcher_node)
        builder.add_node("qa-join", qa_join_node)
        active_names.add("qa-dispatcher")
        active_names.add("qa-join")

        # Find upstream: e2e-execute (preferred) or verify
        upstream_nodes = []
        if "e2e-execute" in active_names:
            upstream_nodes.append("e2e-execute")
        elif "verify" in active_names:
            upstream_nodes.append("verify")

        if not upstream_nodes:
            logger.warning("qa parallel: no upstream node found, skipping")
            return

        # Routing is Command-only (routing invariant: no declared edges out of
        # command-routed nodes — LangGraph would evaluate a declared edge in
        # parallel with the Command's goto, causing double execution when the
        # targets diverge):
        #   - upstream (verify / e2e-execute) → Command(goto="qa-dispatcher")
        #     when _parallel_dispatch_active(state) matches this wiring
        #   - each QA worker → Command(goto="qa-join") in parallel mode
        #     (fan-in via Command is validated: the join waits for all workers)
        # The upstream→qa-dispatcher and qa→qa-join fixed edges are therefore
        # redundant and intentionally NOT added.

        # qa-join owns its routing via Command (PASS→deploy-prepare,
        # FAIL→impl-code, BLOCKED→__end__). NO conditional edge is registered:
        # LangGraph would evaluate it in parallel with the Command's goto,
        # running deploy-prepare even on BLOCKED/FAIL (double execution).

        # Record parallel groups in topology
        for group_name, group_nodes in PARALLEL_GROUPS.items():
            active_in_group = [n for n in group_nodes if n in active_names]
            if len(active_in_group) >= 2:
                topology.parallel_groups[group_name] = active_in_group

        logger.info(
            "  Parallel QA: %s → qa-dispatcher → [%s] → qa-join → deploy-prepare",
            upstream_nodes,
            ", ".join(qa_node_names),
        )

    def _to_node_name(self, stage_id: str) -> str:
        if stage_id in ("__start__", "__end__", "START", "END"):
            return stage_id
        return stage_id.replace(".", "-").replace("_", "-")


def build_dynamic_graph(
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
    authorized_topology: AuthorizedGraphTopology | None = None,
) -> tuple[Any, GraphTopology]:
    parallel_qa = (config or {}).get("dynamic_graph", {}).get("parallel_qa", False)
    # Single source of truth: nodes read the effective parallel-QA mode from
    # state config for routing decisions (e.g. verify → qa-dispatcher).
    state.setdefault("config", {}).setdefault("dynamic_graph", {})["parallel_qa"] = parallel_qa
    builder = GraphBuilder(parallel_qa=parallel_qa)
    return builder.compile(state, config, checkpointer, authorized_topology=authorized_topology)

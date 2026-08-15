from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from eng_loop.edge_rules import EdgeRule, EdgeRulesEngine, build_edge_rules
from eng_loop.node_registry import NodeRegistry, NodeSpec, build_registry
from eng_loop.state import PipelineState
from eng_loop.tools.contract_gate import CONTRACT_RULES, with_contract_gate
from eng_loop.tools.progress import trace_node

logger = logging.getLogger(__name__)


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
    ) -> tuple[StateGraph, GraphTopology]:
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
        active_ids = {s.id for s in active_specs}
        active_node_names = {s.node_name for s in active_specs}

        topology = GraphTopology()
        topology.complexity = complexity
        topology.ui_project = ui_project
        topology.total_available = len(self.registry)
        topology.nodes_included = len(active_specs)
        topology.active_nodes = [s.id for s in active_specs]

        builder = StateGraph(PipelineState)

        # Register active nodes
        for spec in active_specs:
            handler = trace_node(spec.id)(spec.handler)
            # Apply contract gate for nodes that have outgoing contract rules
            if spec.node_name in _get_contract_sources():
                handler = with_contract_gate(spec.node_name)(handler)
            builder.add_node(spec.node_name, handler)
            logger.info("  Node registered: %s (%s)", spec.node_name, spec.description)

        bypassed_rules = self.rules.resolve_with_bypass(
            active_node_names | {"__start__"}, state
        )
        self._add_edges(builder, bypassed_rules, active_node_names, state, topology)

        if self.parallel_qa:
            self._add_parallel_qa(builder, active_specs, active_node_names, state, topology)

        logger.info(
            "Graph built: %d/%d nodes active (complexity=%s, ui=%s)",
            len(active_specs), len(self.registry), complexity, ui_project,
        )

        return builder, topology

    def compile(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
        checkpointer: Any | None = None,
        interrupt_before: list[str] | None = None,
    ) -> tuple[Any, GraphTopology]:
        builder, topology = self.build(state, config)
        kwargs: dict[str, Any] = {}
        if checkpointer:
            kwargs["checkpointer"] = checkpointer
        elif interrupt_before:
            kwargs["checkpointer"] = MemorySaver()
        if interrupt_before:
            kwargs["interrupt_before"] = interrupt_before
        compiled = builder.compile(**kwargs)
        return compiled, topology

    def _add_edges(
        self,
        builder: StateGraph,
        rules: list[EdgeRule],
        active_names: set[str],
        state: dict[str, Any],
        topology: GraphTopology,
    ) -> None:
        fixed_edges: dict[str, list[str]] = {}
        conditional_sources: dict[str, list[EdgeRule]] = {}

        for rule in rules:
            from_name = self._to_node_name(rule.from_node)
            to_name = self._to_node_name(rule.to_node)

            if rule.edge_type == "fixed":
                fixed_edges.setdefault(from_name, []).append(to_name)
                topology.edges.append({
                    "from": rule.from_node,
                    "to": rule.to_node,
                    "type": "fixed",
                })
            else:
                conditional_sources.setdefault(from_name, []).append(rule)

        for from_name, to_names in fixed_edges.items():
            if from_name not in active_names:
                continue
            for to_name in to_names:
                if to_name == "__end__":
                    builder.add_edge(from_name, END)
                elif to_name == "__start__":
                    builder.add_edge(START, from_name)
                elif to_name in active_names:
                    builder.add_edge(from_name, to_name)

        start_targets = fixed_edges.get("__start__", [])
        for target in start_targets:
            if target in active_names:
                builder.add_edge(START, target)

        for from_name, cond_rules in conditional_sources.items():
            if from_name not in active_names:
                continue

            choices: dict[str, Any] = {}
            for rule in cond_rules:
                label = rule.to_node
                to_name = self._to_node_name(rule.to_node)
                if to_name == "__end__":
                    choices[label] = END
                elif to_name == "__start__":
                    choices[label] = START
                else:
                    choices[label] = to_name

            if "__end__" not in choices:
                choices["__end__"] = END

            rules_capture = list(cond_rules)
            builder.add_conditional_edges(
                from_name,
                lambda s, r=rules_capture: self._route(r, s),
                choices,
            )

    def _route(self, rules: list[EdgeRule], state: dict[str, Any]) -> str:
        for rule in rules:
            if rule.evaluate(state):
                return rule.to_node
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

        Replaces the sequential QA chain with:
        verify/e2e → qa-dispatcher → [Send(qa-security), Send(qa-api), ...] → qa-join → deploy

        IMPORTANT: qa-dispatcher and qa-join are NOT in the registry.
        They are added here directly. The edge_rules parallel_qa block
        does NOT add verify→qa-dispatcher edges (those are added here).
        """
        from eng_loop.nodes.qa_parallel import qa_dispatcher_node, qa_join_node

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

        # Find upstream: verify (non-UI) or e2e-execute (UI)
        upstream_nodes = []
        if "verify" in active_names:
            upstream_nodes.append("verify")
        if "e2e-execute" in active_names:
            upstream_nodes.append("e2e-execute")

        if not upstream_nodes:
            logger.warning("qa parallel: no upstream node found, skipping")
            return

        # Replace verify/e2e → qa edges with verify/e2e → qa-dispatcher
        # The dispatcher uses Send API to fan-out to QA nodes
        for upstream in upstream_nodes:
            builder.add_edge(upstream, "qa-dispatcher")

        # qa-dispatcher returns list[Send] which handles routing directly.
        # No conditional edges needed — each Send targets a QA node.

        # Each QA node → qa-join (replaces sequential QA chain)
        for qa_name in qa_node_names:
            builder.add_edge(qa_name, "qa-join")

        # qa-join → deploy-prepare (or impl-code on rollback)
        builder.add_conditional_edges(
            "qa-join",
            lambda s: "deploy-prepare",
            path_map={
                "deploy-prepare": "deploy-prepare",
                "impl-code": "impl-code",
                "__end__": END,
            },
        )

        logger.info(
            "  Parallel QA: %s → qa-dispatcher → [%s] → qa-join → deploy-prepare",
            upstream_nodes, ", ".join(qa_node_names),
        )

    def _to_node_name(self, stage_id: str) -> str:
        if stage_id in ("__start__", "__end__", "START", "END"):
            return stage_id
        return stage_id.replace(".", "-").replace("_", "-")


def build_dynamic_graph(
    state: dict[str, Any],
    config: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
) -> tuple[Any, GraphTopology]:
    parallel_qa = (config or {}).get("dynamic_graph", {}).get("parallel_qa", False)
    builder = GraphBuilder(parallel_qa=parallel_qa)
    return builder.compile(state, config, checkpointer)

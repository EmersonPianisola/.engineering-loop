from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from eng_loop.graph_builder import GraphBuilder
from eng_loop.nodes.architecture import arch_node, get_arch_nodes
from eng_loop.nodes.deploy import deploy_prepare_node, smoke_test_node

# Legacy imports — kept for backward compatibility with existing tests
from eng_loop.nodes.design import design_node, get_design_nodes
from eng_loop.nodes.documentation import doc_decisions_node, doc_project_node
from eng_loop.nodes.implementation import doc_update_node, impl_code_node, impl_design_node
from eng_loop.nodes.init import init_bdd_node, init_ideate_node, init_node, init_refine_node
from eng_loop.nodes.post import post_node
from eng_loop.nodes.qa import get_qa_nodes, qa_node
from eng_loop.nodes.verification import e2e_execute_node, verify_node
from eng_loop.routing import (
    route_arch_complete,
    route_deploy_result,
    route_design_complete,
    route_e2e_result,
    route_init_complete,
    route_qa_result,
    route_smoke_result,
    route_verify_result,
)
from eng_loop.state import PipelineState
from eng_loop.tools.progress import trace_node


def build_graph() -> StateGraph:
    """Build the static graph (legacy mode — all 28 nodes, hardcoded edges).

    Used when dynamic_graph is disabled. Preserves exact v10 behavior.
    """
    builder = StateGraph(PipelineState)

    # --- Register nodes ---
    builder.add_node("init", trace_node("init")(init_node))
    builder.add_node("init-ideate", trace_node("init.ideate")(init_ideate_node))
    builder.add_node("init-bdd", trace_node("init.bdd")(init_bdd_node))
    builder.add_node("init-refine", trace_node("init.refine")(init_refine_node))

    builder.add_node("impl-design", trace_node("impl.design")(impl_design_node))
    builder.add_node("impl-code", trace_node("impl.code")(impl_code_node))
    builder.add_node("doc-update", trace_node("doc.update")(doc_update_node))

    builder.add_node("verify", trace_node("verify")(verify_node))
    builder.add_node("e2e-execute", trace_node("e2e.execute")(e2e_execute_node))

    builder.add_node("deploy-prepare", trace_node("deploy.prepare")(deploy_prepare_node))
    builder.add_node("smoke-test", trace_node("smoke.test")(smoke_test_node))

    builder.add_node("doc-decisions", trace_node("doc.decisions")(doc_decisions_node))
    builder.add_node("doc-project", trace_node("doc.project")(doc_project_node))
    builder.add_node("post", trace_node("post")(post_node))

    # Design stages
    for node_name, stage_id in get_design_nodes():
        builder.add_node(node_name, trace_node(stage_id)(design_node(stage_id)))

    # Architecture stages
    for node_name, stage_id in get_arch_nodes():
        builder.add_node(node_name, trace_node(stage_id)(arch_node(stage_id)))

    # QA stages
    for node_name, stage_id in get_qa_nodes():
        builder.add_node(node_name, trace_node(stage_id)(qa_node(stage_id)))

    # --- Entry point ---
    builder.add_edge(START, "init")

    # --- Init chain ---
    builder.add_conditional_edges(
        "init",
        route_init_complete,
        {
            "init-ideate": "init-ideate",
            "__end__": END,
        },
    )

    builder.add_edge("init-ideate", "init-bdd")
    builder.add_edge("init-bdd", "init-refine")

    builder.add_conditional_edges(
        "init-refine",
        lambda s: _post_init_refine(s),
        {
            "arch-requirements": "arch-requirements",
            "impl-design": "impl-design",
        },
    )

    # --- Design chain ---
    builder.add_edge("design-user-research", "design-personas")
    builder.add_edge("design-personas", "design-info-arch")
    builder.add_edge("design-info-arch", "design-interaction")
    builder.add_edge("design-interaction", "design-design-system")
    builder.add_edge("design-design-system", "design-visual-design")

    builder.add_conditional_edges(
        "design-visual-design",
        route_design_complete,
        {
            "arch-requirements": "arch-requirements",
            "impl-design": "impl-design",
        },
    )

    # --- Architecture chain ---
    builder.add_edge("arch-requirements", "arch-solution")

    builder.add_conditional_edges(
        "arch-solution",
        route_arch_complete,
        {
            "arch-review": "arch-review",
            "impl-design": "impl-design",
        },
    )

    builder.add_edge("arch-review", "impl-design")

    # --- Implementation chain ---
    builder.add_edge("impl-design", "impl-code")
    builder.add_edge("impl-code", "doc-update")
    builder.add_edge("doc-update", "verify")

    # --- Verification ---
    builder.add_conditional_edges(
        "verify",
        route_verify_result,
        {
            "impl-code": "impl-code",
            "qa-static": "qa-static",
            "e2e-execute": "e2e-execute",
            "qa-security": "qa-security",
            "deploy-prepare": "deploy-prepare",
        },
    )

    # --- QA: Static Analysis ---
    builder.add_conditional_edges(
        "qa-static",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "qa-unit": "qa-unit",
        },
    )

    # --- QA: Unit Testing ---
    builder.add_conditional_edges(
        "qa-unit",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "qa-integration": "qa-integration",
            "e2e-execute": "e2e-execute",
        },
    )

    # --- QA: Integration ---
    builder.add_conditional_edges(
        "qa-integration",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "e2e-execute": "e2e-execute",
        },
    )

    # --- E2E ---
    builder.add_conditional_edges(
        "e2e-execute",
        route_e2e_result,
        {
            "impl-code": "impl-code",
            "qa-security": "qa-security",
            "qa-human-flow": "qa-human-flow",
            "deploy-prepare": "deploy-prepare",
        },
    )

    # --- QA chain (post-E2E) ---
    builder.add_conditional_edges(
        "qa-security",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "qa-performance": "qa-performance",
            "qa-human-flow": "qa-human-flow",
            "deploy-prepare": "deploy-prepare",
        },
    )

    builder.add_conditional_edges(
        "qa-performance",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "qa-human-flow": "qa-human-flow",
            "deploy-prepare": "deploy-prepare",
        },
    )

    # --- QA: Human Flow ---
    builder.add_conditional_edges(
        "qa-human-flow",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "qa-human-ux": "qa-human-ux",
            "deploy-prepare": "deploy-prepare",
        },
    )

    # --- QA: Human UX ---
    builder.add_conditional_edges(
        "qa-human-ux",
        route_qa_result,
        {
            "impl-code": "impl-code",
            "deploy-prepare": "deploy-prepare",
        },
    )

    # --- Deploy ---
    builder.add_conditional_edges(
        "deploy-prepare",
        route_deploy_result,
        {
            "impl-code": "impl-code",
            "smoke-test": "smoke-test",
            "doc-decisions": "doc-decisions",
            "post": "post",
        },
    )

    builder.add_conditional_edges(
        "smoke-test",
        route_smoke_result,
        {
            "impl-code": "impl-code",
            "doc-decisions": "doc-decisions",
            "post": "post",
        },
    )

    # --- Documentation ---
    builder.add_edge("doc-decisions", "doc-project")
    builder.add_edge("doc-project", "post")

    # --- Post ---
    builder.add_edge("post", END)

    return builder


def _post_init_refine(state: dict[str, Any]) -> str:
    complexity = state.get("complexity", "small")
    if complexity in ("medium", "large", "complex"):
        return "arch-requirements"
    return "impl-design"


def compile_graph(
    config: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
    dynamic: bool = False,
    state: dict[str, Any] | None = None,
) -> Any:
    """Compile the graph.

    Args:
        config: Framework configuration.
        checkpointer: Optional LangGraph checkpointer for persistence.
        dynamic: If True, use dynamic graph construction (v11).
        state: Required when dynamic=True — used to determine active nodes.

    Returns:
        Compiled LangGraph graph (or tuple with topology if dynamic).
    """
    if dynamic and state is not None:
        parallel_qa = (config or {}).get("dynamic_graph", {}).get("parallel_qa", False)
        builder = GraphBuilder(parallel_qa=parallel_qa)
        compiled, topology = builder.compile(state, config, checkpointer)
        return compiled, topology
    else:
        builder = build_graph()
        kwargs: dict[str, Any] = {}
        if checkpointer:
            kwargs["checkpointer"] = checkpointer
        return builder.compile(**kwargs)

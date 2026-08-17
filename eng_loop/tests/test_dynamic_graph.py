from __future__ import annotations

from eng_loop.edge_rules import (
    build_edge_rules,
)
from eng_loop.graph_builder import GraphBuilder
from eng_loop.node_registry import (
    build_registry,
    complexity_meets,
)
from eng_loop.state import make_initial_state


def test_complexity_meets():
    assert complexity_meets("small", "small") is True
    assert complexity_meets("medium", "small") is True
    assert complexity_meets("medium", "medium") is True
    assert complexity_meets("small", "medium") is False
    assert complexity_meets("complex", "large") is True
    assert complexity_meets("large", "complex") is False


def test_registry_builds():
    registry = build_registry()
    assert len(registry) == 34
    assert "init" in registry
    assert "impl.code" in registry
    assert "post" in registry


def test_registry_filter_small():
    registry = build_registry()
    active = registry.filter(complexity="small", ui_project=False)
    active_ids = {s.id for s in active}

    assert "init" in active_ids
    assert "impl.code" in active_ids
    assert "verify" in active_ids
    assert "post" in active_ids
    assert "design.user-research" not in active_ids
    assert "arch.requirements" not in active_ids
    assert "qa.security" not in active_ids
    assert "e2e.execute" not in active_ids


def test_registry_filter_medium():
    registry = build_registry()
    active = registry.filter(complexity="medium", ui_project=False)
    active_ids = {s.id for s in active}

    assert "arch.requirements" in active_ids
    assert "arch.solution" in active_ids
    assert "qa.security" in active_ids
    assert "qa.api-contract" in active_ids
    assert "doc.decisions" in active_ids
    assert "design.user-research" not in active_ids
    assert "arch.review" not in active_ids
    assert "qa.performance" not in active_ids


def test_registry_filter_large_ui():
    registry = build_registry()
    active = registry.filter(complexity="large", ui_project=True)
    active_ids = {s.id for s in active}

    assert "design.user-research" in active_ids
    assert "design.visual-design" in active_ids
    assert "e2e.execute" in active_ids
    assert "smoke.test" in active_ids
    assert "arch.review" not in active_ids
    assert "qa.performance" not in active_ids


def test_registry_filter_complex():
    registry = build_registry()
    active = registry.filter(complexity="complex", ui_project=True)
    active_ids = {s.id for s in active}

    assert "arch.review" in active_ids
    assert "qa.performance" in active_ids
    assert "e2e.execute" in active_ids
    assert "smoke.test" in active_ids


def test_registry_parallel_groups():
    registry = build_registry()
    groups = registry.get_parallel_groups()
    assert "qa" in groups
    qa_nodes = groups["qa"]
    assert len(qa_nodes) == 8
    qa_ids = {s.id for s in qa_nodes}
    assert "qa.security" in qa_ids
    assert "qa.api-contract" in qa_ids
    assert "qa.performance" in qa_ids
    assert "qa.static" in qa_ids
    assert "qa.unit" in qa_ids
    assert "qa.integration" in qa_ids
    assert "qa.human.flow" in qa_ids
    assert "qa.human.ux" in qa_ids


def test_registry_phase_grouping():
    registry = build_registry()
    init_nodes = registry.get_by_phase("init")
    assert len(init_nodes) == 4

    design_nodes = registry.get_by_phase("design")
    assert len(design_nodes) == 6

    qa_nodes = registry.get_by_phase("qa")
    assert len(qa_nodes) == 8


def test_edge_rules_build():
    engine = build_edge_rules()
    rules = engine.get_rules_for_node("init")
    assert len(rules) >= 2


def test_edge_rules_resolve_active():
    engine = build_edge_rules()
    active = {"init", "init-ideate", "impl-code", "verify", "deploy-prepare", "post", "__end__"}
    state = {
        "complexity": "small",
        "ui_project": False,
        "stages": {
            "init": {"done": True, "attempts": 1},
            "init.refine": {"done": True, "attempts": 1},
            "verify": {"done": True, "attempts": 1},
        },
    }
    resolved = engine.resolve(active, state)
    assert len(resolved) > 0


def test_graph_builder_small():
    state = make_initial_state({}, {})
    state["complexity"] = "small"
    state["ui_project"] = False

    builder = GraphBuilder()
    _graph_builder, topology = builder.build(state)

    assert topology.nodes_included < topology.total_available
    assert "init" in topology.active_nodes
    assert "impl.code" in topology.active_nodes
    assert "post" in topology.active_nodes
    assert "design.user-research" not in topology.active_nodes
    assert "arch.requirements" not in topology.active_nodes


def test_graph_builder_complex():
    state = make_initial_state({}, {})
    state["complexity"] = "complex"
    state["ui_project"] = True

    builder = GraphBuilder()
    _graph_builder, topology = builder.build(state)

    assert topology.nodes_included == topology.total_available
    assert "arch.review" in topology.active_nodes
    assert "qa.performance" in topology.active_nodes
    assert "e2e.execute" in topology.active_nodes


def test_graph_topology_serialization():
    state = make_initial_state({}, {})
    state["complexity"] = "medium"
    state["ui_project"] = False

    builder = GraphBuilder()
    _, topology = builder.build(state)

    topo_dict = topology.to_dict()
    assert "active_nodes" in topo_dict
    assert "edges" in topo_dict
    assert "complexity" in topo_dict
    assert topo_dict["complexity"] == "medium"

    json_str = topology.to_json()
    assert "medium" in json_str


def test_graph_compiles():
    state = make_initial_state({}, {})
    state["complexity"] = "small"
    state["ui_project"] = False

    builder = GraphBuilder()
    compiled, _topology = builder.compile(state)
    assert compiled is not None


def test_topology_markdown_generation():
    """Test that topology markdown is generated correctly."""
    from eng_loop.cli import _topology_to_markdown
    from eng_loop.graph_builder import GraphBuilder

    state = make_initial_state({}, {})
    state["complexity"] = "small"
    state["ui_project"] = False
    state["work_type"] = "feature"

    builder = GraphBuilder()
    _, topology = builder.build(state)

    md = _topology_to_markdown(
        topology,
        "Fix typo in README",
        "small",
        "feature",
        False,
        {},
    )

    assert "# DYNAMIC GRAPH TOPOLOGY" in md
    assert "Fix typo in README" in md
    assert "small" in md
    assert "## ACTIVE STAGES" in md
    assert "## ROUTING RULES" in md
    assert "## CONSTRAINTS" in md
    assert "impl.code" in md
    assert "Work Type: feature" in md
    assert "## STAGE CHECKLIST" in md
    assert "## STAGE SCOPE" in md
    assert "## DEACTIVATED STAGES" in md
    assert "verify" in md
    # design.user-research is deactivated for small, appears in DEACTIVATED section
    assert "design.user-research" in md
    # Verify it's in the deactivated section, not active
    deactivated_idx = md.index("## DEACTIVATED STAGES")
    active_idx = md.index("## ACTIVE STAGES")
    assert deactivated_idx > active_idx  # Active comes first
    assert md.index("design.user-research") > deactivated_idx  # In deactivated section


def test_node_spec_attributes():
    registry = build_registry()
    spec = registry.get("impl.code")
    assert spec is not None
    assert spec.id == "impl.code"
    assert spec.node_name == "impl-code"
    assert spec.phase == "impl"
    assert spec.min_complexity == "small"
    assert spec.requires_ui is False

    e2e_spec = registry.get("e2e.execute")
    assert e2e_spec is not None
    assert e2e_spec.requires_ui is True

    qa_spec = registry.get("qa.security")
    assert qa_spec is not None
    assert qa_spec.parallel_group == "qa"


if __name__ == "__main__":
    test_complexity_meets()
    test_registry_builds()
    test_registry_filter_small()
    test_registry_filter_medium()
    test_registry_filter_large_ui()
    test_registry_filter_complex()
    test_registry_parallel_groups()
    test_registry_phase_grouping()
    test_edge_rules_build()
    test_edge_rules_resolve_active()
    test_graph_builder_small()
    test_graph_builder_complex()
    test_graph_topology_serialization()
    test_graph_compiles()
    test_topology_markdown_generation()
    test_node_spec_attributes()
    print("All dynamic graph tests passed.")

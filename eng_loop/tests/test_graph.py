from __future__ import annotations

from eng_loop.graph import build_graph, compile_graph
from eng_loop.state import STAGE_ORDER


def test_graph_compiles():
    graph = compile_graph()
    assert graph is not None


def test_graph_has_all_nodes():
    graph = compile_graph()
    g = graph.get_graph()
    node_names = list(g.nodes)

    assert "__start__" in node_names
    assert "__end__" in node_names
    assert "init" in node_names
    assert "post" in node_names

    for sid in STAGE_ORDER:
        expected = sid.replace(".", "-").replace("_", "-")
        assert expected in node_names, f"Missing node: {expected}"


def test_graph_node_count():
    graph = compile_graph()
    g = graph.get_graph()
    nodes = list(g.nodes)
    assert len(nodes) == len(STAGE_ORDER) + 2


def test_builder_returns_stategraph():
    builder = build_graph()
    assert builder is not None


if __name__ == "__main__":
    test_graph_compiles()
    test_graph_has_all_nodes()
    test_graph_node_count()
    test_builder_returns_stategraph()
    print("All graph tests passed.")

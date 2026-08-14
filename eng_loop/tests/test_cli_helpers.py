from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from eng_loop.cli import (
    _build_topology,
    _check_model,
    _format_size,
    _is_active,
    _make_saveable,
    _topology_to_markdown,
)
from eng_loop.graph_builder import GraphTopology

# ── _format_size ─────────────────────────────────────────────────────


def test_format_size_bytes():
    assert _format_size(500) == "500B"


def test_format_size_1023_bytes():
    assert _format_size(1023) == "1023B"


def test_format_size_kb():
    assert _format_size(2048) == "2.0KB"


def test_format_size_large_kb():
    assert _format_size(102400) == "100.0KB"


def test_format_size_mb():
    assert _format_size(15728640) == "15.0MB"


def test_format_size_zero():
    assert _format_size(0) == "0B"


# ── _make_saveable ───────────────────────────────────────────────────


def _make_sample_state() -> dict[str, Any]:
    return {
        "iteration": 3,
        "status": "running",
        "blocking_condition": "",
        "complexity": "medium",
        "work_type": "feature",
        "work_item": "Add login feature",
        "ideation": {"notes": "brainstormed"},
        "ui_project": True,
        "stages": {"init": {"done": True, "attempts": 1}},
        "decisions": [{"decision": "use oauth"}],
        "stage_artifacts": {"init": "init.md"},
        "lessons": ["learned something"],
        "errors": [],
        "handoffs": {},
        "context_tiers": {},
        "tags": ["auth"],
        "active_nodes": ["init", "impl.code"],
        "graph_topology": {},
        "parallel_groups": {},
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_make_saveable_includes_all_keys():
    state = _make_sample_state()
    result = _make_saveable(state)

    assert result["iteration"] == 3
    assert result["status"] == "running"
    assert result["blocking_condition"] == ""
    assert result["complexity"] == "medium"
    assert result["work_type"] == "feature"
    assert result["work_item"] == "Add login feature"
    assert result["ideation"] == {"notes": "brainstormed"}
    assert result["ui_project"] is True
    assert result["stages"] == {"init": {"done": True, "attempts": 1}}
    assert result["decisions"] == [{"decision": "use oauth"}]
    assert result["stage_artifacts"] == {"init": "init.md"}
    assert result["lessons"] == ["learned something"]
    assert result["errors"] == []
    assert result["handoffs"] == {}
    assert result["context_tiers"] == {}
    assert result["tags"] == ["auth"]
    assert result["active_nodes"] == ["init", "impl.code"]
    assert result["graph_topology"] == {}
    assert result["parallel_groups"] == {}


def test_make_saveable_excludes_non_serializable():
    state = _make_sample_state()
    result = _make_saveable(state)

    assert "messages" not in result


def test_make_saveable_empty_state():
    result = _make_saveable({})

    assert result["iteration"] == 0
    assert result["status"] == "running"
    assert result["blocking_condition"] == ""
    assert result["complexity"] == "unset"
    assert result["work_type"] == "feature"
    assert result["work_item"] == ""
    assert result["ideation"] is None
    assert result["ui_project"] is False
    assert result["stages"] == {}
    assert result["decisions"] == []
    assert result["stage_artifacts"] == {}
    assert result["lessons"] == []
    assert result["errors"] == []
    assert result["handoffs"] == {}
    assert result["context_tiers"] == {}
    assert result["tags"] == []
    assert result["active_nodes"] == []
    assert result["graph_topology"] == {}
    assert result["parallel_groups"] == {}


def test_make_saveable_includes_timing():
    state = _make_sample_state()
    result = _make_saveable(state)

    assert "timing" in result
    assert isinstance(result["timing"], dict)
    assert "loop_start" in result["timing"]
    assert "loop_elapsed" in result["timing"]
    assert "stages" in result["timing"]


# ── _is_active ───────────────────────────────────────────────────────


def test_is_active_small_all_basic():
    assert _is_active("init", "small", False) is True
    assert _is_active("impl.code", "small", False) is True
    assert _is_active("verify", "small", False) is True
    assert _is_active("post", "small", False) is True
    assert _is_active("deploy.prepare", "small", False) is True


def test_is_active_small_design_inactive():
    assert _is_active("design.user-research", "small", False) is False
    assert _is_active("design.personas", "small", False) is False
    assert _is_active("design.info-arch", "small", False) is False
    assert _is_active("design.interaction", "small", False) is False
    assert _is_active("design.design-system", "small", False) is False
    assert _is_active("design.visual-design", "small", False) is False


def test_is_active_medium_arch_active():
    assert _is_active("arch.requirements", "medium", False) is True
    assert _is_active("arch.solution", "medium", False) is True
    assert _is_active("qa.security", "medium", False) is True
    assert _is_active("qa.api-contract", "medium", False) is True


def test_is_active_e2e_no_ui():
    assert _is_active("e2e.execute", "medium", False) is False
    assert _is_active("e2e.execute", "large", False) is False
    assert _is_active("e2e.execute", "complex", False) is False


def test_is_active_smoke_no_ui():
    assert _is_active("smoke.test", "medium", False) is False
    assert _is_active("smoke.test", "large", False) is False
    assert _is_active("smoke.test", "complex", False) is False


def test_is_active_e2e_with_ui():
    assert _is_active("e2e.execute", "medium", True) is True
    assert _is_active("e2e.execute", "large", True) is True
    assert _is_active("smoke.test", "medium", True) is True
    assert _is_active("smoke.test", "large", True) is True


def test_is_active_unset_all_active():
    assert _is_active("init", "unset", False) is True
    assert _is_active("design.user-research", "unset", False) is True
    assert _is_active("arch.requirements", "unset", False) is True
    assert _is_active("e2e.execute", "unset", False) is True
    assert _is_active("smoke.test", "unset", False) is True
    assert _is_active("qa.performance", "unset", False) is True


# ── _build_topology ──────────────────────────────────────────────────


def test_build_topology_creates_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_root = str(Path(tmpdir) / "artifacts")
        Path(artifact_root).mkdir()

        paths = {"artifact_root": artifact_root}
        config = {}
        work_item = "Add search feature"

        mock_topology = MagicMock()
        mock_topology.active_nodes = ["init", "impl.code", "verify", "post"]
        mock_topology.edges = []
        mock_topology.parallel_groups = {}
        mock_topology.complexity = "small"
        mock_topology.ui_project = False
        mock_topology.total_available = 26
        mock_topology.nodes_included = 4
        mock_topology.to_dict.return_value = {
            "active_nodes": ["init", "impl.code", "verify", "post"],
            "edges": [],
            "parallel_groups": {},
            "complexity": "small",
            "ui_project": False,
            "total_available": 26,
            "nodes_included": 4,
        }

        mock_builder = MagicMock()
        mock_builder.build.return_value = (MagicMock(), mock_topology)

        with (
            patch("eng_loop.tools.autosizing.classify_complexity", return_value="small"),
            patch("eng_loop.tools.autosizing.classify_work_type", return_value="feature"),
            patch("eng_loop.tools.autosizing.detect_ui_project", return_value=False),
            patch("eng_loop.cli.make_initial_state", return_value={}),
            patch("eng_loop.graph_builder.GraphBuilder", return_value=mock_builder),
            patch("builtins.print"),
        ):
            _build_topology(work_item, config, paths)

            md_path = Path(artifact_root) / "graph-topology.md"
            json_path = Path(artifact_root) / "graph-topology.json"

            assert md_path.exists()
            assert json_path.exists()

            with open(json_path) as f:
                saved = json.load(f)

            assert saved["active_nodes"] == ["init", "impl.code", "verify", "post"]


# ── _topology_to_markdown ────────────────────────────────────────────


def _make_topology(active: list[str] | None = None, parallel: dict[str, list[str]] | None = None) -> GraphTopology:
    t = GraphTopology()
    t.active_nodes = active or ["init", "impl.code", "verify", "post"]
    t.edges = []
    t.parallel_groups = parallel or {}
    t.complexity = "small"
    t.ui_project = False
    t.total_available = 26
    t.nodes_included = len(t.active_nodes)
    return t


def test_topology_markdown_includes_work_item():
    topology = _make_topology()
    md = _topology_to_markdown(topology, "Fix the login bug", "small", "bugfix", False, {})
    assert "Fix the login bug" in md


def test_topology_markdown_includes_routing_rules():
    topology = _make_topology()
    md = _topology_to_markdown(topology, "Test item", "small", "feature", False, {})
    assert "## ROUTING RULES" in md
    assert "Post-Init-Refine" in md
    assert "Post-Verify" in md


def test_topology_markdown_includes_stage_checklist():
    topology = _make_topology()
    md = _topology_to_markdown(topology, "Test item", "small", "feature", False, {})
    assert "## STAGE CHECKLIST" in md
    assert "- [ ]" in md


def test_topology_markdown_includes_stage_scope():
    topology = _make_topology()
    md = _topology_to_markdown(topology, "Test item", "small", "feature", False, {})
    assert "## STAGE SCOPE" in md
    assert "ALLOWED:" in md
    assert "FORBIDDEN:" in md


def test_topology_markdown_deactivated_stages():
    topology = _make_topology()
    md = _topology_to_markdown(topology, "Test item", "small", "feature", False, {})
    assert "## DEACTIVATED STAGES" in md
    assert "design.user-research" in md


def test_topology_markdown_parallel_groups():
    topology = _make_topology(
        active=["init", "impl.code", "verify", "qa.security", "qa.api-contract", "qa.performance", "post"],
        parallel={"qa": ["qa.security", "qa.api-contract", "qa.performance"]},
    )
    topology.complexity = "complex"
    topology.nodes_included = len(topology.active_nodes)
    md = _topology_to_markdown(topology, "Test item", "complex", "feature", False, {})
    assert "## PARALLEL GROUPS" in md
    assert "qa.security" in md


def test_topology_markdown_constraints_table():
    topology = _make_topology()
    config = {"constraints": {"max_impl_code_attempts": 5}}
    md = _topology_to_markdown(topology, "Test item", "small", "feature", False, config)
    assert "## CONSTRAINTS" in md
    assert "| Stage | Max Attempts |" in md
    assert "|-------|-------------|" in md


# ── _check_model ─────────────────────────────────────────────────────


def test_check_model_success():
    mock_model = MagicMock()
    mock_model.invoke.return_value = MagicMock(content="OK")

    config = {"model": {"base_url": "http://localhost:8000", "model": "test-model"}}

    with patch("eng_loop.cli.create_model_from_config", return_value=mock_model):
        result = _check_model(config, quiet=True)

    assert result is True
    mock_model.invoke.assert_called_once()


def test_check_model_failure():
    mock_model = MagicMock()
    mock_model.invoke.side_effect = ConnectionError("network down")

    config = {"model": {"base_url": "http://localhost:8000", "model": "test-model"}}

    with patch("eng_loop.cli.create_model_from_config", return_value=mock_model):
        result = _check_model(config, quiet=True)

    assert result is False

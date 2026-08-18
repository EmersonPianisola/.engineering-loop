from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[2] / "skills"


def _make_state(
    *,
    stage_id: str = "init",
    essence_checked: bool = False,
    essence_enabled: bool = True,
) -> dict:
    """Build a minimal state dict for essence gate testing."""
    return {
        "stages": {
            stage_id: {
                "done": False,
                "attempts": 0,
                "essence_checked": essence_checked,
            }
        },
        "config": {
            "essence": {
                "enabled": essence_enabled,
                "skill": "essence",
                "capture_decisions": True,
                "context_file": "context.md",
            },
            "agent": {"max_agent_iterations": 5},
        },
        "paths": {
            "framework_skill_root": str(_skill_root()),
            "loop_root": str(Path(__file__).parent),
            "project_root": ".",
        },
        "work_item": "Test work item",
        "complexity": "small",
        "ui_project": False,
        "decisions": [],
        "stage_artifacts": {},
    }


def test_skip_when_essence_checked():
    """Essence gate should skip when stage is already essence_checked."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(essence_checked=True)
    result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False


def test_skip_when_disabled_config():
    """Essence gate should skip when config.essence.enabled is false."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(essence_enabled=False)
    result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False


def test_pass_clean_inputs():
    """Essence gate should pass when agent returns clean=True."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "summary": "All clear.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent", return_value=mock_result
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False
    assert result.updated_state is not None
    assert result.updated_state["stages"]["init"]["essence_checked"] is True


def test_block_lens_4_tension():
    """Essence gate should block when Lens 4 conflicts are found."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [
            {
                "goal_a": "Fast delivery",
                "goal_b": "Comprehensive testing",
                "tension": "Speed vs. thoroughness conflict",
                "requires_user_resolution": True,
            }
        ],
        "clean": False,
        "adjustments": [],
        "summary": "Lens 4 tension found.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent", return_value=mock_result
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.blocked is True
    assert "Speed vs. thoroughness conflict" in result.tension


def test_retry_lens_1_3_findings():
    """Essence gate should retry when Lens 1-3 findings need adjustments."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    # First call: returns adjustments (not clean)
    mock_adjust = MagicMock()
    mock_adjust.error = None
    mock_adjust.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Clarified 'robust' to mean error recovery"],
        "summary": "Adjustments applied.",
    }

    # Second call: returns clean
    mock_clean = MagicMock()
    mock_clean.error = None
    mock_clean.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "summary": "All clear after adjustment.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent", side_effect=[mock_adjust, mock_clean]
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False


def test_max_retries_exceeded():
    """Essence gate should proceed when max retries are exhausted."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()
    state["config"]["max_essence_retries_per_stage"] = 2

    # Always return adjustments (never clean)
    mock_adjust = MagicMock()
    mock_adjust.error = None
    mock_adjust.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Adjustment applied"],
        "summary": "Still needs work.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent", return_value=mock_adjust
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.updated_state["stages"]["init"]["essence_checked"] is True
    assert result.updated_state["stages"]["init"]["essence_retries_exceeded"] is True


def test_tools_read_only():
    """Essence gate should use only read and glob tools."""
    from eng_loop.tools.agent_tools import get_essence_tools

    tools = get_essence_tools({})
    tool_names = [t.name for t in tools]

    assert "read" in tool_names
    assert "glob" in tool_names
    assert "write" not in tool_names
    assert "edit" not in tool_names
    assert "bash" not in tool_names


def test_essence_output_schema():
    """EssenceOutput schema should validate correctly."""
    from eng_loop.schemas import (
        EssenceConflict,
        EssenceHiddenAssumption,
        EssenceLiteralTrap,
        EssenceOutput,
        EssenceSubjectiveTerm,
    )

    output = EssenceOutput(
        lens_1_subjective_terms=[
            EssenceSubjectiveTerm(
                term="robust",
                context="Make the API robust",
                interpretations=["network resilience", "error recovery"],
            )
        ],
        lens_2_hidden_assumptions=[
            EssenceHiddenAssumption(
                assumption="Payment service is always available",
                risk="Checkout flow fails if payment is down",
                severity="high",
            )
        ],
        lens_3_literal_traps=[
            EssenceLiteralTrap(
                phrasing="Fix the login",
                ambiguity="Fix bug? Improve UX? Add auth method?",
                likely_misinterpretation="LLM fixes most obvious bug",
            )
        ],
        lens_4_conflicts=[
            EssenceConflict(
                goal_a="Fast delivery",
                goal_b="Comprehensive testing",
                tension="Speed vs. thoroughness",
                requires_user_resolution=True,
            )
        ],
        clean=False,
        adjustments=["Clarified 'robust'"],
        summary="Findings across all lenses.",
    )

    assert len(output.lens_1_subjective_terms) == 1
    assert len(output.lens_2_hidden_assumptions) == 1
    assert len(output.lens_3_literal_traps) == 1
    assert len(output.lens_4_conflicts) == 1
    assert output.clean is False


def test_essence_gate_decorator():
    """The @essence_gate decorator should block on Lens 4 tensions."""
    from langgraph.types import Command

    from eng_loop.tools.essence_gate import essence_gate

    @essence_gate("test-stage")
    def mock_handler(state: dict) -> Command:
        return Command(goto="next", update={"stages": state.get("stages", {})})

    state = _make_state(stage_id="test-stage")

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [
            {
                "goal_a": "A",
                "goal_b": "B",
                "tension": "Conflict A vs B",
                "requires_user_resolution": True,
            }
        ],
        "clean": False,
        "adjustments": [],
        "summary": "Blocked.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent", return_value=mock_result
    ):
        result = mock_handler(state)

    assert result.goto == "__end__"
    assert result.update["status"] == "blocked"
    assert "Conflict A vs B" in result.update["blocking_condition"]


def test_essence_gate_decorator_passes_through():
    """The @essence_gate decorator should pass through on clean inputs."""
    from langgraph.types import Command

    from eng_loop.tools.essence_gate import essence_gate

    called = [False]

    @essence_gate("test-stage")
    def mock_handler(state: dict) -> Command:
        called[0] = True
        return Command(goto="next", update={"stages": state.get("stages", {})})

    state = _make_state(stage_id="test-stage")

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "summary": "All clear.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent", return_value=mock_result
    ):
        result = mock_handler(state)

    assert called[0] is True
    assert result.goto == "next"

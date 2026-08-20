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
    clarification_threshold: str = "medium",
    auto_adjust_max: int = 3,
    max_clarification_attempts: int = 3,
    clarification_attempts: int = 0,
    auto_adjust_attempts: int = 0,
    blocked_stage: str | None = None,
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
                "clarification_threshold": clarification_threshold,
                "auto_adjust_max": auto_adjust_max,
                "max_clarification_attempts": max_clarification_attempts,
                "max_questions_per_request": 5,
                "capture_decisions": True,
                "context_file": "context.md",
            },
            "agent": {"max_agent_iterations": 5},
            "max_essence_retries_per_stage": 5,
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
        "essence": {
            "checked": False,
            "blocked_stage": blocked_stage,
            "decision": None,
            "clarification_attempts": clarification_attempts,
            "auto_adjust_attempts": auto_adjust_attempts,
            "pending_questions": [],
            "resolved_findings": [],
        },
        "essence_clarifying_questions": [],
    }


# ── Classification tests ─────────────────────────────────────────
def test_skip_when_essence_checked():
    """Essence gate should skip when stage is already essence_checked."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(essence_checked=True)
    result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False
    assert result.waiting_for_input is False


def test_skip_when_disabled_config():
    """Essence gate should skip when config.essence.enabled is false."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(essence_enabled=False)
    result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False


# ── Policy classification tests ──────────────────────────────────
def test_pass_clean_inputs():
    """Essence gate should pass when agent returns clean=True."""
    from eng_loop.schemas import EssenceDecision
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
        "clarifying_questions": [],
        "summary": "All clear.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.blocked is False
    assert result.decision == EssenceDecision.PASS


def test_block_lens_4_tension():
    """Essence gate should block when Lens 4 conflicts are found."""
    from eng_loop.schemas import EssenceDecision
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
        "clarifying_questions": [],
        "summary": "Lens 4 tension found.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.blocked is True
    assert result.decision == EssenceDecision.BLOCKED
    assert "Speed vs. thoroughness conflict" in result.tension


def test_high_severity_triggers_clarification():
    """HIGH severity finding should trigger clarification (above medium threshold)."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_cake",
                "term": "cake",
                "context": "Write a cake recipe",
                "interpretations": ["vanilla", "chocolate", "carrot"],
                "severity": "high",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": [],
        "clarifying_questions": [
            {
                "id": "essence_q_001",
                "finding_id": "lens1_subject_cake",
                "lens": "lens_1",
                "finding_summary": "'cake' is ambiguous",
                "question": "What type of cake?",
                "options": ["vanilla", "chocolate", "carrot"],
                "severity": "high",
            }
        ],
        "summary": "High severity finding.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.waiting_for_input is True
    assert result.decision == EssenceDecision.CLARIFICATION_REQUIRED
    assert len(result.clarifying_questions) >= 1


def test_low_severity_auto_adjusts():
    """LOW severity finding should auto-adjust (below medium threshold)."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    # First call: low severity + adjustments
    mock_adjust = MagicMock()
    mock_adjust.error = None
    mock_adjust.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_nice",
                "term": "nice",
                "context": "Make it nice",
                "interpretations": ["aesthetically pleasing", "user-friendly"],
                "severity": "low",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Clarified 'nice' to mean user-friendly"],
        "clarifying_questions": [],
        "summary": "Low severity, adjustable.",
    }

    # Second call: clean after adjustment
    mock_clean = MagicMock()
    mock_clean.error = None
    mock_clean.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "clarifying_questions": [],
        "summary": "All clear after adjustment.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent",
        side_effect=[mock_adjust, mock_clean],
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.decision == EssenceDecision.PASS


def test_threshold_high_allows_medium():
    """When threshold=high, medium findings should not trigger clarification."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(clarification_threshold="high")

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_cache",
                "term": "cache",
                "context": "Add caching",
                "interpretations": ["in-memory", "redis", "memcached"],
                "severity": "medium",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Defaulting cache to in-memory"],
        "clarifying_questions": [],
        "summary": "Medium severity, below high threshold.",
    }

    # Should auto-adjust, then get clean
    mock_clean = MagicMock()
    mock_clean.error = None
    mock_clean.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "clarifying_questions": [],
        "summary": "All clear.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent",
        side_effect=[mock_result, mock_clean],
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.decision == EssenceDecision.PASS


def test_threshold_low_blocks_everything():
    """When threshold=low, any finding should trigger clarification."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(clarification_threshold="low")

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_clean",
                "term": "clean",
                "context": "Write clean code",
                "interpretations": ["readable", "minimal", "well-documented"],
                "severity": "low",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": [],
        "clarifying_questions": [
            {
                "id": "essence_q_001",
                "finding_id": "lens1_subject_clean",
                "lens": "lens_1",
                "finding_summary": "'clean' is subjective",
                "question": "What does 'clean' mean here?",
                "options": ["readable", "minimal", "well-documented"],
                "severity": "low",
            }
        ],
        "summary": "Low severity, but threshold is low.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.waiting_for_input is True
    assert result.decision == EssenceDecision.CLARIFICATION_REQUIRED


# ── Retry tests ───────────────────────────────────────────────────
def test_retry_lens_1_3_findings():
    """Essence gate should retry when Lens 1-3 findings need adjustments."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    # First call: returns adjustments (not clean)
    mock_adjust = MagicMock()
    mock_adjust.error = None
    mock_adjust.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_robust",
                "term": "robust",
                "context": "Make it robust",
                "interpretations": ["error recovery", "data integrity"],
                "severity": "low",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Clarified 'robust' to mean error recovery"],
        "clarifying_questions": [],
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
        "clarifying_questions": [],
        "summary": "All clear after adjustment.",
    }

    with patch(
        "eng_loop.tools.essence_gate.run_agent",
        side_effect=[mock_adjust, mock_clean],
    ):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.decision == EssenceDecision.PASS


def test_max_retries_exceeded():
    """Essence gate should proceed when max retries are exhausted."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()
    state["config"]["max_essence_retries_per_stage"] = 2

    # Always return adjustments (never clean)
    mock_adjust = MagicMock()
    mock_adjust.error = None
    mock_adjust.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_x",
                "term": "x",
                "context": "x",
                "interpretations": [],
                "severity": "low",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Adjustment applied"],
        "clarifying_questions": [],
        "summary": "Still needs work.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_adjust):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True
    assert result.updated_state["stages"]["init"]["essence_checked"] is True
    assert result.updated_state["stages"]["init"]["essence_retries_exceeded"] is True


def test_auto_adjust_max_respected():
    """Auto-adjust should respect auto_adjust_max before escalating."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state(auto_adjust_max=1)

    # Return adjustments twice — second time should escalate
    mock_adjust = MagicMock()
    mock_adjust.error = None
    mock_adjust.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_x",
                "term": "x",
                "context": "x",
                "interpretations": [],
                "severity": "low",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": ["Adjustment"],
        "clarifying_questions": [],
        "summary": "Needs adjustment.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_adjust):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    # After auto_adjust_max retries, should escalate to clarification
    assert result.waiting_for_input is True
    assert result.decision == EssenceDecision.CLARIFICATION_REQUIRED


def test_clarification_attempts_exceeded():
    """When clarification attempts exceed max for the same stage, should BLOCKED (terminal)."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    # blocked_stage must match the stage being tested so the per-stage counter
    # is not reset (new stages get their own clarification budget).
    state = _make_state(
        clarification_attempts=3,
        max_clarification_attempts=3,
        blocked_stage="init",
    )

    result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.blocked is True
    assert result.decision == EssenceDecision.BLOCKED
    assert "exhausted" in result.tension.lower() or "exceeded" in result.tension.lower()


# ── Lens 4 tests ─────────────────────────────────────────────────
def test_lens_4_no_interaction():
    """Lens 4 should block, not generate interaction."""
    from eng_loop.schemas import EssenceDecision
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
                "goal_a": "A",
                "goal_b": "B",
                "tension": "Conflict A vs B",
                "requires_user_resolution": True,
            }
        ],
        "clean": False,
        "adjustments": [],
        "clarifying_questions": [],
        "summary": "Lens 4 conflict.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.blocked is True
    assert result.waiting_for_input is False
    assert result.decision == EssenceDecision.BLOCKED


def test_lens_4_no_auto_adjust():
    """Lens 4 should never auto-adjust."""
    from eng_loop.schemas import EssenceDecision
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
                "goal_a": "Fast",
                "goal_b": "Thorough",
                "tension": "Speed vs quality",
                "requires_user_resolution": True,
            }
        ],
        "clean": False,
        "adjustments": ["Some adjustment"],  # Should be ignored
        "clarifying_questions": [],
        "summary": "Lens 4.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.blocked is True
    assert result.decision == EssenceDecision.BLOCKED


# ── Interaction tests ────────────────────────────────────────────
def test_clarification_generates_waiting_for_input():
    """Clarification should produce waiting_for_input status."""
    from eng_loop.schemas import EssenceDecision
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_cake",
                "term": "cake",
                "context": "Write a cake recipe",
                "interpretations": ["vanilla", "chocolate"],
                "severity": "high",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": [],
        "clarifying_questions": [
            {
                "id": "essence_q_001",
                "finding_id": "lens1_subject_cake",
                "lens": "lens_1",
                "finding_summary": "'cake' is ambiguous",
                "question": "What type of cake?",
                "options": ["vanilla", "chocolate"],
                "severity": "high",
            }
        ],
        "summary": "Needs clarification.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.waiting_for_input is True
    assert result.decision == EssenceDecision.CLARIFICATION_REQUIRED
    assert len(result.clarifying_questions) >= 1


def test_questions_persisted_in_result():
    """Clarifying questions should be preserved in result."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_db",
                "term": "database",
                "context": "Add a database",
                "interpretations": ["PostgreSQL", "MongoDB", "SQLite"],
                "severity": "high",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": [],
        "clarifying_questions": [
            {
                "id": "essence_q_001",
                "finding_id": "lens1_subject_db",
                "lens": "lens_1",
                "finding_summary": "'database' is ambiguous",
                "question": "Which database?",
                "options": ["PostgreSQL", "MongoDB", "SQLite"],
                "severity": "high",
            }
        ],
        "summary": "DB type unclear.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert len(result.clarifying_questions) == 1
    assert result.clarifying_questions[0]["finding_id"] == "lens1_subject_db"
    assert result.clarifying_questions[0]["id"] == "essence_q_001"


# ── Decorator tests ──────────────────────────────────────────────
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
        "clarifying_questions": [],
        "summary": "Blocked.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
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
        "clarifying_questions": [],
        "summary": "All clear.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = mock_handler(state)

    assert called[0] is True
    assert result.goto == "next"


def test_essence_gate_decorator_waiting_for_input():
    """The @essence_gate decorator should return waiting_for_input on clarification."""
    from langgraph.types import Command

    from eng_loop.tools.essence_gate import essence_gate

    @essence_gate("test-stage")
    def mock_handler(state: dict) -> Command:
        return Command(goto="next", update={"stages": state.get("stages", {})})

    state = _make_state(stage_id="test-stage")

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [
            {
                "finding_id": "lens1_subject_x",
                "term": "x",
                "context": "x",
                "interpretations": [],
                "severity": "high",
            }
        ],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": False,
        "adjustments": [],
        "clarifying_questions": [
            {
                "id": "essence_q_001",
                "finding_id": "lens1_subject_x",
                "lens": "lens_1",
                "finding_summary": "x is ambiguous",
                "question": "What is x?",
                "options": [],
                "severity": "high",
            }
        ],
        "summary": "Needs clarification.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = mock_handler(state)

    assert result.goto == "__end__"
    assert result.update["status"] == "waiting_for_input"
    assert result.update["blocking_condition"] == "essence_clarification_needed"


# ── Tools tests ──────────────────────────────────────────────────
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


# ── Schema tests ─────────────────────────────────────────────────
def test_essence_output_schema():
    """EssenceOutput schema should validate correctly with new fields."""
    from eng_loop.schemas import (
        EssenceClarifyingQuestion,
        EssenceConflict,
        EssenceHiddenAssumption,
        EssenceLiteralTrap,
        EssenceOutput,
        EssenceSubjectiveTerm,
        Severity,
    )

    output = EssenceOutput(
        lens_1_subjective_terms=[
            EssenceSubjectiveTerm(
                finding_id="lens1_subject_robust",
                term="robust",
                context="Make the API robust",
                interpretations=["network resilience", "error recovery"],
                severity=Severity.HIGH,
            )
        ],
        lens_2_hidden_assumptions=[
            EssenceHiddenAssumption(
                finding_id="lens2_assump_payment",
                assumption="Payment service is always available",
                risk="Checkout flow fails if payment is down",
                severity=Severity.HIGH,
            )
        ],
        lens_3_literal_traps=[
            EssenceLiteralTrap(
                finding_id="lens3_trap_fix_login",
                phrasing="Fix the login",
                ambiguity="Fix bug? Improve UX? Add auth method?",
                likely_misinterpretation="LLM fixes most obvious bug",
                severity=Severity.MEDIUM,
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
        clarifying_questions=[
            EssenceClarifyingQuestion(
                id="essence_q_001",
                finding_id="lens1_subject_robust",
                lens="lens_1",
                finding_summary="'robust' is subjective",
                question="What does 'robust' mean?",
                options=["network resilience", "error recovery", "data integrity"],
                severity=Severity.HIGH,
            )
        ],
        summary="Findings across all lenses.",
    )

    assert len(output.lens_1_subjective_terms) == 1
    assert len(output.lens_2_hidden_assumptions) == 1
    assert len(output.lens_3_literal_traps) == 1
    assert len(output.lens_4_conflicts) == 1
    assert len(output.clarifying_questions) == 1
    assert output.clarifying_questions[0].finding_id == "lens1_subject_robust"


def test_severity_enum():
    """Severity enum should have correct values."""
    from eng_loop.schemas import Severity

    assert Severity.LOW.value == "low"
    assert Severity.MEDIUM.value == "medium"
    assert Severity.HIGH.value == "high"


def test_essence_decision_enum():
    """EssenceDecision enum should have correct values."""
    from eng_loop.schemas import EssenceDecision

    assert EssenceDecision.PASS.value == "pass"
    assert EssenceDecision.AUTO_ADJUST.value == "auto_adjust"
    assert EssenceDecision.CLARIFICATION_REQUIRED.value == "clarification_required"
    assert EssenceDecision.BLOCKED.value == "blocked"


# ── Policy helper tests ──────────────────────────────────────────
def test_should_clarify_high_above_medium():
    """HIGH severity should trigger clarification when threshold is medium."""
    from eng_loop.tools.essence_gate import should_clarify

    assert should_clarify("high", "medium") is True


def test_should_clarify_medium_above_medium():
    """MEDIUM severity should trigger clarification when threshold is medium."""
    from eng_loop.tools.essence_gate import should_clarify

    assert should_clarify("medium", "medium") is True


def test_should_clarify_low_below_medium():
    """LOW severity should NOT trigger clarification when threshold is medium."""
    from eng_loop.tools.essence_gate import should_clarify

    assert should_clarify("low", "medium") is False


def test_should_clarify_medium_below_high():
    """MEDIUM severity should NOT trigger clarification when threshold is high."""
    from eng_loop.tools.essence_gate import should_clarify

    assert should_clarify("medium", "high") is False


def test_should_clarify_low_below_low():
    """LOW severity should trigger clarification when threshold is low."""
    from eng_loop.tools.essence_gate import should_clarify

    assert should_clarify("low", "low") is True


# ── Backward compatibility tests ─────────────────────────────────
def test_backward_compat_no_severity():
    """Findings without severity field should default to low."""
    from eng_loop.tools.essence_gate import _get_severity

    finding = {"term": "robust", "context": "Make it robust"}
    assert _get_severity(finding) == "low"


def test_backward_compat_no_clarifying_questions():
    """Output without clarifying_questions should work."""
    from eng_loop.schemas import EssenceOutput

    output = EssenceOutput(
        lens_1_subjective_terms=[],
        lens_2_hidden_assumptions=[],
        lens_3_literal_traps=[],
        lens_4_conflicts=[],
        clean=True,
        adjustments=[],
        summary="All clear.",
    )
    assert output.clarifying_questions == []


def test_backward_compat_old_state_no_essence():
    """State without essence section should work."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()
    del state["essence"]
    del state["essence_clarifying_questions"]

    # Mock agent to avoid real LLM call
    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "clarifying_questions": [],
        "summary": "All clear.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True


def test_backward_compat_old_config_no_threshold():
    """Config without clarification_threshold should default to medium."""
    from eng_loop.tools.essence_gate import run_essence_gate

    state = _make_state()
    del state["config"]["essence"]["clarification_threshold"]

    # Mock agent to return clean — avoids real LLM call
    mock_result = MagicMock()
    mock_result.error = None
    mock_result.data = {
        "lens_1_subjective_terms": [],
        "lens_2_hidden_assumptions": [],
        "lens_3_literal_traps": [],
        "lens_4_conflicts": [],
        "clean": True,
        "adjustments": [],
        "clarifying_questions": [],
        "summary": "All clear.",
    }

    with patch("eng_loop.tools.essence_gate.run_agent", return_value=mock_result):
        result = run_essence_gate("init", state, state["paths"], state["config"])

    assert result.passed is True

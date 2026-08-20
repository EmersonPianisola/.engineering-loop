from __future__ import annotations

from unittest.mock import MagicMock, patch

from eng_loop.schemas import ErrorClassification, Lesson, RecoveryPlan
from eng_loop.tools.recovery_agent import (
    _extract_json_from_text,
    _fallback_recovery_plan,
    analyze_and_propose,
    generate_lessons,
)


class TestExtractJsonFromText:
    def test_plain_json(self) -> None:
        result = _extract_json_from_text('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_markdown_code_block(self) -> None:
        text = 'Some text\n```json\n{"key": "value"}\n```'
        result = _extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_markdown_code_block_no_lang(self) -> None:
        text = '``` \n{"key": "value"}\n```'
        result = _extract_json_from_text(text)
        assert result == '{"key": "value"}'

    def test_no_json(self) -> None:
        result = _extract_json_from_text("Just plain text")
        assert result is None

    def test_json_with_surrounding_text(self) -> None:
        text = "Here is the plan: {\"key\": \"value\"} done."
        result = _extract_json_from_text(text)
        assert result == '{"key": "value"} done.'


class TestFallbackRecoveryPlan:
    def test_returns_valid_plan(self) -> None:
        classification = ErrorClassification(
            category="logic",
            severity="high",
            is_retryable=True,
            description="test error",
            suggested_strategy="rollback",
        )
        plan = _fallback_recovery_plan(classification, "test error", "impl.code", "LLM timeout")
        assert plan.error_category == "logic"
        assert plan.root_cause.startswith("LLM recovery analysis failed")
        assert len(plan.fix_actions) >= 1
        assert plan.confidence == 0.3
        assert "test error" in plan.fix_prompt_injection


class TestGenerateLessons:
    def test_marks_lessons_confirmed_on_success(self) -> None:
        state = {"blocking_condition": "error", "current_stage": "impl.code"}
        classification = ErrorClassification(
            category="logic",
            severity="high",
            is_retryable=True,
            description="test",
            suggested_strategy="rollback",
        )
        lesson = Lesson(
            lesson_id="l1",
            category="logic",
            pattern="non-convergence",
            fix_strategy="TDD",
            context="",
        )
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=[],
            lessons=[lesson],
            confidence=0.8,
        )
        result = generate_lessons(state, classification, plan, success=True)
        assert len(result) == 1
        assert result[0].confirmed is True
        assert result[0].times_applied == 1

    def test_marks_lessons_unconfirmed_on_failure(self) -> None:
        state = {"blocking_condition": "error", "current_stage": "impl.code"}
        classification = ErrorClassification(
            category="logic",
            severity="high",
            is_retryable=True,
            description="test",
            suggested_strategy="rollback",
        )
        lesson = Lesson(
            lesson_id="l1",
            category="logic",
            pattern="non-convergence",
            fix_strategy="TDD",
            context="",
        )
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=[],
            lessons=[lesson],
            confidence=0.8,
        )
        result = generate_lessons(state, classification, plan, success=False)
        assert len(result) == 1
        assert result[0].confirmed is False
        assert result[0].times_applied == 0

    def test_generates_lesson_when_none_provided_and_failed(self) -> None:
        state = {"blocking_condition": "error msg", "current_stage": "impl.code"}
        classification = ErrorClassification(
            category="schema",
            severity="medium",
            is_retryable=True,
            description="test",
            suggested_strategy="retry",
        )
        plan = RecoveryPlan(
            root_cause="root cause",
            error_category="schema",
            fix_actions=["fix1"],
            stages_to_rollback=[],
            lessons=[],
            confidence=0.5,
        )
        result = generate_lessons(state, classification, plan, success=False)
        assert len(result) == 1
        assert result[0].category == "schema"
        assert "impl.code" in result[0].pattern

    def test_no_new_lesson_when_success_and_no_lessons(self) -> None:
        state = {"blocking_condition": "error", "current_stage": "impl.code"}
        classification = ErrorClassification(
            category="logic",
            severity="high",
            is_retryable=True,
            description="test",
            suggested_strategy="rollback",
        )
        plan = RecoveryPlan(
            root_cause="cause",
            error_category="logic",
            fix_actions=["fix"],
            stages_to_rollback=[],
            lessons=[],
            confidence=0.8,
        )
        result = generate_lessons(state, classification, plan, success=True)
        assert len(result) == 0


class TestAnalyzeAndPropose:
    @patch("eng_loop.tools.recovery_agent.create_model_from_config")
    def test_returns_recovery_plan(self, mock_create_model: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(
            content='{"root_cause": "test", "error_category": "logic", "fix_actions": ["fix"], "confidence": 0.7}'
        )
        mock_create_model.return_value = mock_model

        state = {
            "blocking_condition": "test error",
            "current_stage": "impl.code",
            "stages": {"impl.code": {"output": "some output", "attempts": 2}},
            "work_item": "test work",
            "complexity": "medium",
            "work_type": "feature",
            "lessons": [],
        }
        classification = ErrorClassification(
            category="logic",
            severity="high",
            is_retryable=True,
            description="test",
            suggested_strategy="rollback",
        )
        config = {"model": {"base_url": "http://localhost:8000", "model": "test"}}

        plan = analyze_and_propose(state, classification, config)
        assert isinstance(plan, RecoveryPlan)
        assert plan.root_cause == "test"
        assert plan.error_category == "logic"

    @patch("eng_loop.tools.recovery_agent.create_model_from_config")
    def test_fallback_on_llm_error(self, mock_create_model: MagicMock) -> None:
        mock_create_model.side_effect = Exception("Model unavailable")

        state = {
            "blocking_condition": "test error",
            "current_stage": "impl.code",
            "stages": {},
            "work_item": "",
            "complexity": "small",
            "work_type": "feature",
            "lessons": [],
        }
        classification = ErrorClassification(
            category="infrastructure",
            severity="high",
            is_retryable=False,
            description="test",
            suggested_strategy="abort",
        )
        config = {"model": {"base_url": "http://localhost:8000", "model": "test"}}

        plan = analyze_and_propose(state, classification, config)
        assert isinstance(plan, RecoveryPlan)
        assert "Model unavailable" in plan.root_cause

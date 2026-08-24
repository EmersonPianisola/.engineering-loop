"""F1.4 — Recovery agent parse fix (C3).

The fallback parse (_parse_structured) previously passed locals() to
_process_section — a frame snapshot that is never written back — so no
field was ever populated and imperfect LLM output silently degraded to
identical-retry defaults. These tests pin the explicit-dict behavior and
the warning log when LLM output is unparseable.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from eng_loop.schemas import ErrorClassification, RecoveryPlan
from eng_loop.tools.recovery_agent import _parse_recovery_plan, _parse_structured, analyze_and_propose

CLASSIFICATION = ErrorClassification(
    category="logic",
    severity="high",
    is_retryable=True,
    description="test error",
    suggested_strategy="rollback",
)

STATE = {
    "blocking_condition": "test error",
    "current_stage": "impl.code",
    "stages": {},
    "work_item": "test",
    "complexity": "small",
    "work_type": "feature",
    "lessons": [],
}

CONFIG = {"model": {"base_url": "http://localhost:8000", "model": "test"}}


class TestParseStructured:
    def test_text_sections_populate_all_fields(self) -> None:
        content = (
            "root_cause: The build cache was stale\n"
            "fix_actions:\n"
            "- Clear the cache\n"
            "- Re-run the build\n"
            "stages_to_rollback:\n"
            "- impl.code\n"
            "confidence: 0.8\n"
            "lessons:\n"
            "- Invalidate the build cache after dependency changes\n"
            "fix_prompt_injection: Check the build cache before debugging\n"
        )
        plan = _parse_structured(content, CLASSIFICATION)
        assert plan.root_cause == "The build cache was stale"
        assert plan.fix_actions == ["Clear the cache", "Re-run the build"]
        assert plan.stages_to_rollback == ["impl.code"]
        assert plan.confidence == 0.8
        assert len(plan.lessons) == 1
        assert plan.lessons[0].pattern == "Invalidate the build cache after dependency changes"
        assert plan.fix_prompt_injection == "Check the build cache before debugging"
        assert plan.error_category == "logic"

    def test_defaults_when_no_sections(self) -> None:
        plan = _parse_structured("I could not analyze the failure.", CLASSIFICATION)
        assert plan.root_cause == "Unclassified logic error"
        assert plan.fix_actions == ["Retry with adjusted approach for logic"]
        assert plan.stages_to_rollback == []
        assert plan.lessons == []
        assert plan.confidence == 0.5
        assert plan.fix_prompt_injection == ""

    def test_invalid_confidence_keeps_default(self) -> None:
        plan = _parse_structured("root_cause: cache stale\nconfidence: high\n", CLASSIFICATION)
        assert plan.root_cause == "cache stale"
        assert plan.confidence == 0.5


class TestParseRecoveryPlan:
    def test_clean_json(self) -> None:
        content = '{"root_cause": "rc", "error_category": "schema", "fix_actions": ["a"], "confidence": 0.9}'
        plan = _parse_recovery_plan(content, CLASSIFICATION)
        assert plan.root_cause == "rc"
        assert plan.error_category == "schema"
        assert plan.fix_actions == ["a"]
        assert plan.confidence == 0.9

    def test_clean_json_in_code_block(self) -> None:
        content = 'Plan:\n```json\n{"root_cause": "rc", "error_category": "logic", "fix_actions": ["a"]}\n```'
        plan = _parse_recovery_plan(content, CLASSIFICATION)
        assert plan.root_cause == "rc"
        assert plan.error_category == "logic"

    def test_json_schema_error_falls_back_to_structured(self) -> None:
        content = '{"root_cause": "rc", "confidence": "not-a-number"}'
        plan = _parse_recovery_plan(content, CLASSIFICATION)
        assert plan.error_category == "logic"
        assert plan.root_cause == "Unclassified logic error"


class TestAnalyzeAndProposeLogging:
    def test_garbage_json_logs_warning_and_falls_back(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            patch("eng_loop.tools.recovery_agent.create_model_from_config") as mock_create,
            caplog.at_level(logging.WARNING, logger="eng_loop.tools.recovery_agent"),
        ):
            mock_model = MagicMock()
            mock_model.invoke.return_value = MagicMock(content='{"root_cause": broken')
            mock_create.return_value = mock_model

            plan = analyze_and_propose(STATE, CLASSIFICATION, CONFIG)

        assert isinstance(plan, RecoveryPlan)
        assert plan.root_cause.startswith("LLM recovery analysis failed")
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("analysis failed" in r.getMessage() for r in warnings)

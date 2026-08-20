#!/usr/bin/env python3
"""Integration test for the auto-recovery mechanism.

Simulates pipeline failures at various stages and verifies that the
recovery loop correctly classifies errors, proposes fixes, and retries.

Usage:
    # Run all recovery scenarios
    python scripts/test_recovery_integration.py --scenario ALL

    # Run specific scenario
    python scripts/test_recovery_integration.py --scenario LOGIC_NON_CONVERGENCE
    python scripts/test_recovery_integration.py --schema TRANSIENT_TIMEOUT
    python scripts/test_recovery_integration.py --scenario SCHEMA_JSON_ERROR
    python scripts/test_recovery_integration.py --scenario CONTRACT_VIOLATION
    python scripts/test_recovery_integration.py --scenario CONTEXT_OVERFLOW
    python scripts/test_recovery_integration.py --scenario EXHAUST_ATTEMPTS

    # Run with actual LLM (requires model running)
    python scripts/test_recovery_integration.py --scenario ALL --use-llm

    # Dry run (mock LLM, default)
    python scripts/test_recovery_integration.py --scenario ALL --mock-llm
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure eng_loop package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "eng_loop" / "src"
sys.path.insert(0, str(SRC_DIR))

from eng_loop.schemas import ErrorClassification, Lesson, RecoveryPlan, RecoveryEntry
from eng_loop.tools.error_classifier import classify_error
from eng_loop.tools.fix_applier import apply_recovery_plan, reset_stage_for_retry
from eng_loop.tools.recovery_logger import RecoveryLogger
from eng_loop.state import make_initial_state


# ──────────────────────────────────────────────────────────────────────
# Assertion Helpers
# ──────────────────────────────────────────────────────────────────────

class AssertionFailure(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def assert_true(condition: bool, msg: str):
    if not condition:
        raise AssertionFailure(f"FAIL: {msg}")
    print(f"  [PASS] {msg}")


def assert_equals(actual, expected, msg: str):
    if actual != expected:
        raise AssertionFailure(f"FAIL: {msg}\n    expected={expected!r}\n    actual={actual!r}")
    print(f"  [PASS] {msg}")


def assert_in(needle, haystack, msg: str):
    if needle not in haystack:
        raise AssertionFailure(f"FAIL: {msg}\n    {needle!r} not in {haystack!r}")
    print(f"  [PASS] {msg}")


def assert_greater_equal(actual, expected, msg: str):
    if actual < expected:
        raise AssertionFailure(f"FAIL: {msg}\n    expected >= {expected!r}\n    actual={actual!r}")
    print(f"  [PASS] {msg}")


def assert_non_empty(value, msg: str):
    if not value:
        raise AssertionFailure(f"FAIL: {msg}")
    print(f"  [PASS] {msg}")


# ──────────────────────────────────────────────────────────────────────
# Test 1: Error Classification Accuracy
# ──────────────────────────────────────────────────────────────────────

def test_error_classification():
    """Verify error classifier correctly identifies all categories."""
    print(f"\n{'=' * 70}")
    print("TEST: Error Classification Accuracy")
    print(f"{'=' * 70}")

    test_cases = [
        # (error_message, expected_category, description)
        ("Connection timed out after 30s", "transient", "timeout detection"),
        ("429 Too Many Requests", "transient", "rate limit detection"),
        ("OpenAI API error: 503 Service Unavailable", "infrastructure", "LLM error detection"),
        ("No space left on device: disk full", "infrastructure", "disk full detection"),
        ("JSON parse error: unexpected token", "schema", "JSON error detection"),
        ("Pydantic validation error: field required", "schema", "Pydantic error detection"),
        ("Contract violation: type mismatch", "contract", "contract violation detection"),
        ("impl.code non-convergence after 3 attempts", "logic", "non-convergence detection"),
        ("Agent stalled: no progress after 10 iterations", "logic", "stall detection"),
        ("Test failure: assertion error in test_login", "logic", "test failure detection"),
        ("Context window exceeded: token limit reached", "context_overflow", "context overflow detection"),
    ]

    state = {"current_stage": "impl.code", "stages": {}}
    passed = 0
    failed = 0

    for error_msg, expected_cat, desc in test_cases:
        try:
            result = classify_error(error_msg, state)
            assert_equals(result.category, expected_cat, desc)
            passed += 1
        except AssertionFailure as e:
            failed += 1
            print(f"  [FAIL] {desc}: {e.message}")

    print(f"\n  Classification: {passed}/{passed + failed} correct")
    return failed == 0


# ──────────────────────────────────────────────────────────────────────
# Test 2: Recovery Logger — JSONL Persistence
# ──────────────────────────────────────────────────────────────────────

def test_recovery_logger():
    """Verify recovery logger correctly persists and retrieves entries."""
    print(f"\n{'=' * 70}")
    print("TEST: Recovery Logger (JSONL)")
    print(f"{'=' * 70}")

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "recovery.jsonl"
        logger = RecoveryLogger(str(log_path))

        # Log multiple entries
        entries_to_log = []
        for i in range(1, 4):
            entry = RecoveryEntry(
                timestamp=time.time(),
                attempt_number=i,
                stage_id="impl.code",
                error_message=f"Error attempt {i}",
                error_category="logic",
                root_cause=f"Root cause {i}",
                fix_actions=[f"Fix {i}"],
                lessons_generated=[],
                outcome="failed" if i < 3 else "success",
                confidence=0.5 + i * 0.1,
                duration_ms=100.0 * i,
            )
            logger.log_attempt(entry)
            entries_to_log.append(entry)

        # Verify entries were persisted
        assert_true(log_path.exists(), "Log file exists")

        history = logger.get_history()
        assert_equals(len(history), 3, "3 entries in history")

        # Verify last entry
        last = history[-1]
        assert_equals(last.outcome, "success", "Last entry outcome is success")
        assert_equals(last.attempt_number, 3, "Last entry attempt number is 3")

        # Verify summary
        summary = logger.get_summary()
        assert_equals(summary["total_attempts"], 3, "Summary total attempts = 3")
        assert_equals(summary["successful"], 1, "Summary successful = 1")
        assert_equals(summary["failed"], 2, "Summary failed = 2")
        assert_equals(summary["categories"]["logic"], 3, "Summary logic category = 3")

    print(f"\n  -> Logger: ALL CHECKS PASSED")
    return True


# ──────────────────────────────────────────────────────────────────────
# Test 3: Fix Applier — Selective Rollback
# ──────────────────────────────────────────────────────────────────────

def test_fix_applier():
    """Verify fix applier correctly applies recovery plans."""
    print(f"\n{'=' * 70}")
    print("TEST: Fix Applier (Selective Rollback)")
    print(f"{'=' * 70}")

    state = make_initial_state({}, {})
    state["current_stage"] = "impl.code"
    state["status"] = "blocked"
    state["blocking_condition"] = "impl.code non-convergence after 3 attempts"
    state["stages"]["impl.design"]["done"] = True
    state["stages"]["impl.design"]["attempts"] = 1
    state["stages"]["impl.code"]["done"] = False
    state["stages"]["impl.code"]["attempts"] = 3
    state["stages"]["verify"]["done"] = False
    state["stages"]["verify"]["attempts"] = 0
    state["fix_tasks"] = [
        {"source": "verify", "gap": "old gap", "evidence": "e1", "severity": "critical"},
        {"source": "impl.code", "gap": "code gap", "evidence": "e2", "severity": "critical"},
    ]

    plan = RecoveryPlan(
        root_cause="Agent kept generating same code without progress",
        error_category="logic",
        fix_actions=["Reset impl.code and re-implement with TDD approach", "Add stricter type annotations"],
        stages_to_rollback=["impl.code"],
        lessons=[
            Lesson(
                lesson_id="l1",
                category="logic",
                pattern="non-convergence in impl.code",
                fix_strategy="Use TDD approach",
                context="Agent stalled on same code",
            )
        ],
        confidence=0.7,
        fix_prompt_injection="Previous attempt failed with non-convergence. Use TDD: write test first, then implement.",
    )

    result = apply_recovery_plan(state, plan)

    # Verify blocking condition cleared
    assert_equals(result["blocking_condition"], "", "Blocking condition cleared")
    assert_equals(result["status"], "running", "Status reset to running")

    # Verify selective rollback
    assert_equals(result["stages"]["impl.code"]["done"], False, "impl.code reset")
    assert_equals(result["stages"]["impl.code"]["attempts"], 0, "impl.code attempts reset")
    assert_equals(result["stages"]["impl.design"]["done"], True, "impl.design preserved")

    # Verify lessons injected
    assert_greater_equal(len(result["lessons"]), 1, "Lessons injected into state")

    # Verify fix guidance injected
    assert_greater_equal(len(result["fix_tasks"]), 1, "Fix task from recovery agent added")
    sources = [ft["source"] for ft in result["fix_tasks"]]
    assert_in("recovery-agent", sources, "Fix task source is recovery-agent")

    # Verify fix prompt in handoffs
    assert_true("recovery_fix_prompt" in result.get("handoffs", {}), "Fix prompt in handoffs")

    # Verify old fix_tasks from rolled-back stage filtered
    sources = [ft["source"] for ft in result["fix_tasks"]]
    assert_true("impl.code" not in sources, "Old fix_tasks from impl.code filtered")

    print(f"\n  -> Fix Applier: ALL CHECKS PASSED")
    return True


# ──────────────────────────────────────────────────────────────────────
# Test 4: Recovery Plan — LLM Mock
# ──────────────────────────────────────────────────────────────────────

def test_recovery_plan_generation():
    """Verify recovery plan is generated correctly from LLM mock."""
    print(f"\n{'=' * 70}")
    print("TEST: Recovery Plan Generation (Mock LLM)")
    print(f"{'=' * 70}")

    from eng_loop.tools.recovery_agent import analyze_and_propose

    state = {
        "blocking_condition": "impl.code non-convergence after 3 attempts",
        "current_stage": "impl.code",
        "stages": {
            "impl.code": {
                "output": "Agent generated same code 3 times without progress",
                "attempts": 3,
            }
        },
        "work_item": "Implement OAuth2 authentication",
        "complexity": "medium",
        "work_type": "feature",
        "lessons": [],
    }

    classification = ErrorClassification(
        category="logic",
        severity="high",
        is_retryable=True,
        description="Agent non-convergence or stall — needs different approach",
        suggested_strategy="rollback",
    )

    config = {"model": {"base_url": "http://localhost:8000", "model": "test"}}

    # Mock LLM response
    mock_model = MagicMock()
    mock_model.invoke.return_value = MagicMock(
        content=json.dumps({
            "root_cause": "Agent kept generating identical code without making progress",
            "error_category": "logic",
            "fix_actions": [
                "Reset impl.code and re-implement with strict TDD approach",
                "Add type annotations to force different code generation",
            ],
            "stages_to_rollback": ["impl.code"],
            "lessons": [
                {
                    "lesson_id": "lesson_001",
                    "category": "logic",
                    "pattern": "non-convergence in impl.code",
                    "fix_strategy": "Use TDD approach with stricter types",
                    "context": "Agent stalled generating same code",
                }
            ],
            "confidence": 0.8,
            "fix_prompt_injection": "Previous 3 attempts failed with non-convergence. Write tests first, then implement.",
        })
    )

    with patch("eng_loop.tools.recovery_agent.create_model_from_config", return_value=mock_model):
        plan = analyze_and_propose(state, classification, config)

    assert_true(isinstance(plan, RecoveryPlan), "Result is RecoveryPlan")
    assert_equals(plan.error_category, "logic", "Error category is logic")
    assert_greater_equal(len(plan.fix_actions), 2, "At least 2 fix actions")
    assert_equals(plan.confidence, 0.8, "Confidence is 0.8")
    assert_equals(len(plan.lessons), 1, "1 lesson generated")
    assert_non_empty(plan.fix_prompt_injection, "Fix prompt injection present")

    print(f"\n  -> Recovery Plan: ALL CHECKS PASSED")
    return True


# ──────────────────────────────────────────────────────────────────────
# Test 5: Full Recovery Loop Simulation
# ──────────────────────────────────────────────────────────────────────

def test_full_recovery_loop():
    """Simulate a full recovery loop: fail → classify → plan → apply → succeed."""
    print(f"\n{'=' * 70}")
    print("TEST: Full Recovery Loop Simulation")
    print(f"{'=' * 70}")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_root = Path(tmp) / "artifacts"
        artifact_root.mkdir()

        # Phase 1: Initial failure
        print("\n  Phase 1: Initial failure")
        state = make_initial_state({}, {})
        state["current_stage"] = "impl.code"
        state["status"] = "blocked"
        state["blocking_condition"] = "impl.code non-convergence after 3 attempts"
        state["stages"]["impl.code"]["done"] = False
        state["stages"]["impl.code"]["attempts"] = 3

        # Classify error
        classification = classify_error(state["blocking_condition"], state)
        assert_equals(classification.category, "logic", "Error classified as logic")
        assert_equals(classification.suggested_strategy, "rollback", "Strategy is rollback")

        # Phase 2: LLM analysis (mocked)
        print("\n  Phase 2: LLM analysis (mocked)")
        from eng_loop.tools.recovery_agent import analyze_and_propose

        config = {"model": {"base_url": "http://localhost:8000", "model": "test"}}
        mock_model = MagicMock()
        mock_model.invoke.return_value = MagicMock(
            content=json.dumps({
                "root_cause": "Agent generated same code without progress",
                "error_category": "logic",
                "fix_actions": ["Re-implement with TDD", "Add type annotations"],
                "stages_to_rollback": ["impl.code"],
                "lessons": [
                    {
                        "lesson_id": "l1",
                        "category": "logic",
                        "pattern": "non-convergence in impl.code",
                        "fix_strategy": "TDD with types",
                        "context": "Agent stalled",
                    }
                ],
                "confidence": 0.8,
                "fix_prompt_injection": "Use TDD approach",
            })
        )

        with patch("eng_loop.tools.recovery_agent.create_model_from_config", return_value=mock_model):
            plan = analyze_and_propose(state, classification, config)

        assert_true(isinstance(plan, RecoveryPlan), "Recovery plan generated")
        assert_greater_equal(plan.confidence, 0.5, "Confidence above threshold")

        # Phase 3: Apply fix
        print("\n  Phase 3: Apply fix plan")
        fixed_state = apply_recovery_plan(state, plan)
        assert_equals(fixed_state["blocking_condition"], "", "Blocking condition cleared")
        assert_equals(fixed_state["status"], "running", "Status reset to running")
        assert_equals(fixed_state["stages"]["impl.code"]["attempts"], 0, "impl.code reset")

        # Phase 4: Simulate successful retry
        print("\n  Phase 4: Simulate successful retry")
        fixed_state["status"] = "done"
        fixed_state["stages"]["impl.code"]["done"] = True
        fixed_state["stages"]["impl.code"]["attempts"] = 1

        # Phase 5: Log recovery
        print("\n  Phase 5: Log recovery attempt")
        logger = RecoveryLogger(str(artifact_root / "recovery.jsonl"))

        entry = RecoveryEntry(
            timestamp=time.time(),
            attempt_number=1,
            stage_id="impl.code",
            error_message=state["blocking_condition"],
            error_category=classification.category,
            root_cause=plan.root_cause,
            fix_actions=plan.fix_actions,
            lessons_generated=plan.lessons,
            outcome="success",
            confidence=plan.confidence,
            duration_ms=500.0,
        )
        logger.log_attempt(entry)

        # Persist lessons
        logger.log_lessons(plan.lessons, str(artifact_root))

        # Verify log
        history = logger.get_history()
        assert_equals(len(history), 1, "1 recovery entry logged")
        assert_equals(history[0].outcome, "success", "Outcome is success")

        # Verify lessons persisted
        lessons_path = artifact_root / "lessons.json"
        assert_true(lessons_path.exists(), "Lessons file created")

        with open(lessons_path) as f:
            lessons_data = json.load(f)
        assert_true(len(lessons_data) > 0, "Lessons data contains entries")

        # Verify summary
        summary = logger.get_summary()
        assert_equals(summary["successful"], 1, "1 successful recovery")

    print(f"\n  -> Full Recovery Loop: ALL CHECKS PASSED")
    return True


# ──────────────────────────────────────────────────────────────────────
# Test 6: Exhausted Attempts
# ──────────────────────────────────────────────────────────────────────

def test_exhausted_attempts():
    """Verify behavior when recovery attempts are exhausted."""
    print(f"\n{'=' * 70}")
    print("TEST: Exhausted Recovery Attempts")
    print(f"{'=' * 70}")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_root = Path(tmp) / "artifacts"
        artifact_root.mkdir()
        logger = RecoveryLogger(str(artifact_root / "recovery.jsonl"))

        max_attempts = 3
        state = make_initial_state({}, {})
        state["current_stage"] = "impl.code"
        state["status"] = "blocked"
        state["blocking_condition"] = "impl.code non-convergence"

        classification = classify_error(state["blocking_condition"], state)

        # Simulate 3 failed attempts
        for attempt in range(1, max_attempts + 1):
            entry = RecoveryEntry(
                timestamp=time.time(),
                attempt_number=attempt,
                stage_id="impl.code",
                error_message=state["blocking_condition"],
                error_category=classification.category,
                root_cause=f"Root cause attempt {attempt}",
                fix_actions=[f"Fix attempt {attempt}"],
                lessons_generated=[],
                outcome="failed",
                confidence=0.5,
                duration_ms=200.0,
            )
            logger.log_attempt(entry)

        # Log exhaustion
        exhausted_entry = RecoveryEntry(
            timestamp=time.time(),
            attempt_number=max_attempts,
            stage_id="impl.code",
            error_message=state["blocking_condition"],
            error_category=classification.category,
            root_cause=f"Recovery exhausted after {max_attempts} attempts",
            fix_actions=[],
            lessons_generated=[],
            outcome="exhausted",
            confidence=0.0,
            duration_ms=0.0,
        )
        logger.log_attempt(exhausted_entry)

        # Verify summary
        summary = logger.get_summary()
        assert_equals(summary["total_attempts"], 4, f"4 total entries (3 failed + 1 exhausted)")
        assert_equals(summary["failed"], 3, "3 failed attempts")
        assert_equals(summary["exhausted"], 1, "1 exhausted entry")
        assert_equals(summary["successful"], 0, "0 successful recoveries")

    print(f"\n  -> Exhausted Attempts: ALL CHECKS PASSED")
    return True


# ──────────────────────────────────────────────────────────────────────
# Test 7: Lessons Integration
# ──────────────────────────────────────────────────────────────────────

def test_lessons_integration():
    """Verify lessons flow from recovery → logger → lessons.json."""
    print(f"\n{'=' * 70}")
    print("TEST: Lessons Integration")
    print(f"{'=' * 70}")

    with tempfile.TemporaryDirectory() as tmp:
        artifact_root = Path(tmp) / "artifacts"
        artifact_root.mkdir()
        logger = RecoveryLogger(str(artifact_root / "recovery.jsonl"))

        lessons = [
            Lesson(
                lesson_id="l1",
                category="logic",
                pattern="non-convergence in impl.code with OAuth2",
                fix_strategy="Use TDD with strict type annotations",
                context="Agent kept generating same code pattern",
                confirmed=True,
            ),
            Lesson(
                lesson_id="l2",
                category="schema",
                pattern="Pydantic validation error on RecoveryPlan",
                fix_strategy="Ensure JSON response matches schema exactly",
                context="LLM returned extra fields",
                confirmed=False,
            ),
        ]

        logger.log_lessons(lessons, str(artifact_root))

        # Verify lessons.json
        lessons_path = artifact_root / "lessons.json"
        assert_true(lessons_path.exists(), "lessons.json created")

        with open(lessons_path) as f:
            data = json.load(f)

        assert_true(len(data) >= 2, f"At least 2 lesson entries (got {len(data)})")

        # Verify lesson structure
        for lesson_data in data.values():
            if isinstance(lesson_data, dict):
                assert_true("id" in lesson_data, "Lesson has 'id' field")
                assert_true("fix" in lesson_data, "Lesson has 'fix' field")
                assert_true("category" in lesson_data, "Lesson has 'category' field")

    print(f"\n  -> Lessons Integration: ALL CHECKS PASSED")
    return True


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

SCENARIOS = {
    "CLASSIFICATION": {
        "description": "Error classifier accuracy across all categories",
        "test_fn": test_error_classification,
    },
    "LOGGER": {
        "description": "Recovery logger JSONL persistence and retrieval",
        "test_fn": test_recovery_logger,
    },
    "FIX_APPLIER": {
        "description": "Selective rollback, lesson injection, fix guidance",
        "test_fn": test_fix_applier,
    },
    "PLAN_GENERATION": {
        "description": "LLM recovery plan generation (mocked)",
        "test_fn": test_recovery_plan_generation,
    },
    "FULL_LOOP": {
        "description": "Complete recovery loop: fail → classify → plan → apply → succeed",
        "test_fn": test_full_recovery_loop,
    },
    "EXHAUSTED": {
        "description": "Behavior when recovery attempts are exhausted",
        "test_fn": test_exhausted_attempts,
    },
    "LESSONS": {
        "description": "Lessons flow from recovery to persistence",
        "test_fn": test_lessons_integration,
    },
}


def main():
    parser = argparse.ArgumentParser(
        description="Integration test for auto-recovery mechanism",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  CLASSIFICATION    Error classifier accuracy
  LOGGER            JSONL persistence
  FIX_APPLIER       Selective rollback + lesson injection
  PLAN_GENERATION   LLM recovery plan (mocked)
  FULL_LOOP         Complete recovery loop simulation
  EXHAUSTED         Exhausted attempts behavior
  LESSONS           Lessons persistence flow
  ALL               Run all scenarios
        """,
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()) + ["ALL"],
        default="ALL",
        help="Scenario to run (default: ALL)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("AUTO-RECOVERY INTEGRATION TEST")
    print(f"Scenario: {args.scenario}")
    print("=" * 70)

    if args.scenario == "ALL":
        scenarios_to_run = SCENARIOS.values()
    else:
        scenarios_to_run = [SCENARIOS[args.scenario]]

    passed = 0
    failed = 0
    failures = []

    for scenario in scenarios_to_run:
        try:
            result = scenario["test_fn"]()
            if result:
                passed += 1
            else:
                failed += 1
                failures.append((scenario["description"], "Assertions failed"))
        except AssertionFailure as e:
            failed += 1
            failures.append((scenario["description"], e.message))
        except Exception as e:
            failed += 1
            failures.append((scenario["description"], str(e)))
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} scenarios")
    print(f"{'=' * 70}")

    if failures:
        print("\nFailed scenarios:")
        for name, error in failures:
            print(f"  {name}: {error[:120]}")
        sys.exit(1)
    else:
        print("\n  All scenarios passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

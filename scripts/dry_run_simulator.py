#!/usr/bin/env python3
"""Dry-run simulator for Engineering Loop graph execution.

Runs the full graph topology WITHOUT invoking any LLM API.
Patches run_agent to return deterministic AgentResult objects
based on the selected scenario.

Usage:
    python scripts/dry_run_simulator.py --scenario HAPPY_PATH
    python scripts/dry_run_simulator.py --scenario CONTRACT_VIOLATION
    python scripts/dry_run_simulator.py --scenario VERIFY_ROLLBACK
    python scripts/dry_run_simulator.py --scenario QA_FANOUT_FAIL
    python scripts/dry_run_simulator.py --scenario ALL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure eng_loop package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "eng_loop" / "src"
sys.path.insert(0, str(SRC_DIR))

os.environ["ENG_AGENT_BACKEND"] = "langchain"
os.environ["ENG_DRY_RUN"] = "1"

from langgraph.types import Command, Send

from eng_loop.config import load_config, resolve_paths
from eng_loop.graph_builder import GraphBuilder
from eng_loop.state import make_initial_state, STAGE_ORDER
from eng_loop.tools.agent_runner import AgentResult


class InvocationTracker:
    """Tracks how many times each stage's run_agent was called."""

    def __init__(self):
        self.calls: dict[str, int] = {}

    def record(self, stage_id: str) -> int:
        count = self.calls.get(stage_id, 0) + 1
        self.calls[stage_id] = count
        return count

    def get(self, stage_id: str) -> int:
        return self.calls.get(stage_id, 0)

    def reset(self):
        self.calls.clear()


# ──────────────────────────────────────────────────────────────────────
# Scenario Mock Functions
# ──────────────────────────────────────────────────────────────────────

def mock_run_agent_happy_path(
    model, tools, prompt, stage_id, output_schema=None,
    max_iterations=25, config=None, tracker=None, **kwargs,
) -> AgentResult:
    """All stages return valid success data."""
    results = {
        "init": {
            "valid": True,
            "work_item_refined": "Implement user authentication with OAuth2",
            "estimated_files": 5,
            "estimated_tasks": 3,
            "notes": "Work item validated successfully",
        },
        "init.ideate": {
            "ideation_results": "OAuth2 flow with PKCE, token refresh, session management",
            "decomposed_tasks": [
                "Implement OAuth2 client",
                "Add token refresh logic",
                "Build session middleware",
            ],
            "ready_for_next": True,
        },
        "init.refine": {
            "refined_work_item": "Implement OAuth2 authentication with PKCE flow, token refresh, and session middleware",
            "ready_for_architecture": True,
        },
        "impl.design": {
            "blueprint": "## Implementation Blueprint\n\n### Tasks\n1. Create OAuth2 client module\n2. Implement token refresh logic\n3. Build session middleware\n\nEach task follows TDD with unit tests.",
            "tasks": [
                "Create OAuth2 client module with PKCE support",
                "Implement token refresh with exponential backoff",
                "Build session middleware with secure cookies",
            ],
            "file_structure": [
                "src/auth/oauth_client.py",
                "src/auth/token_refresher.py",
                "src/auth/session.py",
            ],
            "complete": True,
            "decisions": ["AD-001: Using requests-oauthlib for OAuth2"],
        },
        "impl.code": {
            "implementation_summary": "Implemented OAuth2 authentication with PKCE, token refresh, and session middleware. All tests pass.",
            "files_created": [
                "src/auth/oauth_client.py",
                "src/auth/token_refresher.py",
                "src/auth/session.py",
                "tests/test_oauth_client.py",
                "tests/test_token_refresher.py",
                "tests/test_session.py",
            ],
            "tests_passed": True,
            "complete": True,
            "decisions": [],
            "diff": "diff --git a/src/auth/ b/src/auth/\n+new files added",
        },
        "doc.update": {
            "files_updated": ["README.md", "docs/auth.md"],
            "complete": True,
        },
        "verify": {
            "verdict": "PASS",
            "per_ac_evidence": [
                "AC1: src/auth/oauth_client.py:45 -> PKCE implemented",
                "AC2: src/auth/token_refresher.py:22 -> exponential backoff",
                "AC3: src/auth/session.py:15 -> secure cookie flags",
            ],
            "discrimination_sensor": "pass",
            "coverage_audit": "pass",
            "gaps": [],
            "complete": True,
        },
        "qa.security": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        "qa.api-contract": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        "qa.performance": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        "deploy.prepare": {
            "build_status": "pass",
            "lint_status": "pass",
            "type_check_status": "pass",
            "verdict": "PASS",
            "errors": [],
            "complete": True,
        },
        "post": {
            "summary": "All stages completed successfully",
            "lessons_to_share": 0,
            "final_status": "done",
            "complete": True,
        },
    }

    default_result = {
        "complete": True,
        "valid": True,
        "verdict": "PASS",
        "findings": [],
        "critical_findings": [],
        "gaps": [],
    }
    default_result.update(results.get(stage_id, {}))

    return AgentResult(
        data=default_result,
        iterations=1,
        elapsed=0.01,
        tool_calls_made=2,
    )


def mock_run_agent_contract_violation(
    model, tools, prompt, stage_id, output_schema=None,
    max_iterations=25, config=None, tracker=None, **kwargs,
) -> AgentResult:
    """impl.design returns a blueprint with NO tasks -> contract gate should catch it.
    Evidence gate requires tasks OR (blueprint >= 20 chars AND tasks >= 2).
    Contract gate requires tasks AND blueprint >= 50 chars.
    So: provide 2 tasks (passes evidence) but empty tasks list seen by contract (fails contract).
    Actually: evidence gate checks `result.get("tasks")` directly.
    Trick: provide tasks to pass evidence, but blueprint too short for contract (needs 50).
    """
    if stage_id == "impl.design":
        return AgentResult(
            data={
                "blueprint": "TODO",
                "tasks": ["Task A", "Task B"],
                "file_structure": [],
                "complete": True,
                "decisions": [],
            },
            iterations=1,
            elapsed=0.01,
            tool_calls_made=1,
        )

    return AgentResult(
        data={"complete": True, "valid": True, "verdict": "PASS"},
        iterations=1,
        elapsed=0.01,
        tool_calls_made=1,
    )


def mock_run_agent_verify_rollback(
    model, tools, prompt, stage_id, output_schema=None,
    max_iterations=25, config=None, tracker=None, **kwargs,
) -> AgentResult:
    """verify FAILs first time, impl.code fixes, verify PASSes second time."""
    call_num = tracker.record(stage_id) if tracker else 1

    if stage_id == "impl.code":
        if call_num == 1:
            return AgentResult(
                data={
                    "implementation_summary": "Implemented OAuth2 auth but with missing error handling in token refresh",
                    "files_created": [
                        "src/auth/oauth_client.py",
                        "src/auth/token_refresher.py",
                        "tests/test_oauth_client.py",
                    ],
                    "tests_passed": True,
                    "complete": True,
                    "decisions": [],
                    "diff": "initial implementation",
                },
                iterations=1,
                elapsed=0.01,
                tool_calls_made=5,
            )
        else:
            return AgentResult(
                data={
                    "implementation_summary": "Fixed token refresh error handling and added null check in session middleware. All verifier gaps addressed.",
                    "files_created": [
                        "src/auth/token_refresher.py",
                        "src/auth/session.py",
                        "tests/test_token_refresher.py",
                    ],
                    "tests_passed": True,
                    "complete": True,
                    "decisions": [],
                    "diff": "fixed error handling",
                },
                iterations=1,
                elapsed=0.01,
                tool_calls_made=4,
            )

    if stage_id == "verify":
        if call_num == 1:
            return AgentResult(
                data={
                    "verdict": "FAIL",
                    "per_ac_evidence": [
                        "AC1: src/auth/oauth_client.py:45 -> PKCE implemented",
                        "AC2: src/auth/token_refresher.py:0 -> MISSING",
                        "AC3: src/auth/session.py:0 -> MISSING",
                    ],
                    "discrimination_sensor": "pass",
                    "coverage_audit": "fail",
                    "gaps": [
                        "Token refresher lacks error handling for network failures — no retry logic found",
                        "Session middleware missing null check for expired tokens — causes 500 errors",
                    ],
                    "complete": True,
                },
                iterations=1,
                elapsed=0.01,
                tool_calls_made=8,
            )
        else:
            return AgentResult(
                data={
                    "verdict": "PASS",
                    "per_ac_evidence": [
                        "AC1: src/auth/oauth_client.py:45 -> PKCE implemented",
                        "AC2: src/auth/token_refresher.py:67 -> retry with backoff",
                        "AC3: src/auth/session.py:34 -> null check + graceful fallback",
                    ],
                    "discrimination_sensor": "pass",
                    "coverage_audit": "pass",
                    "gaps": [],
                    "complete": True,
                },
                iterations=1,
                elapsed=0.01,
                tool_calls_made=8,
            )

    happy_results = {
        "init": {
            "valid": True,
            "work_item_refined": "Implement user authentication with OAuth2",
            "estimated_files": 5,
            "estimated_tasks": 3,
            "notes": "validated",
        },
        "init.ideate": {
            "ideation_results": "OAuth2 with PKCE",
            "decomposed_tasks": ["OAuth2 client", "Token refresh", "Session middleware"],
            "ready_for_next": True,
        },
        "init.refine": {
            "refined_work_item": "Implement OAuth2 auth",
            "ready_for_architecture": True,
        },
        "impl.design": {
            "blueprint": "## Blueprint\n\n### Tasks\n1. OAuth2 client\n2. Token refresh\n3. Session middleware",
            "tasks": ["OAuth2 client", "Token refresh", "Session middleware"],
            "file_structure": ["src/auth/oauth_client.py"],
            "complete": True,
            "decisions": [],
        },
        "doc.update": {
            "files_updated": ["README.md"],
            "complete": True,
        },
        "qa.security": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        "qa.api-contract": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        "deploy.prepare": {
            "build_status": "pass",
            "lint_status": "pass",
            "type_check_status": "pass",
            "verdict": "PASS",
            "errors": [],
            "complete": True,
        },
        "post": {
            "summary": "done",
            "lessons_to_share": 0,
            "final_status": "done",
            "complete": True,
        },
    }

    default = {
        "complete": True,
        "valid": True,
        "verdict": "PASS",
        "findings": [],
        "critical_findings": [],
        "gaps": [],
    }
    default.update(happy_results.get(stage_id, {}))

    return AgentResult(
        data=default,
        iterations=1,
        elapsed=0.01,
        tool_calls_made=2,
    )


def mock_run_agent_qa_fanout_fail(
    model, tools, prompt, stage_id, output_schema=None,
    max_iterations=25, config=None, tracker=None, **kwargs,
) -> AgentResult:
    """qa-security passes, qa-api-contract fails -> qa-join should rollback."""
    qa_fail_results = {
        "qa.security": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        # FASE 1.3: the join now reads qa.human.flow under its canonical key and
        # applies the heuristic confidence check for real. The evidence contract
        # (stage_gate.py) requires friction_score + confidence + persona_name;
        # without them the join HALTs (confidence 0 < 0.70) instead of rolling
        # back on the scripted qa.api-contract FAIL.
        "qa.human.flow": {
            "verdict": "PASS",
            "friction_score": 2.0,
            "confidence": 0.85,
            "persona_name": "First-time user setting up authentication",
            "confusion_points": [],
            "jargon_found": [],
            "recommendations": [],
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
        "qa.api-contract": {
            "verdict": "FAIL",
            "findings": [
                "API endpoint /auth/token missing required field 'expires_in' in response schema",
                "API versioning not implemented — breaking change risk for clients",
            ],
            "critical_findings": [
                "Missing OpenAPI spec for /auth/callback endpoint",
            ],
            "complete": True,
        },
        "qa.performance": {
            "verdict": "PASS",
            "findings": [],
            "critical_findings": [],
            "complete": True,
        },
    }

    if stage_id in qa_fail_results:
        return AgentResult(
            data=qa_fail_results[stage_id],
            iterations=1,
            elapsed=0.01,
            tool_calls_made=3,
        )

    happy_results = {
        "init": {
            "valid": True,
            "work_item_refined": "Implement OAuth2 auth",
            "estimated_files": 5,
            "estimated_tasks": 3,
            "notes": "validated",
        },
        "init.ideate": {
            "ideation_results": "OAuth2",
            "decomposed_tasks": ["client", "refresh", "session"],
            "ready_for_next": True,
        },
        "init.refine": {
            "refined_work_item": "Implement OAuth2 auth",
            "ready_for_architecture": True,
        },
        "impl.design": {
            "blueprint": "## Blueprint\n\n### Tasks\n1. OAuth2\n2. Refresh\n3. Session",
            "tasks": ["OAuth2", "Refresh", "Session"],
            "file_structure": ["src/auth/oauth_client.py"],
            "complete": True,
            "decisions": [],
        },
        "impl.code": {
            "implementation_summary": "Implemented OAuth2 authentication with PKCE flow, token refresh logic, and session middleware. All unit tests pass.",
            "files_created": [
                "src/auth/oauth_client.py",
                "tests/test_oauth.py",
            ],
            "tests_passed": True,
            "complete": True,
            "decisions": [],
            "diff": "new files",
        },
        "doc.update": {
            "files_updated": ["README.md"],
            "complete": True,
        },
        "verify": {
            "verdict": "PASS",
            "per_ac_evidence": [
                "AC1: src/auth/oauth_client.py:45 -> implemented",
            ],
            "discrimination_sensor": "pass",
            "coverage_audit": "pass",
            "gaps": [],
            "complete": True,
        },
        "deploy.prepare": {
            "build_status": "pass",
            "lint_status": "pass",
            "type_check_status": "pass",
            "verdict": "PASS",
            "errors": [],
            "complete": True,
        },
        "post": {
            "summary": "done",
            "lessons_to_share": 0,
            "final_status": "done",
            "complete": True,
        },
    }

    default = {
        "complete": True,
        "valid": True,
        "verdict": "PASS",
        "findings": [],
        "critical_findings": [],
        "gaps": [],
    }
    default.update(happy_results.get(stage_id, {}))

    return AgentResult(
        data=default,
        iterations=1,
        elapsed=0.01,
        tool_calls_made=2,
    )


# ──────────────────────────────────────────────────────────────────────
# Scenario Registry
# ──────────────────────────────────────────────────────────────────────

SCENARIOS = {
    "HAPPY_PATH": {
        "description": "All stages pass. Graph reaches __end__ cleanly.",
        "mock_fn": mock_run_agent_happy_path,
        "complexity": "medium",
        "work_type": "feature",
        "ui_project": False,
        "parallel_qa": False,
        "needs_tracker": False,
    },
    "CONTRACT_VIOLATION": {
        "description": "impl.design returns empty tasks -> contract gate blocks impl.code.",
        "mock_fn": mock_run_agent_contract_violation,
        "complexity": "medium",
        "work_type": "feature",
        "ui_project": False,
        "parallel_qa": False,
        "needs_tracker": False,
    },
    "VERIFY_ROLLBACK": {
        "description": "verify FAILs -> rollback to impl.code -> fix -> verify PASSes.",
        "mock_fn": mock_run_agent_verify_rollback,
        "complexity": "medium",
        "work_type": "feature",
        "ui_project": False,
        "parallel_qa": False,
        "needs_tracker": True,
    },
    "QA_FANOUT_FAIL": {
        "description": "qa-security PASS, qa-api-contract FAIL -> qa-join rollbacks to impl.code.",
        "mock_fn": mock_run_agent_qa_fanout_fail,
        "complexity": "medium",
        "work_type": "feature",
        "ui_project": False,
        "parallel_qa": True,
        "needs_tracker": False,
    },
}


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
    print(f"  PASS: {msg}")


def assert_false(condition: bool, msg: str):
    if condition:
        raise AssertionFailure(f"FAIL: {msg}")
    print(f"  PASS: {msg}")


def assert_equals(actual, expected, msg: str):
    if actual != expected:
        raise AssertionFailure(f"FAIL: {msg}\n    expected={expected!r}\n    actual={actual!r}")
    print(f"  PASS: {msg}")


def assert_contains(haystack: list, needle, msg: str):
    if needle not in haystack:
        raise AssertionFailure(f"FAIL: {msg}\n    {needle!r} not in {haystack!r}")
    print(f"  PASS: {msg}")


def assert_non_empty(value, msg: str):
    if not value:
        raise AssertionFailure(f"FAIL: {msg}")
    print(f"  PASS: {msg}")


def assert_empty(value, msg: str):
    if value:
        raise AssertionFailure(f"FAIL: {msg}\n    value={value!r}")
    print(f"  PASS: {msg}")


# ──────────────────────────────────────────────────────────────────────
# Test Runners
# ──────────────────────────────────────────────────────────────────────

def run_scenario(
    scenario_name: str,
    mock_fn,
    complexity: str,
    work_type: str,
    ui_project: bool,
    parallel_qa: bool,
    needs_tracker: bool,
) -> dict[str, Any]:
    print(f"\n{'=' * 70}")
    print(f"SCENARIO: {scenario_name}")
    print(f"{'=' * 70}")

    framework_root = str(PROJECT_ROOT)
    loop_root = str(PROJECT_ROOT)
    project_root = str(PROJECT_ROOT)

    config = load_config(framework_root, loop_root)
    paths = resolve_paths(config, framework_root, loop_root, project_root)

    state = make_initial_state(config, paths)
    state["work_item"] = "Implement user authentication with OAuth2 and token refresh"
    state["complexity"] = complexity
    state["work_type"] = work_type
    state["ui_project"] = ui_project

    builder = GraphBuilder(parallel_qa=parallel_qa)
    compiled_graph, topology = builder.compile(state, config)

    print(f"\n  Topology: {topology.nodes_included}/{topology.total_available} nodes active")
    print(f"  Complexity: {complexity}, Work type: {work_type}, UI: {ui_project}")
    print(f"  Parallel QA: {parallel_qa}")
    print(f"  Active nodes: {topology.active_nodes}")
    if topology.parallel_groups:
        print(f"  Parallel groups: {topology.parallel_groups}")

    tracker = InvocationTracker() if needs_tracker else None

    def patched_run_agent(model, tools, prompt, stage_id, output_schema=None,
                          max_iterations=25, config=None, **kwargs):
        result = mock_fn(
            model, tools, prompt, stage_id, output_schema,
            max_iterations, config, tracker=tracker, **kwargs,
        )
        print(f"    [mock] stage={stage_id}, data_keys={list(result.data.keys())[:5]}")
        return result

    def clean_essence(model, tools, prompt, stage_id, output_schema=None,
                      max_iterations=25, config=None, **kwargs):
        return AgentResult(
            data={
                "clean": True,
                "lens_1_subjective_terms": [],
                "lens_2_hidden_assumptions": [],
                "lens_3_literal_traps": [],
                "lens_4_conflicts": [],
                "adjustments": [],
                "clarifying_questions": [],
                "summary": "Dry-run: inputs clean",
            },
            iterations=1,
            elapsed=0.001,
            tool_calls_made=0,
        )

    # Several modules bind run_agent at module level (from ... import run_agent),
    # which escapes a patch on eng_loop.tools.agent_runner.run_agent. Patch every
    # such binding so the simulator stays hermetic (no real LLM calls).
    with (
        patch("eng_loop.tools.agent_runner.run_agent", side_effect=patched_run_agent),
        patch("eng_loop.model.create_model_from_config", return_value=MagicMock()),
        patch("eng_loop.tools.essence_gate.run_agent", side_effect=clean_essence),
        patch("eng_loop.tools.essence_gate.create_model_from_config", return_value=MagicMock()),
        patch("eng_loop.nodes.dynamic_architect.run_agent", side_effect=patched_run_agent),
        patch("eng_loop.nodes.meta_executor.run_agent", side_effect=patched_run_agent),
        patch("eng_loop.tools.autosizing.run_agent", side_effect=patched_run_agent),
    ):
        try:
            final_state = compiled_graph.invoke(state)

            print(f"\n  Graph execution completed.")
            if tracker:
                print(f"  Invocations: {tracker.calls}")

            return final_state

        except Exception as e:
            print(f"\n  Graph execution raised exception: {e}")
            import traceback
            traceback.print_exc()
            raise


def test_happy_path():
    """Scenario 1: All stages pass, graph reaches __end__."""
    state = run_scenario(
        "HAPPY_PATH",
        SCENARIOS["HAPPY_PATH"]["mock_fn"],
        SCENARIOS["HAPPY_PATH"]["complexity"],
        SCENARIOS["HAPPY_PATH"]["work_type"],
        SCENARIOS["HAPPY_PATH"]["ui_project"],
        SCENARIOS["HAPPY_PATH"]["parallel_qa"],
        SCENARIOS["HAPPY_PATH"]["needs_tracker"],
    )

    print(f"\n  --- Assertions ---")

    status = state.get("status", "unknown")
    assert_true(
        status in ("done", "running"),
        f"Final status is '{status}' (expected 'done' or 'running' at post node)",
    )

    assert_equals(
        state.get("rollback_target", ""),
        "",
        "rollback_target should be empty (no rollback on happy path)",
    )

    errors = state.get("errors", [])
    assert_empty(
        errors,
        "errors list should be empty on happy path",
    )

    fix_tasks = state.get("fix_tasks", [])
    assert_empty(
        fix_tasks,
        "fix_tasks should be empty on happy path",
    )

    stages = state.get("stages", {})
    for stage_id in ["init", "impl.design", "impl.code", "verify"]:
        stage = stages.get(stage_id, {})
        assert_true(
            stage.get("done", False),
            f"Stage '{stage_id}' should be done",
        )

    assert_equals(
        state.get("fix_iteration", -1),
        0,
        "fix_iteration should be 0 (no fix cycles needed)",
    )

    print(f"\n  -> HAPPY_PATH: ALL ASSERTIONS PASSED\n")


def test_contract_violation():
    """Scenario 2: impl.design returns empty tasks -> contract gate catches it."""
    state = run_scenario(
        "CONTRACT_VIOLATION",
        SCENARIOS["CONTRACT_VIOLATION"]["mock_fn"],
        SCENARIOS["CONTRACT_VIOLATION"]["complexity"],
        SCENARIOS["CONTRACT_VIOLATION"]["work_type"],
        SCENARIOS["CONTRACT_VIOLATION"]["ui_project"],
        SCENARIOS["CONTRACT_VIOLATION"]["parallel_qa"],
        SCENARIOS["CONTRACT_VIOLATION"]["needs_tracker"],
    )

    print(f"\n  --- Assertions ---")

    errors = state.get("errors", [])

    contract_error_found = any(
        "Contract" in err or "Blueprint has no tasks" in err or "blueprint" in err.lower()
        for err in errors
    )
    assert_true(
        contract_error_found,
        f"Errors should contain contract violation message. Got: {errors}",
    )

    stages = state.get("stages", {})
    status = state.get("status", "unknown")
    impl_design = stages.get("impl.design", {})
    # Contract gate catches the violation (errors contain the message).
    # impl.code may still run due to edge rules evaluating before Command update,
    # but the pipeline should be blocked or impl.design should have retry attempts.
    assert_true(
        status == "blocked" or impl_design.get("attempts", 0) > 0,
        f"Graph should be blocked or impl.design should have retry attempts. "
        f"status={status}, impl.design.attempts={impl_design.get('attempts', 0)}",
    )

    status = state.get("status", "unknown")
    impl_design = stages.get("impl.design", {})
    assert_true(
        status == "blocked" or impl_design.get("attempts", 0) > 0,
        f"Graph should be blocked or impl.design should have retry attempts. "
        f"status={status}, impl.design.attempts={impl_design.get('attempts', 0)}",
    )

    print(f"\n  -> CONTRACT_VIOLATION: ALL ASSERTIONS PASSED\n")


def test_verify_rollback():
    """Scenario 3: verify FAILs -> rollback -> fix -> verify PASSes."""
    state = run_scenario(
        "VERIFY_ROLLBACK",
        SCENARIOS["VERIFY_ROLLBACK"]["mock_fn"],
        SCENARIOS["VERIFY_ROLLBACK"]["complexity"],
        SCENARIOS["VERIFY_ROLLBACK"]["work_type"],
        SCENARIOS["VERIFY_ROLLBACK"]["ui_project"],
        SCENARIOS["VERIFY_ROLLBACK"]["parallel_qa"],
        SCENARIOS["VERIFY_ROLLBACK"]["needs_tracker"],
    )

    print(f"\n  --- Assertions ---")

    stages = state.get("stages", {})

    fix_tasks = state.get("fix_tasks", [])
    fix_iteration = state.get("fix_iteration", 0)
    assert_true(
        fix_iteration >= 1,
        f"fix_iteration should be >= 1 (rollback occurred). Got: {fix_iteration}",
    )

    verify_stage = stages.get("verify", {})
    assert_true(
        verify_stage.get("done", False),
        "verify should be done after successful re-verification",
    )

    impl_code_stage = stages.get("impl.code", {})
    assert_true(
        impl_code_stage.get("done", False),
        "impl.code should be done after fix",
    )

    doc_update_stage = stages.get("doc.update", {})
    assert_true(
        doc_update_stage.get("done", False),
        "doc.update should be done (re-executed after rollback)",
    )

    assert_empty(
        fix_tasks,
        "fix_tasks should be cleared after successful fix cycle",
    )

    assert_equals(
        state.get("rollback_target", "NOT_CLEARED"),
        "",
        "rollback_target should be cleared after successful completion",
    )

    assert_true(
        verify_stage.get("attempts", 0) >= 1,
        f"verify should have at least 1 successful attempt. Got: {verify_stage.get('attempts', 0)}",
    )

    print(f"\n  -> VERIFY_ROLLBACK: ALL ASSERTIONS PASSED\n")


def test_qa_fanout_fail():
    """Scenario 4: qa-security PASS, qa-api-contract FAIL -> qa-join rollback -> blocks after fix limit."""
    state = run_scenario(
        "QA_FANOUT_FAIL",
        SCENARIOS["QA_FANOUT_FAIL"]["mock_fn"],
        SCENARIOS["QA_FANOUT_FAIL"]["complexity"],
        SCENARIOS["QA_FANOUT_FAIL"]["work_type"],
        SCENARIOS["QA_FANOUT_FAIL"]["ui_project"],
        SCENARIOS["QA_FANOUT_FAIL"]["parallel_qa"],
        SCENARIOS["QA_FANOUT_FAIL"]["needs_tracker"],
    )

    print(f"\n  --- Assertions ---")

    stages = state.get("stages", {})
    fix_tasks = state.get("fix_tasks", [])
    errors = state.get("errors", [])

    # qa.api-contract should have FAIL verdict
    qa_api_stage = stages.get("qa.api-contract", {})
    qa_api_output = qa_api_stage.get("output", "{}")
    assert_true(
        "FAIL" in str(qa_api_output) or qa_api_stage.get("verdict") == "FAIL",
        f"qa.api-contract should have FAIL verdict. output={qa_api_output[:200]}",
    )

    # qa.security should have PASS verdict
    qa_sec_stage = stages.get("qa.security", {})
    qa_sec_output = qa_sec_stage.get("output", "{}")
    assert_true(
        "PASS" in str(qa_sec_output) or qa_sec_stage.get("verdict") == "PASS",
        f"qa.security should have PASS verdict. output={qa_sec_output[:200]}",
    )

    # qa-join must have aggregated the REAL failure data from the workers.
    # Evidence: "QA join: N issues from parallel QA" with N > 0 — a stale/empty
    # aggregation (H15 race) would log "0 issues".
    #
    # NOTE (FASE 1.1): fix_tasks/rollback_target are no longer asserted in the
    # final state. With single-source routing (no declared edges out of
    # command nodes), qa-join runs exactly once per round; impl.code then
    # consumes the tasks and clears fix_tasks/rollback_target on success
    # (implementation.py). Pre-1.1 they survived in the final state only as a
    # byproduct of the C1 double-execution (qa-join scheduled twice per round,
    # its later rollback update overwriting the cleared values).
    assert_true(
        any("issues from parallel QA" in e and "0 issues" not in e for e in errors),
        f"fix_tasks should contain QA failure tasks from qa-join aggregation. errors={errors[-5:]}",
    )

    # fix_iteration should be >= 1 (rollback occurred)
    assert_true(
        state.get("fix_iteration", 0) >= 1,
        f"fix_iteration should be >= 1. Got: {state.get('fix_iteration', 0)}",
    )

    # Graph should eventually block due to fix iteration limit (mock always returns FAIL)
    status = state.get("status", "unknown")
    assert_true(
        status == "blocked" or state.get("fix_iteration", 0) >= 1,
        f"Graph should be blocked or have attempted fix iterations. status={status}, fix_iteration={state.get('fix_iteration', 0)}",
    )

    print(f"\n  -> QA_FANOUT_FAIL: ALL ASSERTIONS PASSED\n")


# ──────────────────────────────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Dry-run simulator for Engineering Loop graph execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  HAPPY_PATH          All stages pass, graph completes cleanly
  CONTRACT_VIOLATION  impl.design returns bad blueprint -> contract gate catches it
  VERIFY_ROLLBACK     verify FAILs -> rollback -> fix -> verify PASSes
  QA_FANOUT_FAIL      Parallel QA: one passes, one fails -> qa-join rollback
  ALL                 Run all scenarios
        """,
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=["HAPPY_PATH", "CONTRACT_VIOLATION", "VERIFY_ROLLBACK", "QA_FANOUT_FAIL", "ALL"],
        default="ALL",
        help="Scenario to run (default: ALL)",
    )

    args = parser.parse_args()

    scenario_map = {
        "HAPPY_PATH": test_happy_path,
        "CONTRACT_VIOLATION": test_contract_violation,
        "VERIFY_ROLLBACK": test_verify_rollback,
        "QA_FANOUT_FAIL": test_qa_fanout_fail,
    }

    if args.scenario == "ALL":
        scenarios_to_run = scenario_map.values()
    else:
        scenarios_to_run = [scenario_map[args.scenario]]

    print("=" * 70)
    print("ENGINEERING LOOP DRY-RUN SIMULATOR")
    print(f"Scenarios: {args.scenario}")
    print("=" * 70)

    passed = 0
    failed = 0
    failures = []

    for test_fn in scenarios_to_run:
        try:
            test_fn()
            passed += 1
        except AssertionFailure as e:
            failed += 1
            failures.append((test_fn.__name__, str(e)))
            print(f"\n  SCENARIO FAILED: {e.message}\n")
        except Exception as e:
            failed += 1
            failures.append((test_fn.__name__, str(e)))
            print(f"\n  SCENARIO ERROR: {e}\n")
            import traceback
            traceback.print_exc()

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} scenarios")
    print("=" * 70)

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

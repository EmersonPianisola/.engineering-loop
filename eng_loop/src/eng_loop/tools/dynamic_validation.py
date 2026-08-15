from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eng_loop.schemas import ValidationRule


def evaluate_validation_rules(
    agent_result: dict[str, Any],
    rules: tuple[ValidationRule, ...],
    workspace_root: str,
    state: dict[str, Any],
) -> tuple[bool, str | None]:
    """Evaluate all typed validation rules against agent output.

    Returns (True, None) if all rules pass or rules tuple is empty.
    Returns (False, error_message) on first failure.
    """
    if not rules:
        return True, None

    for rule in rules:
        passed, err = _evaluate_single_rule(rule, agent_result, workspace_root, state)
        if not passed:
            return False, err

    return True, None


def _evaluate_single_rule(
    rule: ValidationRule,
    agent_result: dict[str, Any],
    workspace_root: str,
    state: dict[str, Any],
) -> tuple[bool, str | None]:
    if rule.type == "tests_pass":
        return _eval_tests_pass(rule.payload, workspace_root)
    if rule.type == "files_exist":
        return _eval_files_exist(rule.payload, workspace_root)
    if rule.type == "contains_symbol":
        return _eval_contains_symbol(rule.payload, workspace_root)

    return False, f"Unknown validation rule type: {rule.type}"


def _eval_tests_pass(
    payload: Any,
    workspace_root: str,
) -> tuple[bool, str | None]:
    """Run a test suite command and verify exit code is 0."""
    suite = getattr(payload, "suite", "unit")
    command = getattr(payload, "command", "")

    if not command:
        suite_commands = {
            "unit": "pytest --tb=short -q",
            "integration": "pytest --tb=short -q -m integration",
            "e2e": "playwright test --reporter=line",
        }
        command = suite_commands.get(suite, "pytest --tb=short -q")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            return True, None
        return False, f"tests_pass({suite}): exit code {result.returncode}: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, f"tests_pass({suite}): timed out after 120s"
    except Exception as e:
        return False, f"tests_pass({suite}): {e}"


def _eval_files_exist(
    payload: Any,
    workspace_root: str,
) -> tuple[bool, str | None]:
    """Verify that all required paths exist relative to workspace root."""
    paths = getattr(payload, "paths", ())
    root = Path(workspace_root).resolve()

    missing = []
    for p in paths:
        target = (root / p).resolve()
        if not target.exists():
            missing.append(p)

    if missing:
        return False, f"files_exist: missing {missing}"
    return True, None


def _eval_contains_symbol(
    payload: Any,
    workspace_root: str,
) -> tuple[bool, str | None]:
    """Search for a symbol/regex pattern in a target file."""
    symbol = getattr(payload, "symbol", "")
    target_file = getattr(payload, "target_file", "")

    root = Path(workspace_root).resolve()
    target_path = (root / target_file).resolve()

    if not target_path.exists():
        return False, f"contains_symbol: target file '{target_file}' not found"

    try:
        content = target_path.read_text(encoding="utf-8")
        if re.search(symbol, content):
            return True, None
        return False, f"contains_symbol: pattern '{symbol}' not found in '{target_file}'"
    except Exception as e:
        return False, f"contains_symbol: {e}"

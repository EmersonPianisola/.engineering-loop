from __future__ import annotations

"""Integration tests: dynamic validation rules.

Validates the typed validation rule evaluation:
  - tests_pass: runs test suite command, checks exit code
  - files_exist: verifies paths exist relative to workspace root
  - contains_symbol: searches for regex pattern in target file
"""

import tempfile
from pathlib import Path

from eng_loop.schemas import FilesExistPayload, SymbolPayload, TestsPassPayload, ValidationRule
from eng_loop.tools.dynamic_validation import (
    _eval_contains_symbol,
    _eval_files_exist,
    _eval_tests_pass,
    evaluate_validation_rules,
)


class TestEvaluateValidationRules:
    """evaluate_validation_rules orchestrator."""

    def test_empty_rules_pass(self):
        passed, err = evaluate_validation_rules(
            agent_result={"complete": True},
            rules=(),
            workspace_root=".",
            state={},
        )
        assert passed is True
        assert err is None

    def test_multiple_rules_all_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "src/main.py").parent.mkdir(exist_ok=True)
            Path(tmp, "src/main.py").write_text("def hello(): pass", encoding="utf-8")
            Path(tmp, "tests/test_main.py").parent.mkdir(exist_ok=True)
            Path(tmp, "tests/test_main.py").write_text("def test_hello(): pass", encoding="utf-8")

            rules = (
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("src/main.py", "tests/test_main.py")),
                ),
                ValidationRule(
                    type="contains_symbol",
                    payload=SymbolPayload(symbol="def hello", target_file="src/main.py"),
                ),
            )

            passed, err = evaluate_validation_rules(
                agent_result={},
                rules=rules,
                workspace_root=tmp,
                state={},
            )
            assert passed is True
            assert err is None

    def test_first_failing_rule_short_circuits(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules = (
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("nonexistent.py",)),
                ),
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=(".",)),
                ),
            )

            passed, err = evaluate_validation_rules(
                agent_result={},
                rules=rules,
                workspace_root=tmp,
                state={},
            )
            assert passed is False
            assert "nonexistent.py" in err


class TestEvalFilesExist:
    """files_exist: verify paths exist relative to workspace root."""

    def test_all_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "src/main.py").parent.mkdir(exist_ok=True)
            Path(tmp, "src/main.py").write_text("code", encoding="utf-8")
            Path(tmp, "README.md").write_text("readme", encoding="utf-8")

            payload = FilesExistPayload(paths=("src/main.py", "README.md"))
            passed, err = _eval_files_exist(payload, tmp)
            assert passed is True
            assert err is None

    def test_one_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "exists.py").write_text("code", encoding="utf-8")

            payload = FilesExistPayload(paths=("exists.py", "missing.py"))
            passed, err = _eval_files_exist(payload, tmp)
            assert passed is False
            assert "missing.py" in err

    def test_all_files_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = FilesExistPayload(paths=("a.py", "b.py"))
            passed, err = _eval_files_exist(payload, tmp)
            assert passed is False
            assert "a.py" in err
            assert "b.py" in err

    def test_empty_paths_malformed(self):
        # 4.3.7 — an empty paths payload is a malformed rule and must FAIL the
        # step; the old behavior silently passed (vacuously true check).
        with tempfile.TemporaryDirectory() as tmp:
            payload = FilesExistPayload(paths=())
            passed, err = _eval_files_exist(payload, tmp)
            assert passed is False
            assert "malformed rule payload" in (err or "")

    def test_nested_directory_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b" / "c"
            nested.mkdir(parents=True, exist_ok=True)
            (nested / "file.py").write_text("code", encoding="utf-8")

            payload = FilesExistPayload(paths=("a/b/c/file.py",))
            passed, err = _eval_files_exist(payload, tmp)
            assert passed is True

    def test_directory_path_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "src").mkdir(exist_ok=True)

            payload = FilesExistPayload(paths=("src",))
            passed, err = _eval_files_exist(payload, tmp)
            assert passed is True


class TestEvalContainsSymbol:
    """contains_symbol: search for regex pattern in target file."""

    def test_symbol_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "main.py").write_text("def hello_world():\n    return 42", encoding="utf-8")

            payload = SymbolPayload(symbol="def hello_world", target_file="main.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is True

    def test_symbol_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "main.py").write_text("def hello(): pass", encoding="utf-8")

            payload = SymbolPayload(symbol="def goodbye", target_file="main.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is False
            assert "not found" in err

    def test_regex_pattern_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.py").write_text("PORT = 8080\nHOST = 'localhost'", encoding="utf-8")

            payload = SymbolPayload(symbol=r"PORT\s*=\s*\d+", target_file="config.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is True

    def test_target_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = SymbolPayload(symbol="anything", target_file="nonexistent.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is False
            assert "not found" in err

    def test_multiline_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = """
class MyClass:
    def method(self):
        return True
"""
            Path(tmp, "module.py").write_text(content, encoding="utf-8")

            payload = SymbolPayload(symbol="class MyClass", target_file="module.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is True

    def test_case_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "file.py").write_text("Hello World", encoding="utf-8")

            payload = SymbolPayload(symbol="hello", target_file="file.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is False

    def test_case_insensitive_regex(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "file.py").write_text("Hello World", encoding="utf-8")

            payload = SymbolPayload(symbol="(?i)hello", target_file="file.py")
            passed, err = _eval_contains_symbol(payload, tmp)
            assert passed is True


class TestEvalTestsPass:
    """tests_pass: run test suite command and verify exit code."""

    def test_tests_pass_with_custom_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = TestsPassPayload(suite="unit", command="echo pass")
            passed, err = _eval_tests_pass(payload, tmp)
            assert passed is True

    def test_tests_fail_with_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = TestsPassPayload(suite="unit", command="exit 1")
            passed, err = _eval_tests_pass(payload, tmp)
            assert passed is False
            assert "exit code 1" in err

    def test_default_command_for_unit_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = TestsPassPayload(suite="unit", command="")
            passed, err = _eval_tests_pass(payload, tmp)

    def test_default_command_for_integration_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = TestsPassPayload(suite="integration", command="")
            passed, err = _eval_tests_pass(payload, tmp)

    def test_command_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = TestsPassPayload(suite="unit", command="sleep 300")
            passed, err = _eval_tests_pass(payload, tmp)
            assert passed is False
            assert "timed out" in err

    def test_test_command_output_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = TestsPassPayload(suite="unit", command="echo test-output")
            passed, err = _eval_tests_pass(payload, tmp)
            assert passed is True


class TestValidationRuleIntegration:
    """End-to-end: agent result -> validation rules -> pass/fail."""

    def test_full_validation_pipeline_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "src/app.py").parent.mkdir(exist_ok=True)
            Path(tmp, "src/app.py").write_text("def main(): print('hello')", encoding="utf-8")
            Path(tmp, "tests/test_app.py").parent.mkdir(exist_ok=True)
            Path(tmp, "tests/test_app.py").write_text("def test_main(): assert True", encoding="utf-8")

            agent_result = {
                "complete": True,
                "files_created": ["src/app.py", "tests/test_app.py"],
            }

            rules = (
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("src/app.py", "tests/test_app.py")),
                ),
                ValidationRule(
                    type="contains_symbol",
                    payload=SymbolPayload(symbol="def main", target_file="src/app.py"),
                ),
            )

            passed, err = evaluate_validation_rules(
                agent_result=agent_result,
                rules=rules,
                workspace_root=tmp,
                state={},
            )
            assert passed is True

    def test_full_validation_pipeline_fail_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent_result = {
                "complete": True,
                "files_created": ["src/app.py"],
            }

            rules = (
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("src/app.py", "tests/test_app.py")),
                ),
            )

            passed, err = evaluate_validation_rules(
                agent_result=agent_result,
                rules=rules,
                workspace_root=tmp,
                state={},
            )
            assert passed is False
            assert "tests/test_app.py" in err

    def test_full_validation_pipeline_fail_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "src/app.py").parent.mkdir(exist_ok=True)
            Path(tmp, "src/app.py").write_text("# empty file", encoding="utf-8")

            agent_result = {
                "complete": True,
                "files_created": ["src/app.py"],
            }

            rules = (
                ValidationRule(
                    type="files_exist",
                    payload=FilesExistPayload(paths=("src/app.py",)),
                ),
                ValidationRule(
                    type="contains_symbol",
                    payload=SymbolPayload(symbol="def main", target_file="src/app.py"),
                ),
            )

            passed, err = evaluate_validation_rules(
                agent_result=agent_result,
                rules=rules,
                workspace_root=tmp,
                state={},
            )
            assert passed is False
            assert "def main" in err


class TestUnknownRuleType:
    """Unknown validation rule type returns error."""

    def test_unknown_rule_type(self):
        # ValidationRule enforces type-payload correlation, so an invalid
        # type/payload pair can't be built — test the _evaluate_single_rule path.
        from eng_loop.tools.dynamic_validation import _evaluate_single_rule

        class FakeRule:
            type = "unknown_type"
            payload = object()

        passed, err = _evaluate_single_rule(
            FakeRule(),
            {},
            ".",
            {},
        )
        assert passed is False
        assert "Unknown validation rule type" in err

    def test_none_payload_is_malformed(self):
        # 4.3.7 — a missing payload is malformed (fails closed) before the
        # rule-type dispatch.
        from eng_loop.tools.dynamic_validation import _evaluate_single_rule

        class FakeRule:
            type = "unknown_type"
            payload = None

        passed, err = _evaluate_single_rule(
            FakeRule(),
            {},
            ".",
            {},
        )
        assert passed is False
        assert "malformed rule payload" in (err or "")

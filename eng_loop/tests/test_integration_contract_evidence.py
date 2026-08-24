from __future__ import annotations

"""Integration tests: contract gate + evidence gate validation chain.

Validates the inter-stage contract enforcement:
  stage output → contract gate → proceed/retry/block → evidence gate
"""

import json

from langgraph.types import Command

from eng_loop.tools.contract_gate import (
    CONTRACT_RULES,
    blueprint_has_tasks,
    code_exists_for_verify,
    contract_gate_middleware,
    implementation_artifacts_exist,
    verify_has_substantive_output,
    with_contract_gate,
)
from eng_loop.tools.evidence_gate import (
    MIN_OUTPUT_LENGTH,
    validate_stage_output,
)


class TestContractGateBlueprintHasTasks:
    """impl.design → impl.code: Blueprint must contain actionable tasks."""

    def test_blueprint_with_tasks_passes(self):
        source_output = {
            "tasks": [{"id": "1", "description": "Create API endpoint"}],
            "blueprint": "Detailed implementation blueprint with architecture decisions and task breakdown for the feature",
        }
        valid, msg = blueprint_has_tasks(source_output, {})
        assert valid is True
        assert msg == "ok"

    def test_blueprint_empty_tasks_fails(self):
        source_output = {
            "tasks": [],
            "blueprint": "Some blueprint content",
        }
        valid, msg = blueprint_has_tasks(source_output, {})
        assert valid is False
        assert "no tasks" in msg

    def test_blueprint_missing_tasks_fails(self):
        source_output = {
            "blueprint": "Some blueprint content",
        }
        valid, msg = blueprint_has_tasks(source_output, {})
        assert valid is False
        assert "no tasks" in msg

    def test_blueprint_too_short_fails(self):
        source_output = {
            "tasks": [{"id": "1"}],
            "blueprint": "Short",
        }
        valid, msg = blueprint_has_tasks(source_output, {})
        assert valid is False
        assert "too short" in msg

    def test_blueprint_minimal_length_passes(self):
        source_output = {
            "tasks": [{"id": "1"}],
            "blueprint": "x" * 50,
        }
        valid, msg = blueprint_has_tasks(source_output, {})
        assert valid is True


class TestContractGateCodeExistsForVerify:
    """impl.code → doc-update: Implementation must have produced artifacts."""

    def test_code_with_files_and_tests_passes(self):
        source_output = {
            "files_created": ["src/main.py", "tests/test_main.py"],
            "tests_passed": True,
            "implementation_summary": "Implemented the feature with comprehensive test coverage and documentation",
        }
        valid, msg = code_exists_for_verify(source_output, {})
        assert valid is True

    def test_no_files_created_fails(self):
        source_output = {
            "files_created": [],
            "tests_passed": True,
            "implementation_summary": "Some summary",
        }
        valid, msg = code_exists_for_verify(source_output, {})
        assert valid is False
        assert "No files created" in msg

    def test_tests_not_passing_fails(self):
        source_output = {
            "files_created": ["file.py"],
            "tests_passed": False,
            "implementation_summary": "Some summary text here",
        }
        valid, msg = code_exists_for_verify(source_output, {})
        assert valid is False
        assert "Tests not passing" in msg

    def test_short_summary_fails(self):
        source_output = {
            "files_created": ["file.py"],
            "tests_passed": True,
            "implementation_summary": "Short",
        }
        valid, msg = code_exists_for_verify(source_output, {})
        assert valid is False
        assert "too short" in msg


class TestContractGateImplementationArtifactsExist:
    """doc-update → verify: impl.code must have produced artifacts."""

    def test_artifacts_in_stage_artifacts_passes(self):
        source_output = {}
        state = {"stage_artifacts": {"impl.code": "Implementation output with sufficient detail for verification"}}
        valid, msg = implementation_artifacts_exist(source_output, state)
        assert valid is True

    def test_impl_code_done_with_output_passes(self):
        source_output = {}
        state = {
            "stage_artifacts": {},
            "stages": {"impl.code": {"done": True, "output": "Implementation output with sufficient detail"}},
        }
        valid, msg = implementation_artifacts_exist(source_output, state)
        assert valid is True

    def test_impl_code_not_done_fails(self):
        source_output = {}
        state = {"stage_artifacts": {}, "stages": {"impl.code": {"done": False}}}
        valid, msg = implementation_artifacts_exist(source_output, state)
        assert valid is False
        assert "not completed" in msg

    def test_empty_artifacts_fails(self):
        source_output = {}
        state = {"stage_artifacts": {"impl.code": ""}, "stages": {"impl.code": {"done": False}}}
        valid, msg = implementation_artifacts_exist(source_output, state)
        assert valid is False


class TestContractGateVerifySubstantiveOutput:
    """verify → downstream: Verdict must be explicit with evidence."""

    def test_pass_with_evidence_passes(self):
        source_output = {
            "verdict": "PASS",
            "per_ac_evidence": ["AC1 -> file.py:10", "AC2 -> file.py:20"],
        }
        valid, msg = verify_has_substantive_output(source_output, {})
        assert valid is True

    def test_fail_verdict_passes(self):
        source_output = {
            "verdict": "FAIL",
            "gaps": ["missing test coverage"],
        }
        valid, msg = verify_has_substantive_output(source_output, {})
        assert valid is True

    def test_pass_without_evidence_fails(self):
        source_output = {
            "verdict": "PASS",
            "per_ac_evidence": [],
        }
        valid, msg = verify_has_substantive_output(source_output, {})
        assert valid is False
        assert "no per-AC evidence" in msg

    def test_invalid_verdict_fails(self):
        source_output = {
            "verdict": "UNKNOWN",
        }
        valid, msg = verify_has_substantive_output(source_output, {})
        assert valid is False
        assert "Invalid verdict" in msg

    def test_missing_verdict_fails(self):
        source_output = {}
        valid, msg = verify_has_substantive_output(source_output, {})
        assert valid is False


class TestContractGateMiddleware:
    """Contract gate middleware intercepts node handler commands."""

    def test_proceed_when_contract_satisfied(self):
        handler_result = Command(goto="impl-code", update={"stages": {"impl.design": {"done": True}}})
        source_output = {
            "tasks": [{"id": "1"}],
            "blueprint": "Detailed blueprint with enough content for implementation guidance",
        }
        state = {"stages": {}}

        result = contract_gate_middleware("impl-design", handler_result, source_output, state)
        assert result.goto == "impl-code"

    def test_retry_source_when_contract_fails(self):
        handler_result = Command(goto="impl-code", update={"stages": {"impl.design": {"done": True}}})
        source_output = {
            "tasks": [],
            "blueprint": "Short",
        }
        state = {"stages": {"impl.design": {"attempts": 0}}}

        result = contract_gate_middleware("impl-design", handler_result, source_output, state)
        assert result.goto == "impl-design"

    def test_block_when_source_exhausted(self):
        handler_result = Command(goto="impl-code", update={"stages": {"impl.design": {"done": True}}})
        source_output = {
            "tasks": [],
            "blueprint": "Short",
        }
        state = {
            "stages": {"impl.design": {"attempts": 3}},
            "config": {"constraints": {"max_impl_design_attempts": 2}},
        }

        result = contract_gate_middleware("impl-design", handler_result, source_output, state)
        assert result.goto == "__end__"

    def test_skip_validation_for_end_command(self):
        handler_result = Command(goto="__end__", update={"status": "done"})
        source_output = {}
        state = {}

        result = contract_gate_middleware("post", handler_result, source_output, state)
        assert result.goto == "__end__"

    def test_no_matching_rule_proceeds(self):
        handler_result = Command(goto="init-ideate", update={})
        source_output = {}
        state = {}

        result = contract_gate_middleware("init", handler_result, source_output, state)
        assert result.goto == "init-ideate"


class TestContractGateDecorator:
    """with_contract_gate decorator wraps node handlers."""

    def test_decorator_passes_through_list_results(self):
        @with_contract_gate("qa-dispatcher")
        def mock_handler(state):
            return [Command(goto="qa-security", update={})]

        result = mock_handler({})
        assert isinstance(result, list)

    def test_decorator_validates_command_results(self):
        @with_contract_gate("impl-design")
        def mock_handler(state):
            return Command(
                goto="impl-code",
                update={
                    "stages": {
                        "impl-design": {
                            "done": True,
                            "output": {"tasks": [], "blueprint": "Short"},
                        }
                    }
                },
            )

        result = mock_handler({"stages": {"impl.design": {"attempts": 0}}})
        assert result.goto == "impl-design"


class TestEvidenceGateAllStages:
    """Evidence gate validates output quality for each stage type."""

    def test_verify_pass_with_evidence(self):
        result = {
            "verdict": "PASS",
            "per_ac_evidence": ["AC1 -> file.py:10"],
            "tests_passed": True,
        }
        valid, err = validate_stage_output("verify", result, json.dumps(result))
        assert valid is True

    def test_verify_fail_with_gaps(self):
        result = {
            "verdict": "FAIL",
            "gaps": ["missing coverage"],
        }
        valid, err = validate_stage_output("verify", result, json.dumps(result))
        assert valid is True

    def test_verify_fail_without_gaps(self):
        result = {
            "verdict": "FAIL",
            "gaps": [],
        }
        valid, err = validate_stage_output("verify", result, json.dumps(result))
        assert valid is False
        assert "no gaps" in err

    def test_verify_invalid_verdict(self):
        result = {"verdict": "MAYBE"}
        valid, err = validate_stage_output("verify", result, json.dumps(result))
        assert valid is False

    def test_impl_design_with_tasks(self):
        result = {
            "blueprint": "Detailed implementation plan",
            "tasks": [{"id": "1"}, {"id": "2"}],
        }
        valid, err = validate_stage_output("impl.design", result, json.dumps(result))
        assert valid is True

    def test_impl_design_no_tasks(self):
        result = {"blueprint": "Some blueprint", "tasks": []}
        valid, err = validate_stage_output("impl.design", result, json.dumps(result))
        assert valid is False
        assert "no tasks" in err

    def test_impl_code_with_summary(self):
        result = {
            "implementation_summary": "Implemented the feature with full test coverage and documentation",
            "files_created": ["src/main.py"],
        }
        valid, err = validate_stage_output("impl.code", result, json.dumps(result))
        assert valid is True

    def test_impl_code_short_summary(self):
        result = {
            "implementation_summary": "Short",
            "files_created": ["src/main.py"],
        }
        valid, err = validate_stage_output("impl.code", result, json.dumps(result))
        assert valid is False
        assert "too short" in err

    def test_init_valid(self):
        result = {"valid": True, "work_item_refined": "Refined work item"}
        valid, err = validate_stage_output("init", result, json.dumps(result))
        assert valid is True

    def test_init_with_refinement(self):
        result = {"valid": False, "work_item_refined": "Refined work item"}
        valid, err = validate_stage_output("init", result, json.dumps(result))
        assert valid is True

    def test_init_neither_valid_nor_refined(self):
        result = {"valid": False, "work_item_refined": ""}
        valid, err = validate_stage_output("init", result, json.dumps(result))
        assert valid is False

    def test_init_ideation_with_tasks(self):
        result = {
            "decomposed_tasks": ["task1"],
            "ideation_results": "",
        }
        valid, err = validate_stage_output("init.ideate", result, json.dumps(result))
        assert valid is True

    def test_init_ideation_with_substantial_output(self):
        result = {
            "decomposed_tasks": [],
            "ideation_results": "x" * MIN_OUTPUT_LENGTH,
        }
        valid, err = validate_stage_output("init.ideate", result, json.dumps(result))
        assert valid is True

    def test_init_ideation_empty(self):
        result = {"decomposed_tasks": [], "ideation_results": "short"}
        valid, err = validate_stage_output("init.ideate", result, json.dumps(result))
        assert valid is False

    def test_qa_security_pass(self):
        result = {"verdict": "PASS", "findings": []}
        valid, err = validate_stage_output("qa.security", result, json.dumps(result))
        assert valid is True

    def test_qa_security_fail(self):
        result = {"verdict": "FAIL", "findings": ["vulnerability found"]}
        valid, err = validate_stage_output("qa.security", result, json.dumps(result))
        assert valid is True

    def test_qa_security_invalid_verdict(self):
        result = {"verdict": "UNKNOWN"}
        valid, err = validate_stage_output("qa.security", result, json.dumps(result))
        assert valid is False

    def test_e2e_execute_pass(self):
        result = {"verdict": "PASS"}
        valid, err = validate_stage_output("e2e.execute", result, json.dumps(result))
        assert valid is True

    def test_deploy_prepare_pass(self):
        result = {"verdict": "PASS", "build_status": "success"}
        valid, err = validate_stage_output("deploy.prepare", result, json.dumps(result))
        assert valid is True

    def test_smoke_test_pass(self):
        result = {"verdict": "PASS"}
        valid, err = validate_stage_output("smoke.test", result, json.dumps(result))
        assert valid is True

    def test_empty_result_fails(self):
        valid, err = validate_stage_output("verify", {}, "{}")
        assert valid is False
        assert "Empty result" in err


class TestContractRulesRegistry:
    """Verify all contract rules are properly registered."""

    def test_all_contract_rules_have_valid_source_target(self):
        for rule in CONTRACT_RULES:
            assert rule.source, "Rule source cannot be empty"
            assert rule.target, "Rule target cannot be empty"
            assert callable(rule.validator)
            assert rule.on_fail in ("retry_source", "block", "warn_proceed")

    def test_blueprint_to_code_rule_exists(self):
        rules = [(r.source, r.target) for r in CONTRACT_RULES]
        assert ("impl-design", "impl-code") in rules

    def test_code_to_doc_update_rule_exists(self):
        rules = [(r.source, r.target) for r in CONTRACT_RULES]
        assert ("impl-code", "doc-update") in rules

    def test_verify_to_downstream_rules_exist(self):
        rules = [(r.source, r.target) for r in CONTRACT_RULES]
        verify_rules = [r for r in rules if r[0] == "verify"]
        assert len(verify_rules) >= 1


class TestContractGateEnsureDict:
    """_ensure_dict handles various output formats."""

    def test_dict_passthrough(self):
        from eng_loop.tools.contract_gate import _ensure_dict

        result = _ensure_dict({"key": "value"})
        assert result == {"key": "value"}

    def test_json_string_parsed(self):
        from eng_loop.tools.contract_gate import _ensure_dict

        result = _ensure_dict('{"verdict": "PASS"}')
        assert result == {"verdict": "PASS"}

    def test_plain_string_mention_only_has_no_verdict(self):
        # Substring mentions of FAIL/PASS are NOT a verdict — the old
        # `"FAIL" in value` fallback treated any mention as one (4.3.8).
        from eng_loop.tools.contract_gate import _ensure_dict

        assert "verdict" not in _ensure_dict("Something went wrong, FAIL")
        assert "verdict" not in _ensure_dict("All tests PASS")

    def test_plain_string_explicit_verdict_marker(self):
        from eng_loop.tools.contract_gate import _ensure_dict

        assert _ensure_dict("Verdict: FAIL — coverage gap")["verdict"] == "FAIL"
        assert _ensure_dict('verdict: "PASS"')["verdict"] == "PASS"

    def test_non_dict_non_string(self):
        from eng_loop.tools.contract_gate import _ensure_dict

        result = _ensure_dict(123)
        assert result == {}

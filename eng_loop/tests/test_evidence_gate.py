from __future__ import annotations

"""Tests for evidence gate validation across all stage types."""

from eng_loop.tools.evidence_gate import (
    parse_llm_response,
    should_retry_stage,
    validate_stage_output,
)

# ============================================================
# VALIDATE STAGE OUTPUT
# ============================================================


class TestValidateVerify:
    def test_verify_pass(self):
        result = {"verdict": "PASS", "per_ac_evidence": ["evidence1"], "gaps": []}
        valid, err = validate_stage_output("verify", result, str(result))
        assert valid is True
        assert err == ""

    def test_verify_fail_with_gaps(self):
        result = {"verdict": "FAIL", "gaps": ["gap1", "gap2"]}
        valid, _err = validate_stage_output("verify", result, str(result))
        assert valid is True

    def test_verify_fail_without_gaps(self):
        result = {"verdict": "FAIL", "gaps": []}
        valid, err = validate_stage_output("verify", result, str(result))
        assert valid is False
        assert "no gaps" in err

    def test_verify_invalid_verdict(self):
        result = {"verdict": "UNKNOWN"}
        valid, err = validate_stage_output("verify", result, str(result))
        assert valid is False
        assert "Invalid verdict" in err


class TestValidateE2E:
    def test_e2e_pass(self):
        result = {"verdict": "PASS", "test_results": ["passed"]}
        valid, _err = validate_stage_output("e2e.execute", result, str(result))
        assert valid is True

    def test_e2e_fail(self):
        result = {"verdict": "FAIL", "test_results": ["failed"]}
        valid, _err = validate_stage_output("e2e.execute", result, str(result))
        assert valid is True

    def test_e2e_invalid_verdict(self):
        result = {"verdict": "MAYBE"}
        valid, _err = validate_stage_output("e2e.execute", result, str(result))
        assert valid is False


class TestValidateQA:
    def test_qa_security_pass(self):
        result = {"verdict": "PASS", "findings": []}
        valid, _err = validate_stage_output("qa.security", result, str(result))
        assert valid is True

    def test_qa_api_contract_pass(self):
        result = {"verdict": "PASS", "findings": []}
        valid, _err = validate_stage_output("qa.api-contract", result, str(result))
        assert valid is True

    def test_qa_performance_pass(self):
        result = {"verdict": "PASS", "findings": []}
        valid, _err = validate_stage_output("qa.performance", result, str(result))
        assert valid is True

    def test_qa_invalid_verdict(self):
        result = {"verdict": "UNKNOWN"}
        valid, _err = validate_stage_output("qa.security", result, str(result))
        assert valid is False


class TestValidateImplDesign:
    def test_blueprint_with_tasks(self):
        result = {"blueprint": "A short bp", "tasks": ["task1", "task2"]}
        valid, _err = validate_stage_output("impl.design", result, str(result))
        assert valid is True

    def test_blueprint_short_no_tasks(self):
        result = {"blueprint": "short", "tasks": []}
        valid, err = validate_stage_output("impl.design", result, str(result))
        assert valid is False
        assert "no tasks" in err

    def test_blueprint_short_few_tasks(self):
        result = {"blueprint": "short", "tasks": ["task1"]}
        valid, err = validate_stage_output("impl.design", result, str(result))
        assert valid is False
        assert "too short" in err


class TestValidateImplCode:
    def test_impl_code_valid(self):
        result = {
            "implementation_summary": "Implemented the feature with full test coverage across all modules",
            "files_created": ["src/main.py"],
        }
        valid, _err = validate_stage_output("impl.code", result, str(result))
        assert valid is True

    def test_impl_code_short_summary(self):
        result = {
            "implementation_summary": "Short",
            "files_created": ["src/main.py"],
        }
        valid, err = validate_stage_output("impl.code", result, str(result))
        assert valid is False
        assert "too short" in err


class TestValidateInit:
    def test_init_valid(self):
        result = {"valid": True, "work_item_refined": "Refined item"}
        valid, _err = validate_stage_output("init", result, str(result))
        assert valid is True

    def test_init_refined_only(self):
        result = {"valid": False, "work_item_refined": "Refined item"}
        valid, _err = validate_stage_output("init", result, str(result))
        assert valid is True

    def test_init_neither(self):
        result = {"valid": False, "work_item_refined": ""}
        valid, _err = validate_stage_output("init", result, str(result))
        assert valid is False


class TestValidateInitIdeate:
    def test_ideation_with_tasks(self):
        result = {"decomposed_tasks": ["task1"], "ideation_results": ""}
        valid, _err = validate_stage_output("init.ideate", result, str(result))
        assert valid is True

    def test_ideation_with_content(self):
        result = {"decomposed_tasks": [], "ideation_results": "x" * 100}
        valid, _err = validate_stage_output("init.ideate", result, str(result))
        assert valid is True

    def test_ideation_empty(self):
        result = {"decomposed_tasks": [], "ideation_results": "", "raw_output": ""}
        valid, _err = validate_stage_output("init.ideate", result, str(result))
        assert valid is False


class TestValidateDeploy:
    def test_deploy_pass(self):
        result = {"verdict": "PASS", "build_status": "pass"}
        valid, _err = validate_stage_output("deploy.prepare", result, str(result))
        assert valid is True

    def test_deploy_fail(self):
        result = {"verdict": "FAIL", "build_status": "fail"}
        valid, _err = validate_stage_output("deploy.prepare", result, str(result))
        assert valid is True

    def test_deploy_invalid_verdict(self):
        result = {"verdict": "UNKNOWN"}
        valid, _err = validate_stage_output("deploy.prepare", result, str(result))
        assert valid is False


class TestValidateSmoke:
    def test_smoke_pass(self):
        result = {"verdict": "PASS", "critical_paths": []}
        valid, _err = validate_stage_output("smoke.test", result, str(result))
        assert valid is True

    def test_smoke_invalid_verdict(self):
        result = {"verdict": "UNKNOWN"}
        valid, _err = validate_stage_output("smoke.test", result, str(result))
        assert valid is False


class TestValidateEmptyResult:
    def test_empty_result(self):
        valid, err = validate_stage_output("verify", {}, "")
        assert valid is False
        assert "Empty result" in err


# ============================================================
# PARSE LLM RESPONSE
# ============================================================


class TestParseLLMResponse:
    def test_parse_valid_json(self):
        content = '{"verdict": "PASS", "complete": true}'
        result, err = parse_llm_response("verify", content)
        assert err == ""
        assert result["verdict"] == "PASS"

    def test_parse_markdown_json(self):
        content = '```json\n{"verdict": "PASS"}\n```'
        result, err = parse_llm_response("verify", content)
        assert err == ""
        assert result["verdict"] == "PASS"

    def test_parse_invalid_json(self):
        content = "This is not JSON at all"
        result, _err = parse_llm_response("verify", content)
        # extract_json fallback returns dict with raw_output, not error
        assert isinstance(result, dict)


# ============================================================
# SHOULD RETRY
# ============================================================


class TestShouldRetry:
    def test_retry_with_error_and_attempts_left(self):
        assert should_retry_stage("verify", {}, "some error", 1, 3) is True

    def test_no_retry_without_error(self):
        assert should_retry_stage("verify", {}, "", 1, 3) is False

    def test_no_retry_max_attempts_reached(self):
        assert should_retry_stage("verify", {}, "error", 3, 3) is False

    def test_retry_exactly_at_limit_minus_one(self):
        assert should_retry_stage("verify", {}, "error", 2, 3) is True

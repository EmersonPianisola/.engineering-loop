from __future__ import annotations

"""Tests for evidence gate validation across all stage types."""

from eng_loop.tools.evidence_gate import (
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

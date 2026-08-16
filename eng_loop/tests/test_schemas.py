from __future__ import annotations

"""Tests for Pydantic output schemas for all 26 stages."""

from eng_loop.schemas import (
    STAGE_SCHEMA,
    ArchOutput,
    DeployPrepareOutput,
    DesignOutput,
    DocDecisionsOutput,
    DocProjectOutput,
    DocUpdateOutput,
    E2eOutput,
    ImplCodeOutput,
    ImplDesignOutput,
    InitBddOutput,
    InitIdeateOutput,
    InitOutput,
    InitRefineOutput,
    PostOutput,
    QaOutput,
    SmokeTestOutput,
    VerifyOutput,
    get_schema,
)
from eng_loop.state import STAGE_ORDER

# ============================================================
# SCHEMA REGISTRY
# ============================================================


class TestStageSchemaRegistry:
    def test_all_stages_have_schema(self):
        for stage_id in STAGE_ORDER:
            assert stage_id in STAGE_SCHEMA, f"Missing schema for {stage_id}"

    def test_get_schema_returns_correct_type(self):
        assert get_schema("init") == InitOutput
        assert get_schema("verify") == VerifyOutput
        assert get_schema("post") == PostOutput

    def test_get_schema_unknown(self):
        assert get_schema("nonexistent") is None

    def test_schema_count(self):
        assert len(STAGE_SCHEMA) == len(STAGE_ORDER)


# ============================================================
# INDIVIDUAL SCHEMA VALIDATION
# ============================================================


class TestInitSchemas:
    def test_init_output_defaults(self):
        obj = InitOutput()
        assert obj.valid is True
        assert obj.work_item_refined == ""
        assert obj.estimated_files == 0

    def test_init_output_custom(self):
        obj = InitOutput(valid=False, work_item_refined="Refined", estimated_files=5)
        assert obj.valid is False
        assert obj.estimated_files == 5

    def test_init_ideate_output(self):
        obj = InitIdeateOutput(
            ideation_results="Ideas here",
            decomposed_tasks=["task1", "task2"],
        )
        assert len(obj.decomposed_tasks) == 2

    def test_init_bdd_output(self):
        obj = InitBddOutput(
            journey_map="Journey map",
            gherkin_scenarios=["Given..."],
        )
        assert len(obj.gherkin_scenarios) == 1

    def test_init_refine_output(self):
        obj = InitRefineOutput(
            refined_work_item="Spec",
            ready_for_architecture=True,
        )
        assert obj.ready_for_architecture is True


class TestDesignSchema:
    def test_design_output(self):
        obj = DesignOutput(
            design_output="Design doc",
            artifacts=["artifact1"],
            decisions=["AD-001: decision"],
        )
        assert obj.complete is True
        assert len(obj.decisions) == 1


class TestArchSchema:
    def test_arch_output(self):
        obj = ArchOutput(
            architecture_output="Architecture doc",
            critical_findings=["finding1"],
        )
        assert len(obj.critical_findings) == 1


class TestImplSchemas:
    def test_impl_design_output(self):
        obj = ImplDesignOutput(
            blueprint="Full blueprint",
            tasks=["task1"],
            file_structure=["src/main.py"],
        )
        assert len(obj.tasks) == 1

    def test_impl_code_output(self):
        obj = ImplCodeOutput(
            implementation_summary="Implemented feature with tests",
            files_created=["src/main.py", "tests/test_main.py"],
            tests_passed=True,
            diff="diff --git",
        )
        assert len(obj.files_created) == 2

    def test_doc_update_output(self):
        obj = DocUpdateOutput(files_updated=["README.md"])
        assert len(obj.files_updated) == 1


class TestVerifySchemas:
    def test_verify_output_pass(self):
        obj = VerifyOutput(
            verdict="PASS",
            per_ac_evidence=["AC1 -> file.py:10"],
            discrimination_sensor="pass",
        )
        assert obj.verdict == "PASS"

    def test_verify_output_fail(self):
        obj = VerifyOutput(
            verdict="FAIL",
            gaps=["Missing test for edge case"],
        )
        assert obj.verdict == "FAIL"
        assert len(obj.gaps) == 1

    def test_e2e_output(self):
        obj = E2eOutput(
            verdict="PASS",
            test_results=["Test 1: passed"],
            console_errors=0,
            network_errors=0,
        )
        assert obj.console_errors == 0


class TestQaSchema:
    def test_qa_output(self):
        obj = QaOutput(
            verdict="FAIL",
            findings=["Low severity issue"],
            critical_findings=["Critical: SQL injection"],
        )
        assert len(obj.critical_findings) == 1


class TestDeploySchemas:
    def test_deploy_prepare_output(self):
        obj = DeployPrepareOutput(
            build_status="pass",
            lint_status="pass",
            type_check_status="pass",
            verdict="PASS",
        )
        assert obj.verdict == "PASS"

    def test_smoke_test_output(self):
        obj = SmokeTestOutput(
            verdict="PASS",
            critical_paths=["Login works", "Checkout works"],
        )
        assert len(obj.critical_paths) == 2


class TestDocSchemas:
    def test_doc_decisions_output(self):
        obj = DocDecisionsOutput(
            decision_log="MADR format",
            decisions_count=3,
        )
        assert obj.decisions_count == 3

    def test_doc_project_output(self):
        obj = DocProjectOutput(
            readme="# README",
            setup_guide="Setup steps",
            architecture_overview="C4 diagram",
        )
        assert obj.readme == "# README"


class TestPostSchema:
    def test_post_output(self):
        obj = PostOutput(
            summary="All done",
            lessons_to_share=2,
            final_status="done",
        )
        assert obj.final_status == "done"

    def test_post_output_defaults(self):
        obj = PostOutput()
        assert obj.complete is True
        assert obj.final_status == "done"


# ============================================================
# SCHEMA SERIALIZE/DESERIALIZE
# ============================================================


class TestSchemaSerialization:
    def test_json_roundtrip(self):
        obj = VerifyOutput(verdict="PASS", gaps=["gap1"])
        json_str = obj.model_dump_json()
        parsed = VerifyOutput.model_validate_json(json_str)
        assert parsed.verdict == "PASS"
        assert parsed.gaps == ["gap1"]

    def test_dict_roundtrip(self):
        obj = ImplCodeOutput(
            implementation_summary="Done",
            files_created=["a.py"],
        )
        d = obj.model_dump()
        parsed = ImplCodeOutput(**d)
        assert parsed.files_created == ["a.py"]

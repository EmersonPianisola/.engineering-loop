from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# INIT stages
# ──────────────────────────────────────────────
class InitOutput(BaseModel):
    valid: bool = Field(default=True, description="Whether the work item is valid and ready for engineering")
    work_item_refined: str = Field(default="", description="Refined work item text")
    estimated_files: int = Field(default=0, description="Estimated number of files to modify")
    estimated_tasks: int = Field(default=0, description="Estimated number of tasks")
    notes: str = Field(default="", description="Observations about the work item")


class InitIdeateOutput(BaseModel):
    ideation_results: str = Field(default="", description="Structured ideation output from Party Mode")
    decomposed_tasks: list[str] = Field(default_factory=list, description="Decomposed tasks from ideation")
    ready_for_next: bool = Field(default=True, description="Whether ideation is complete")


class InitBddOutput(BaseModel):
    journey_map: str = Field(default="", description="User journey mapping output")
    gherkin_scenarios: list[str] = Field(default_factory=list, description="Gherkin scenarios")
    complete: bool = Field(default=True, description="Whether BDD mapping is complete")


class InitRefineOutput(BaseModel):
    refined_work_item: str = Field(default="", description="Engineering-ready specification")
    ready_for_architecture: bool = Field(default=True, description="Whether refinement is complete")


# ──────────────────────────────────────────────
# DESIGN stages
# ──────────────────────────────────────────────
class DesignOutput(BaseModel):
    design_output: str = Field(default="", description="Structured design output for this stage")
    artifacts: list[str] = Field(default_factory=list, description="Artifact descriptions")
    complete: bool = Field(default=True, description="Whether design stage is complete")
    decisions: list[str] = Field(default_factory=list, description="AD-NNN style decisions")


# ──────────────────────────────────────────────
# ARCHITECTURE stages
# ──────────────────────────────────────────────
class ArchOutput(BaseModel):
    architecture_output: str = Field(default="", description="Structured architecture output")
    complete: bool = Field(default=True, description="Whether architecture stage is complete")
    decisions: list[str] = Field(default_factory=list, description="AD-NNN style decisions")
    critical_findings: list[str] = Field(
        default_factory=list,
        description="Critical issues found during review (only for arch.review)",
    )


# ──────────────────────────────────────────────
# IMPLEMENTATION stages
# ──────────────────────────────────────────────
class ImplDesignOutput(BaseModel):
    blueprint: str = Field(default="", description="Full implementation blueprint document")
    tasks: list[str] = Field(default_factory=list, description="Implementation tasks")
    file_structure: list[str] = Field(default_factory=list, description="Files to create/modify")
    complete: bool = Field(default=True, description="Whether blueprint is complete")
    decisions: list[str] = Field(default_factory=list, description="AD-NNN decisions")


class ImplCodeOutput(BaseModel):
    implementation_summary: str = Field(default="", description="What was implemented")
    files_created: list[str] = Field(default_factory=list, description="List of files created/modified")
    tests_passed: bool = Field(default=True, description="Whether tests pass")
    complete: bool = Field(default=True, description="Whether implementation is complete")
    decisions: list[str] = Field(default_factory=list, description="AD-NNN decisions")
    diff: str = Field(default="", description="Git diff or summary of changes")


class DocUpdateOutput(BaseModel):
    files_updated: list[str] = Field(default_factory=list, description="Documentation files updated")
    complete: bool = Field(default=True, description="Whether doc update is complete")


# ──────────────────────────────────────────────
# VERIFICATION stages
# ──────────────────────────────────────────────
class VerifyOutput(BaseModel):
    verdict: str = Field(default="PASS", description="PASS or FAIL")
    per_ac_evidence: list[str] = Field(default_factory=list, description="AC -> file:line evidence")
    discrimination_sensor: str = Field(default="pass", description="Pass/fail for discrimination sensor")
    coverage_audit: str = Field(default="pass", description="Pass/fail for coverage audit")
    gaps: list[str] = Field(default_factory=list, description="Gaps found if FAIL")
    complete: bool = Field(default=True, description="Whether verification is complete")


class E2eOutput(BaseModel):
    verdict: str = Field(default="PASS", description="PASS or FAIL")
    test_results: list[str] = Field(default_factory=list, description="Test result lines")
    console_errors: int = Field(default=0, description="Number of console errors")
    network_errors: int = Field(default=0, description="Number of network errors")
    bdd_coverage: str = Field(default="", description="BDD->E2E coverage status")
    complete: bool = Field(default=True, description="Whether E2E is complete")


# ──────────────────────────────────────────────
# QA stages
# ──────────────────────────────────────────────
class QaOutput(BaseModel):
    verdict: str = Field(default="PASS", description="PASS or FAIL")
    findings: list[str] = Field(default_factory=list, description="QA findings")
    critical_findings: list[str] = Field(default_factory=list, description="Critical issues")
    complete: bool = Field(default=True, description="Whether QA is complete")


# ──────────────────────────────────────────────
# DEPLOY stages
# ──────────────────────────────────────────────
class DeployPrepareOutput(BaseModel):
    build_status: str = Field(default="pass", description="Build status: pass/fail")
    lint_status: str = Field(default="pass", description="Lint status: pass/fail")
    type_check_status: str = Field(default="pass", description="Type check status: pass/fail")
    verdict: str = Field(default="PASS", description="PASS or FAIL")
    errors: list[str] = Field(default_factory=list, description="Errors found")
    complete: bool = Field(default=True, description="Whether deploy prep is complete")


class SmokeTestOutput(BaseModel):
    verdict: str = Field(default="PASS", description="PASS or FAIL")
    critical_paths: list[str] = Field(default_factory=list, description="Critical path results")
    console_errors: int = Field(default=0, description="Number of console errors")
    network_errors: int = Field(default=0, description="Number of network errors")
    complete: bool = Field(default=True, description="Whether smoke test is complete")


# ──────────────────────────────────────────────
# DOCUMENTATION stages
# ──────────────────────────────────────────────
class DocDecisionsOutput(BaseModel):
    decision_log: str = Field(default="", description="MADR formatted decision log")
    decisions_count: int = Field(default=0, description="Number of decisions")
    complete: bool = Field(default=True, description="Whether consolidation is complete")


class DocProjectOutput(BaseModel):
    readme: str = Field(default="", description="README content")
    setup_guide: str = Field(default="", description="Setup guide content")
    architecture_overview: str = Field(default="", description="Architecture overview")
    user_manual: str = Field(default="", description="User manual content")
    complete: bool = Field(default=True, description="Whether documentation is complete")


# ──────────────────────────────────────────────
# POST stage
# ──────────────────────────────────────────────
class PostOutput(BaseModel):
    summary: str = Field(default="", description="Execution summary")
    lessons_to_share: int = Field(default=0, description="Number of lessons to share")
    final_status: str = Field(default="done", description="Final status")
    complete: bool = Field(default=True, description="Whether post-loop is complete")


# ──────────────────────────────────────────────
# Mappings: stage_id -> output schema
# ──────────────────────────────────────────────
STAGE_SCHEMA: dict[str, type[BaseModel]] = {
    "init": InitOutput,
    "init.ideate": InitIdeateOutput,
    "init.bdd": InitBddOutput,
    "init.refine": InitRefineOutput,
    "design.user-research": DesignOutput,
    "design.personas": DesignOutput,
    "design.info-arch": DesignOutput,
    "design.interaction": DesignOutput,
    "design.design-system": DesignOutput,
    "design.visual-design": DesignOutput,
    "arch.requirements": ArchOutput,
    "arch.solution": ArchOutput,
    "arch.review": ArchOutput,
    "impl.design": ImplDesignOutput,
    "impl.code": ImplCodeOutput,
    "doc.update": DocUpdateOutput,
    "verify": VerifyOutput,
    "e2e.execute": E2eOutput,
    "qa.security": QaOutput,
    "qa.api-contract": QaOutput,
    "qa.performance": QaOutput,
    "deploy.prepare": DeployPrepareOutput,
    "smoke.test": SmokeTestOutput,
    "doc.decisions": DocDecisionsOutput,
    "doc.project": DocProjectOutput,
    "post": PostOutput,
}


def get_schema(stage_id: str) -> type[BaseModel] | None:
    return STAGE_SCHEMA.get(stage_id)

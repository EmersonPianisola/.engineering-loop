from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ──────────────────────────────────────────────
# TOPOLOGY PROPOSAL — LLM proposes, Policy authorizes, Builder compiles
# ──────────────────────────────────────────────

# Allowed edge condition identifiers. The LLM may only reference these;
# the builder translates them to actual state predicates.
ALLOWED_CONDITIONS: set[str] = {
    # Stage lifecycle
    "stage_done",
    "stage_failed",
    "stage_blocked",
    # Complexity gates
    "complexity_at_least_medium",
    "complexity_at_least_large",
    "complexity_is_complex",
    "complexity_is_small",
    # Project context
    "is_ui_project",
    "not_ui_project",
    # Terminal
    "always",
}


class EdgeDefinition(BaseModel):
    """Declarative edge: source, target, and an allowed condition identifier."""
    model_config = ConfigDict(frozen=True)

    from_stage: str = Field(description="Source stage ID (e.g. 'init', 'impl.code')")
    to_stage: str = Field(description="Target stage ID or '__end__'")
    edge_type: Literal["fixed", "conditional", "loopback", "terminal"] = "fixed"
    condition: Literal[tuple(ALLOWED_CONDITIONS)] = "always"
    description: str = Field(default="", description="Human-readable edge description")


class PhaseGroup(BaseModel):
    """Logical grouping of stages for display and execution ordering."""
    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Phase label, e.g. 'INIT', 'IMPL', 'QA'")
    stages: tuple[str, ...] = Field(description="Stage IDs in this phase")


class ExecutionPolicy(BaseModel):
    """Runtime execution rules that apply to specific stages.
    Separated from topology so the architect doesn't need to redefine
    standard failure/retry behavior for every proposal.
    """
    model_config = ConfigDict(frozen=True)

    stage_id: str = Field(description="Stage this policy applies to")
    max_attempts: int = Field(default=3, ge=1, le=5)
    failure_route: str = Field(
        default="",
        description="Stage to route to on failure (empty = use default terminal)",
    )


class GraphTopologyProposal(BaseModel):
    """Complete topology proposal from the dynamic architect.

    This is a DECLARATIVE specification. The LLM says WHAT graph it wants,
    not HOW to execute it. The builder compiles this into an executable graph.

    Invariant: LLM proposes → Policy authorizes → Builder compiles → Runtime executes.
    """
    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(description="Unique identifier for this proposal")
    work_type: Literal["feature", "bugfix", "documentation", "operational"] = "feature"
    complexity: Literal["small", "medium", "large", "complex"] = "small"
    required_stages: tuple[str, ...] = Field(
        description="Stage IDs that must be included in the graph"
    )
    edges: tuple[EdgeDefinition, ...] = Field(
        description="Declarative edges between stages"
    )
    phase_groups: tuple[PhaseGroup, ...] = Field(
        default_factory=tuple,
        description="Logical phase grouping for display",
    )
    execution_policies: tuple[ExecutionPolicy, ...] = Field(
        default_factory=tuple,
        description="Per-stage execution policies (retry, failure routing)"
    )
    rationale: str = Field(
        description="Explanation of why this topology is optimal for the task"
    )

    @field_validator("required_stages")
    @classmethod
    def validate_stages_not_empty(cls, v):
        if not v:
            raise ValueError("required_stages must not be empty")
        ids = list(v)
        if len(ids) != len(set(ids)):
            raise ValueError("required_stages must not contain duplicates")
        return v

    @field_validator("edges")
    @classmethod
    def validate_edges_not_empty(cls, v):
        if not v:
            raise ValueError("edges must not be empty")
        return v

    @model_validator(mode="after")
    def validate_edge_references(self) -> GraphTopologyProposal:
        stage_set = set(self.required_stages)
        special = {"__end__", "__start__"}
        valid_targets = stage_set | special

        for edge in self.edges:
            if edge.from_stage not in stage_set and edge.from_stage not in special:
                raise ValueError(
                    f"Edge from_stage '{edge.from_stage}' not in required_stages"
                )
            if edge.to_stage not in valid_targets:
                raise ValueError(
                    f"Edge to_stage '{edge.to_stage}' not in required_stages or __end__"
                )
            # Self-loops only allowed for loopback type
            if edge.from_stage == edge.to_stage and edge.edge_type != "loopback":
                raise ValueError(
                    f"Self-loop on '{edge.from_stage}' requires edge_type='loopback'"
                )
        return self

    @model_validator(mode="after")
    def validate_phase_group_stages(self) -> GraphTopologyProposal:
        stage_set = set(self.required_stages)
        for pg in self.phase_groups:
            for s in pg.stages:
                if s not in stage_set:
                    raise ValueError(
                        f"Phase group '{pg.name}' references stage '{s}' not in required_stages"
                    )
        return self

    @model_validator(mode="after")
    def validate_policy_stages(self) -> GraphTopologyProposal:
        stage_set = set(self.required_stages)
        for pol in self.execution_policies:
            if pol.stage_id not in stage_set:
                raise ValueError(
                    f"Execution policy references stage '{pol.stage_id}' not in required_stages"
                )
            if pol.failure_route and pol.failure_route not in stage_set:
                raise ValueError(
                    f"Execution policy failure_route '{pol.failure_route}' not in required_stages"
                )
        return self


class AuthorizedGraphTopology(BaseModel):
    """Policy-authorized version of a topology proposal. Immutable and safe to compile."""
    model_config = ConfigDict(frozen=True)

    plan_id: str
    authorized_stages: tuple[str, ...]
    authorized_edges: tuple[EdgeDefinition, ...]
    phase_groups: tuple[PhaseGroup, ...]
    execution_policies: tuple[ExecutionPolicy, ...]
    rationale: str
    policy_notes: str = Field(default="", description="Notes from policy validation")


# ──────────────────────────────────────────────
# DYNAMIC NODE ORCHESTRATION (V1.3) — Runtime augmentation
# ──────────────────────────────────────────────


class TestsPassPayload(BaseModel):
    __test__ = False
    model_config = ConfigDict(frozen=True)
    suite: Literal["unit", "integration", "e2e"] = "unit"
    command: str = ""


class FilesExistPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    paths: tuple[str, ...] = Field(description="Relative paths that must exist")


class SymbolPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    symbol: str = Field(description="Regex or symbol to search for")
    target_file: str = Field(description="Relative file path to search in")


class ValidationRule(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["tests_pass", "files_exist", "contains_symbol"]
    payload: TestsPassPayload | FilesExistPayload | SymbolPayload


class DynamicStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str = Field(description="Immutable unique identifier, e.g. 'db-migration-step'")
    role_description: str = Field(description="Cognitive agent role for this step")
    requested_capabilities: tuple[str, ...] = Field(default_factory=tuple)
    validation_rules: tuple[ValidationRule, ...] = Field(default_factory=tuple)
    max_attempts: int = Field(default=3, ge=1, le=5, description="Max attempts (1 execution + retries)")

    @field_validator("step_id")
    @classmethod
    def validate_step_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]{2,63}$", v):
            raise ValueError(f"step_id '{v}' must match ^[a-z0-9][a-z0-9-]{{2,63}}$")
        return v


class DynamicBlueprintProposal(BaseModel):
    model_config = ConfigDict(frozen=True)
    plan_id: str
    trigger: Literal["none", "augment"] = "none"
    proposed_complexity: Literal["standard", "adaptive", "restricted"] = "standard"
    steps: tuple[DynamicStep, ...] = Field(default_factory=tuple)
    rationale: str

    @field_validator("steps", mode="before")
    @classmethod
    def coerce_steps_to_tuple(cls, v):
        if v is None:
            return ()
        if isinstance(v, list):
            return tuple(v)
        if isinstance(v, tuple):
            return v
        return (v,)

    @model_validator(mode="after")
    def validate_trigger_consistency(self) -> DynamicBlueprintProposal:
        if self.trigger == "augment" and not self.steps:
            raise ValueError("Trigger 'augment' requires at least one dynamic step.")
        if self.trigger == "none" and self.steps:
            raise ValueError("Trigger 'none' cannot contain dynamic steps.")
        return self


class DynamicBlueprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str
    trigger: Literal["none", "augment"]
    authorized_complexity: Literal["standard", "adaptive", "restricted"]
    steps: tuple[DynamicStep, ...]
    rationale: str

    @field_validator("steps")
    @classmethod
    def validate_unique_steps(cls, v: tuple[DynamicStep, ...]) -> tuple[DynamicStep, ...]:
        ids = [s.step_id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("All step_ids within a DynamicBlueprint must be unique.")
        if len(v) > 5:
            raise ValueError("DynamicBlueprint exceeds MAX_DYNAMIC_STEPS (5).")
        return v


class DynamicAuditEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str
    step_id: str
    attempt: int
    status: Literal["success", "failed"]
    started_at: float
    finished_at: float
    error: str | None = None


class DynamicRuntime(BaseModel):
    cursor: int = Field(default=0, ge=0)
    attempts: dict[str, int] = Field(default_factory=dict)
    completed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "failed", "blocked"] = "pending"
    step_audit: list[DynamicAuditEntry] = Field(default_factory=list)

    def validate_invariants(self, total_steps: int) -> None:
        if not (0 <= self.cursor <= total_steps):
            raise ValueError(f"Cursor {self.cursor} out of bounds [0, {total_steps}]")
        if set(self.completed).intersection(set(self.failed)):
            raise ValueError("Overlap between completed and failed steps")


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


def get_topology_proposal_schema() -> type[BaseModel]:
    return GraphTopologyProposal

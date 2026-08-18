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
    required_stages: tuple[str, ...] = Field(description="Stage IDs that must be included in the graph")
    edges: tuple[EdgeDefinition, ...] = Field(description="Declarative edges between stages")
    phase_groups: tuple[PhaseGroup, ...] = Field(
        default_factory=tuple,
        description="Logical phase grouping for display",
    )
    execution_policies: tuple[ExecutionPolicy, ...] = Field(
        default_factory=tuple, description="Per-stage execution policies (retry, failure routing)"
    )
    rationale: str = Field(description="Explanation of why this topology is optimal for the task")

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
    def validate_edges(cls, v):
        if not v:
            raise ValueError("edges must not be empty")
        # The LLM should only propose happy-path edges.
        # Loopback and terminal edges are injected automatically by the framework.
        for edge in v:
            if edge.edge_type == "loopback":
                raise ValueError(
                    "Loopback edges are not allowed in proposals. "
                    "Failure routing is injected automatically by the framework."
                )
            if edge.edge_type == "terminal":
                raise ValueError(
                    "Terminal edges are not allowed in proposals. "
                    "Blocked routing is injected automatically by the framework."
                )
        return v

    @model_validator(mode="after")
    def validate_edge_references(self) -> GraphTopologyProposal:
        stage_set = set(self.required_stages)
        special = {"__end__", "__start__"}
        valid_targets = stage_set | special

        for edge in self.edges:
            if edge.from_stage not in stage_set and edge.from_stage not in special:
                raise ValueError(f"Edge from_stage '{edge.from_stage}' not in required_stages")
            if edge.to_stage not in valid_targets:
                raise ValueError(f"Edge to_stage '{edge.to_stage}' not in required_stages or __end__")
            # Self-loops only allowed for loopback type
            if edge.from_stage == edge.to_stage and edge.edge_type != "loopback":
                raise ValueError(f"Self-loop on '{edge.from_stage}' requires edge_type='loopback'")
        return self

    @model_validator(mode="after")
    def validate_phase_group_stages(self) -> GraphTopologyProposal:
        stage_set = set(self.required_stages)
        for pg in self.phase_groups:
            for s in pg.stages:
                if s not in stage_set:
                    raise ValueError(f"Phase group '{pg.name}' references stage '{s}' not in required_stages")
        return self

    @model_validator(mode="after")
    def validate_policy_stages(self) -> GraphTopologyProposal:
        stage_set = set(self.required_stages)
        for pol in self.execution_policies:
            if pol.stage_id not in stage_set:
                raise ValueError(f"Execution policy references stage '{pol.stage_id}' not in required_stages")
            if pol.failure_route and pol.failure_route not in stage_set:
                raise ValueError(f"Execution policy failure_route '{pol.failure_route}' not in required_stages")
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
# QA stages — Evidence-based, trinary state (PASS/FAIL/BLOCKED)
# ──────────────────────────────────────────────
QA_VERDICT = Literal["PASS", "FAIL", "BLOCKED"]
QA_SEVERITY = Literal["critical", "high", "medium", "low", "info"]
QA_TYPE = Literal["deterministic", "heuristic"]


class QAEvidence(BaseModel):
    """Verifiable evidence produced by a QA stage. Prevents hallucinated PASS."""

    model_config = ConfigDict(frozen=True)

    files_analyzed: int = Field(default=0, description="Number of source files examined")
    execution_command: str = Field(default="", description="Command that was executed (if applicable)")
    exit_code: int = Field(default=-1, description="Exit code of execution (-1 if not applicable)")
    artifacts: list[str] = Field(default_factory=list, description="Paths to produced artifacts")
    metrics: dict[str, float] = Field(default_factory=dict, description="Quantitative measurements")


class QAExecution(BaseModel):
    """Execution metadata for observability and audit."""

    model_config = ConfigDict(frozen=True)

    started_at: float = Field(default=0.0, description="Unix timestamp of stage start")
    completed_at: float = Field(default=0.0, description="Unix timestamp of stage end")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    tool_calls: int = Field(default=0, description="Number of tool calls made")


class QAFinding(BaseModel):
    """A single QA finding with severity classification."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(default="", description="Category, e.g. 'xss', 'wcag', 'coverage'")
    severity: QA_SEVERITY = Field(default="info", description="Severity level")
    description: str = Field(default="", description="What was found")
    location: str = Field(default="", description="file:line or component reference")
    recommendation: str = Field(default="", description="Suggested fix")


class QAResult(BaseModel):
    """Common envelope for all QA stage outputs.

    Deterministic stages (static, unit, integration, security, performance):
    verdict is PASS/FAIL/BLOCKED based on objective criteria.

    Heuristic stages (human.flow, human.ux):
    verdict includes confidence score and friction_score for policy evaluation.
    """

    model_config = ConfigDict(frozen=True)

    stage_id: str = Field(default="", description="Stage that produced this result")
    verdict: QA_VERDICT = Field(default="PASS", description="PASS, FAIL, or BLOCKED")
    qa_type: QA_TYPE = Field(default="deterministic", description="deterministic or heuristic")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this verdict (0-1)")
    severity: QA_SEVERITY = Field(default="info", description="Highest severity finding")
    evidence: QAEvidence = Field(default_factory=QAEvidence, description="Verifiable evidence")
    findings: list[QAFinding] = Field(default_factory=list, description="All findings")
    execution: QAExecution = Field(default_factory=QAExecution, description="Execution metadata")
    friction_score: float = Field(
        default=-1.0,
        ge=-1.0,
        le=10.0,
        description="Friction score 0-10 (heuristic stages only, -1 if not applicable)",
    )
    blocked_reason: str = Field(
        default="",
        description="Reason for BLOCKED verdict (infrastructure, not-applicable, etc.)",
    )
    complete: bool = Field(default=True, description="Whether QA stage completed processing")


# Legacy compatibility — kept for existing stages (qa.security, qa.api-contract, qa.performance)
class QaOutput(BaseModel):
    verdict: str = Field(default="PASS", description="PASS, FAIL, or BLOCKED")
    findings: list[str] = Field(default_factory=list, description="QA findings")
    critical_findings: list[str] = Field(default_factory=list, description="Critical issues")
    complete: bool = Field(default=True, description="Whether QA is complete")


# ──────────────────────────────────────────────
# QA: Static Analysis
# ──────────────────────────────────────────────
class StaticOutput(BaseModel):
    """Static analysis: lint, type-check, cyclomatic complexity."""

    model_config = ConfigDict(frozen=True)

    verdict: QA_VERDICT = Field(default="PASS")
    qa_type: QA_TYPE = "deterministic"
    confidence: float = Field(default=1.0)
    severity: QA_SEVERITY = Field(default="info")
    lint_errors: list[str] = Field(default_factory=list, description="Linting errors found")
    type_errors: list[str] = Field(default_factory=list, description="Type checking errors")
    cyclomatic_score: int = Field(default=0, description="Average cyclomatic complexity")
    hotspots: list[str] = Field(default_factory=list, description="Functions with high complexity")
    files_analyzed: int = Field(default=0, description="Number of files analyzed")
    execution_command: str = Field(default="", description="Lint/type-check command executed")
    exit_code: int = Field(default=-1, description="Exit code from tool")
    findings: list[QAFinding] = Field(default_factory=list)
    evidence: QAEvidence = Field(default_factory=QAEvidence)
    execution: QAExecution = Field(default_factory=QAExecution)
    complete: bool = Field(default=True)


# ──────────────────────────────────────────────
# QA: Unit Testing
# ──────────────────────────────────────────────
class UnitOutput(BaseModel):
    """Unit test generation and execution results."""

    model_config = ConfigDict(frozen=True)

    verdict: QA_VERDICT = Field(default="PASS")
    qa_type: QA_TYPE = "deterministic"
    confidence: float = Field(default=1.0)
    severity: QA_SEVERITY = Field(default="info")
    test_count: int = Field(default=0, description="Total number of tests defined")
    tests_executed: int = Field(default=0, description="Number of tests actually executed")
    passed: int = Field(default=0, description="Number of passing tests")
    failed: int = Field(default=0, description="Number of failing tests")
    coverage: float = Field(default=0.0, description="Code coverage percentage (0-100)")
    failed_tests: list[str] = Field(default_factory=list, description="Names of failing tests")
    test_files: list[str] = Field(default_factory=list, description="Test files created/modified")
    execution_command: str = Field(default="", description="Test runner command")
    exit_code: int = Field(default=-1, description="Exit code from test runner")
    findings: list[QAFinding] = Field(default_factory=list)
    evidence: QAEvidence = Field(default_factory=QAEvidence)
    execution: QAExecution = Field(default_factory=QAExecution)
    complete: bool = Field(default=True)

    @field_validator("tests_executed")
    @classmethod
    def validate_execution_consistency(cls, v: int, info) -> int:
        if "data" in info.context or hasattr(info, "data"):
            test_count = info.data.get("test_count", 0) if hasattr(info, "data") and isinstance(info.data, dict) else 0
            if v > test_count > 0:
                raise ValueError(f"tests_executed ({v}) cannot exceed test_count ({test_count})")
        return v


# ──────────────────────────────────────────────
# QA: Integration Testing
# ──────────────────────────────────────────────
class IntegrationOutput(BaseModel):
    """Integration testing: API contracts + component communication."""

    model_config = ConfigDict(frozen=True)

    verdict: QA_VERDICT = Field(default="PASS")
    qa_type: QA_TYPE = "deterministic"
    confidence: float = Field(default=1.0)
    severity: QA_SEVERITY = Field(default="info")
    endpoints_tested: list[str] = Field(default_factory=list, description="API endpoints validated")
    components_tested: list[str] = Field(default_factory=list, description="Component interfaces tested")
    contract_violations: list[str] = Field(default_factory=list, description="OpenAPI/contract violations")
    component_gaps: list[str] = Field(default_factory=list, description="Missing integration points")
    tests_executed: int = Field(default=0, description="Number of integration tests run")
    failed: int = Field(default=0, description="Number of failing integration tests")
    artifacts: list[str] = Field(default_factory=list, description="Produced artifacts")
    findings: list[QAFinding] = Field(default_factory=list)
    evidence: QAEvidence = Field(default_factory=QAEvidence)
    execution: QAExecution = Field(default_factory=QAExecution)
    complete: bool = Field(default=True)


# ──────────────────────────────────────────────
# QA: Human Flow — Persona-based heuristic simulation
# ──────────────────────────────────────────────
class HumanFlowOutput(BaseModel):
    """Persona-based heuristic navigation simulation.

    The agent assumes a persona (e.g., novice user) and attempts to complete
    tasks in the system, reporting friction points, jargon, dead ends, and
    unexpected states.
    """

    model_config = ConfigDict(frozen=True)

    verdict: QA_VERDICT = Field(default="PASS")
    qa_type: QA_TYPE = "heuristic"
    confidence: float = Field(default=0.8, description="Confidence in friction assessment (0-1)")
    severity: QA_SEVERITY = Field(default="info")
    persona_name: str = Field(default="", description="Persona assumed for simulation")
    scenario: str = Field(default="", description="Task scenario attempted")
    friction_score: float = Field(default=0.0, ge=0.0, le=10.0, description="Friction score 0-10")
    confusion_points: list[str] = Field(default_factory=list, description="Where user would get confused")
    jargon_found: list[str] = Field(default_factory=list, description="Technical jargon exposed to user")
    dead_ends: list[str] = Field(default_factory=list, description="Flows that lead nowhere")
    unexpected_states: list[str] = Field(default_factory=list, description="Surprising system states")
    recommendations: list[str] = Field(default_factory=list, description="UX improvement suggestions")
    findings: list[QAFinding] = Field(default_factory=list)
    evidence: QAEvidence = Field(default_factory=QAEvidence)
    execution: QAExecution = Field(default_factory=QAExecution)
    complete: bool = Field(default=True)


# ──────────────────────────────────────────────
# QA: Human UX — WCAG audit + cognitive walkthrough
# ──────────────────────────────────────────────
class HumanUxOutput(BaseModel):
    """WCAG accessibility audit + cognitive walkthrough.

    Evaluates cognitive load, step bloat, navigation consistency, and
    accessibility compliance (WCAG 2.1 AA).
    """

    model_config = ConfigDict(frozen=True)

    verdict: QA_VERDICT = Field(default="PASS")
    qa_type: QA_TYPE = "heuristic"
    confidence: float = Field(default=0.8, description="Confidence in UX assessment (0-1)")
    severity: QA_SEVERITY = Field(default="info")
    friction_score: float = Field(default=0.0, ge=0.0, le=10.0, description="Friction score 0-10")
    wcag_violations: list[str] = Field(default_factory=list, description="WCAG 2.1 AA violations")
    cognitive_load: str = Field(default="low", description="Cognitive load assessment: low/medium/high")
    step_bloat: int = Field(default=0, description="Number of unnecessary steps in critical flows")
    navigation_issues: list[str] = Field(default_factory=list, description="Navigation problems")
    accessibility_issues: list[str] = Field(default_factory=list, description="Accessibility concerns")
    recommendations: list[str] = Field(default_factory=list, description="UX improvement suggestions")
    findings: list[QAFinding] = Field(default_factory=list)
    evidence: QAEvidence = Field(default_factory=QAEvidence)
    execution: QAExecution = Field(default_factory=QAExecution)
    complete: bool = Field(default=True)


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
# ESSENCE SIDECAR — Four Lenses validation
# ──────────────────────────────────────────────
class EssenceSubjectiveTerm(BaseModel):
    """A subjective term found by Lens 1."""

    model_config = ConfigDict(frozen=True)

    term: str = Field(default="", description="The subjective term")
    context: str = Field(default="", description="Where the term appears")
    interpretations: list[str] = Field(
        default_factory=list, description="Proposed concrete interpretations"
    )


class EssenceHiddenAssumption(BaseModel):
    """A hidden assumption found by Lens 2."""

    model_config = ConfigDict(frozen=True)

    assumption: str = Field(default="", description="The unstated assumption")
    risk: str = Field(default="", description="What could go wrong if assumption is false")
    severity: Literal["high", "medium", "low"] = Field(default="low")


class EssenceLiteralTrap(BaseModel):
    """A literal trap found by Lens 3."""

    model_config = ConfigDict(frozen=True)

    phrasing: str = Field(default="", description="The ambiguous phrasing")
    ambiguity: str = Field(default="", description="Why it can be misinterpreted")
    likely_misinterpretation: str = Field(default="", description="What an LLM might do wrong")


class EssenceConflict(BaseModel):
    """A conflicting priority found by Lens 4."""

    model_config = ConfigDict(frozen=True)

    goal_a: str = Field(default="", description="First competing goal")
    goal_b: str = Field(default="", description="Second competing goal")
    tension: str = Field(default="", description="Why they conflict")
    requires_user_resolution: bool = Field(default=True)


class EssenceOutput(BaseModel):
    """Structured output from Essence Four Lenses validation."""

    lens_1_subjective_terms: list[EssenceSubjectiveTerm] = Field(default_factory=list)
    lens_2_hidden_assumptions: list[EssenceHiddenAssumption] = Field(default_factory=list)
    lens_3_literal_traps: list[EssenceLiteralTrap] = Field(default_factory=list)
    lens_4_conflicts: list[EssenceConflict] = Field(default_factory=list)
    clean: bool = Field(default=False, description="True if all four lenses found nothing")
    adjustments: list[str] = Field(
        default_factory=list, description="Lens 1-3 adjustments applied inline"
    )
    summary: str = Field(default="", description="One-line summary of findings")


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
    "qa.api-contract": QaOutput,  # DEPRECATED: alias for qa.integration
    "qa.performance": QaOutput,
    "qa.static": StaticOutput,
    "qa.unit": UnitOutput,
    "qa.integration": IntegrationOutput,
    "qa.human.flow": HumanFlowOutput,
    "qa.human.ux": HumanUxOutput,
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

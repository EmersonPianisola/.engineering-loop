from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PipelineStatus(str, Enum):
    """Mutually exclusive pipeline-level execution status.

    Invariants:
    - COMPLETED requires: no active nodes, no pending questions, no failures.
    - WAITING_FOR_INPUT requires: no active nodes, pending questions > 0.
    - FAILED requires: a fatal error exists.
    - RUNNING requires: at least one active node.
    """

    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_INPUT = "waiting_for_input"
    RESUMING = "resuming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeVisualStatus(str, Enum):
    """Visual status of a graph node.

    Symbols are decided by the renderer, not here.
    """

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# ─── Leaf types ────────────────────────────────────────────────────


@dataclass
class AttemptRecord:
    """One attempt within a node execution."""

    attempt_num: int
    duration_ms: int
    result: str  # "success" | "retry" | "failed"


@dataclass
class NodeExecution:
    """One execution of a node (may contain multiple attempts)."""

    execution_id: str
    attempts: list[AttemptRecord] = field(default_factory=list)
    start_ms: float = 0.0
    end_ms: float | None = None
    result: str = "pending"


@dataclass
class GraphNodeInfo:
    """A node in the graph with execution history."""

    id: str
    phase: str = ""
    is_container: bool = False
    children: list[str] = field(default_factory=list)
    visual_status: NodeVisualStatus = NodeVisualStatus.PENDING
    executions: list[NodeExecution] = field(default_factory=list)
    total_duration_ms: int = 0
    error_message: str | None = None
    tool_count: int = 0


@dataclass
class PipelineMetrics:
    """Authoritative metrics derived from graph state.

    The denominator (total_nodes) is fixed for the graph and never
    affected by retries.
    """

    total_nodes: int = 0
    completed_nodes: int = 0
    running_nodes: int = 0
    failed_nodes: int = 0
    pending_nodes: int = 0
    total_executions: int = 0
    total_attempts: int = 0
    retries: int = 0


@dataclass
class ProgressInfo:
    """Progress as completed/total. Denominator never changes."""

    current: int = 0
    total: int = 0

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return self.current / self.total

    @property
    def percentage(self) -> int:
        if self.total <= 0:
            return 0
        return int(100 * self.current / self.total)


@dataclass
class CheckpointInfo:
    """Checkpoint snapshot for resume semantics."""

    completed_nodes: list[str] = field(default_factory=list)
    active_node: str | None = None
    waiting_reason: str | None = None
    state_version: int = 0
    graph_id: str = ""


@dataclass
class EssenceQuestion:
    """A deduplicated clarification question."""

    id: str
    severity: str  # "low" | "medium" | "high"
    question: str
    finding_summary: str = ""
    options: list[str] = field(default_factory=list)
    input_type: str = "text"  # "text" | "choice"


@dataclass
class EssenceGateInfo:
    """State of the Essence Gate when paused."""

    stage: str = ""
    questions: list[EssenceQuestion] = field(default_factory=list)
    resolved_findings: list[str] = field(default_factory=list)
    clarification_count: int = 0


@dataclass
class DiagnosticEntry:
    """A diagnostic message with severity."""

    severity: str  # "INFO" | "WARN" | "ERROR" | "FATAL"
    message: str
    node_id: str | None = None
    timestamp: float = 0.0


@dataclass
class ResumeInfo:
    """Information displayed when resuming after Essence Gate."""

    clarifications_applied: int = 0
    checkpoint_stage: str = ""
    invalidated_stages: list[str] = field(default_factory=list)
    preserved_stages: list[str] = field(default_factory=list)


@dataclass
class ContextBudgetInfo:
    """Context budget state for the current LLM call and stage history.

    Two metrics:
    A. Per-call budget — safety metric, resets per call.
    B. Per-stage history — behavioral metric, tracks accumulation.
    """

    model_name: str = ""
    context_window: int = 0
    # Current call budget
    used_tokens: int = 0
    remaining_tokens: int = 0
    safe_remaining: int = 0
    pressure: str = "safe"  # safe / watch / pressure / exhausted
    # Breakdown
    system_tokens: int = 0
    stage_tokens: int = 0
    conversation_tokens: int = 0
    tool_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    # Tracking
    tool_calls: int = 0
    call_number: int = 0
    # Compaction
    compaction_suggested: bool = False
    compaction_count: int = 0
    tokens_compacted: int = 0
    # Tokenizer
    tokenizer_provider: str = ""
    tokenizer_accuracy: str = "estimated"
    # Stage history (per-call records)
    stage_history: list[dict] = field(default_factory=list)

    @property
    def usage_percentage(self) -> float:
        if self.context_window <= 0:
            return 0.0
        return self.used_tokens / self.context_window * 100

    @property
    def is_critical(self) -> bool:
        return self.pressure in ("pressure", "exhausted")


# ─── Aggregate root ────────────────────────────────────────────────


@dataclass
class ExecutionViewModel:
    """Presentation-agnostic view model for the execution pipeline.

    Contains no ANSI codes, terminal formatting, layout decisions, or
    renderer-specific semantics. The renderer decides how to represent
    each status (e.g., whether RUNNING becomes '●' or '[ACTIVE]').
    """

    # Pipeline-level
    pipeline_status: PipelineStatus = PipelineStatus.PLANNING
    work_item: str = ""
    graph_id: str = ""

    # Planning (separated from graph nodes)
    planning_node_id: str | None = None
    planning_status: NodeVisualStatus = NodeVisualStatus.PENDING

    # Graph topology
    nodes: dict[str, GraphNodeInfo] = field(default_factory=dict)
    phases: dict[str, list[str]] = field(default_factory=dict)

    # Current execution
    current_node_id: str | None = None
    current_attempt: int = 0
    current_elapsed_ms: int = 0
    current_tool_count: int = 0

    # Metrics (authoritative, derived from state)
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    progress: ProgressInfo = field(default_factory=ProgressInfo)

    # History (ordered list of completed nodes)
    history: list[GraphNodeInfo] = field(default_factory=list)

    # Checkpoint
    checkpoint: CheckpointInfo | None = None

    # Essence Gate
    essence_gate: EssenceGateInfo | None = None

    # Resume
    resume_info: ResumeInfo | None = None

    # Diagnostics
    diagnostics: list[DiagnosticEntry] = field(default_factory=list)

    # Context Budget
    context_budget: ContextBudgetInfo | None = None

    # Timing
    total_elapsed_ms: int = 0

    # ─── Invariant enforcement ───────────────────────────────────

    def assert_consistent(self) -> list[str]:
        """Return list of violated invariants. Empty list means consistent."""
        violations: list[str] = []

        m = self.metrics

        # completed <= total
        if m.completed_nodes > m.total_nodes:
            violations.append(f"completed_nodes ({m.completed_nodes}) > total_nodes ({m.total_nodes})")

        # progress.current <= progress.total
        if self.progress.current > self.progress.total:
            violations.append(f"progress.current ({self.progress.current}) > progress.total ({self.progress.total})")

        # progress.denominator == total_nodes
        if self.progress.total != m.total_nodes:
            violations.append(f"progress.total ({self.progress.total}) != metrics.total_nodes ({m.total_nodes})")

        # COMPLETED invariants
        if self.pipeline_status == PipelineStatus.COMPLETED:
            if self.essence_gate and len(self.essence_gate.questions) > 0:
                violations.append("COMPLETED with pending essence questions")
            if m.running_nodes > 0:
                violations.append("COMPLETED with active nodes")
            if m.failed_nodes > 0:
                violations.append("COMPLETED with failed nodes")

        # WAITING_FOR_INPUT invariants
        if self.pipeline_status == PipelineStatus.WAITING_FOR_INPUT:
            if not self.essence_gate or not self.essence_gate.questions:
                violations.append("WAITING_FOR_INPUT without pending questions")
            if m.running_nodes > 0:
                violations.append("WAITING_FOR_INPUT with active nodes")

        # FAILED invariant
        if self.pipeline_status == PipelineStatus.FAILED:
            has_fatal = any(d.severity == "FATAL" for d in self.diagnostics) or m.failed_nodes > 0
            if not has_fatal:
                violations.append("FAILED without fatal error or failed nodes")

        # RUNNING invariant
        if self.pipeline_status == PipelineStatus.RUNNING:
            if m.running_nodes < 1:
                violations.append("RUNNING with no active nodes")

        # No simultaneous COMPLETED + WAITING_FOR_INPUT
        # (enforced by enum being mutually exclusive, but check derived state)
        if m.completed_nodes == m.total_nodes and m.total_nodes > 0:
            if self.essence_gate and len(self.essence_gate.questions) > 0:
                if self.pipeline_status != PipelineStatus.WAITING_FOR_INPUT:
                    violations.append("All nodes completed but gate waiting — status should be WAITING_FOR_INPUT")

        return violations

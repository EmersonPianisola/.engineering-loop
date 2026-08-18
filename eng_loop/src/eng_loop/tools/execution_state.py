from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from dataclasses import replace as dc_replace
from enum import Enum
from typing import Any

# ─── Status Enums ─────────────────────────────────────────────────────


class ExecutionStatus(Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_INPUT = "waiting_for_input"
    RESUMING = "resuming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(Enum):
    LOCKED = "locked"
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    CACHED = "cached"
    SKIPPED = "skipped"
    FAILED = "failed"


class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(Enum):
    THINKING = "thinking"
    READING = "reading"
    WRITING = "writing"
    EDITING = "editing"
    BASHING = "bashing"
    SEARCHING = "searching"
    GLOBING = "globing"
    GRIPPING = "gripping"
    IDLE = "idle"


# ─── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class ResourceTracker:
    attempts: int = 0
    tokens: TokenUsage = field(default_factory=TokenUsage)
    context_tokens: int = 0
    gold_spent: float = 0.0


@dataclass
class NodeExecution:
    execution_id: str
    node_name: str
    attempt_number: int
    start_time: float
    end_time: float | None = None
    status: NodeStatus = NodeStatus.ACTIVE
    resources: ResourceTracker = field(default_factory=ResourceTracker)
    last_action: str | None = None
    action_type: str | None = None
    thinking_buffer: str = ""
    tool_count: int = 0


@dataclass(frozen=True)
class PartyMemberSnapshot:
    node_name: str
    role: str
    icon: str
    color: str
    attempt: int
    attempts_max: int
    status: str
    duration_seconds: float
    stamina_current: int
    mana_current: int
    mana_max: int
    last_action: str
    threat_level: str
    thinking_preview: str = ""
    tool_count: int = 0
    phase_name: str = ""


@dataclass(frozen=True)
class TopologyNode:
    node_name: str
    phase: str
    status: str
    duration_seconds: float | None = None


@dataclass(frozen=True)
class QuestSummary:
    quest_id: str
    title: str
    status: str
    elapsed_seconds: float
    gold_spent: float
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    total_attempts: int
    total_retries: int
    total_tokens_input: int
    total_tokens_output: int
    total_tokens_cached: int
    bottleneck_node: str | None = None
    bottleneck_attempts: int = 0
    mvp_node: str | None = None


@dataclass(frozen=True)
class NarrativeEvent:
    timestamp: float
    icon: str
    role: str
    node_name: str
    action_type: str
    description: str
    color: str = "white"


@dataclass(frozen=True)
class CommandHistoryEntry:
    """Single command history entry for HUD display."""

    tool_name: str
    target: str
    count: int
    is_intercepted: bool = False


@dataclass(frozen=True)
class HUDSnapshot:
    quest_id: str
    quest_title: str
    quest_status: str
    elapsed_seconds: float
    gold_spent: float
    topology: list[TopologyNode]
    party: list[PartyMemberSnapshot]
    narrative: list[NarrativeEvent]
    command_history: list[CommandHistoryEntry] = ()
    quest_summary: QuestSummary | None = None
    wall_clock_ref: float = 0.0
    monotonic_ref: float = 0.0
    is_paused: bool = False
    step_mode: bool = False


# ─── Events ───────────────────────────────────────────────────────────


@dataclass
class NodeStartedEvent:
    node_name: str
    execution_id: str
    attempt_number: int
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class NodeCompletedEvent:
    node_name: str
    execution_id: str
    status: NodeStatus
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class QuestCompletedEvent:
    reason: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class QuestFailedEvent:
    reason: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class QuestCancelledEvent:
    reason: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class AgentActionEvent:
    node_name: str
    execution_id: str
    action_type: str
    description: str
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class ToolStartedEvent:
    node_name: str
    execution_id: str
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class ToolCompletedEvent:
    node_name: str
    execution_id: str
    tool_name: str
    result: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class ToolFailedEvent:
    node_name: str
    execution_id: str
    tool_name: str
    error: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class ResourceConsumedEvent:
    node_name: str
    execution_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    gold: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class TokenStreamEvent:
    """Streaming token from LLM response for HUD visibility."""

    node_name: str
    execution_id: str
    token: str
    is_thought: bool = False
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class CommandHistoryEvent:
    """Command history update from agent_runner for HUD visibility."""

    node_name: str
    execution_id: str
    tool_name: str
    target: str
    count: int
    is_intercepted: bool = False
    timestamp: float = field(default_factory=time.monotonic)


# ─── CLI v2 Events ──────────────────────────────────────────────────


@dataclass
class PlanningStartedEvent:
    """Topology planning has begun (architect phase)."""

    architect_node: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class PlanningCompletedEvent:
    """Topology planning completed; graph is ready."""

    nodes: list[str] = field(default_factory=list)
    phases: dict[str, list[str]] = field(default_factory=dict)
    architect_node: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class GateWaitingEvent:
    """Essence Gate is waiting for user input."""

    node_name: str
    questions: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class GateResolvedEvent:
    """Essence Gate clarifications have been applied."""

    node_name: str
    clarifications_applied: int = 0
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class CheckpointEvent:
    """Execution checkpoint saved."""

    completed_nodes: list[str] = field(default_factory=list)
    active_node: str = ""
    state_version: int = 0
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class DiagnosticEvent:
    """Diagnostic message with severity."""

    severity: str = "INFO"  # INFO / WARN / ERROR / FATAL
    message: str = ""
    node_name: str = ""
    timestamp: float = field(default_factory=time.monotonic)


# ─── Threat Evaluator ─────────────────────────────────────────────────


class ThreatEvaluator:
    """Determines threat level from resource consumption."""

    @staticmethod
    def evaluate(resources: ResourceTracker, attempts_max: int) -> ThreatLevel:
        if attempts_max <= 0:
            return ThreatLevel.LOW

        attempt_ratio = resources.attempts / attempts_max
        context_ratio = resources.context_tokens / max(resources.tokens.input_tokens, 1)

        if attempt_ratio >= 0.8 or context_ratio >= 0.9:
            return ThreatLevel.CRITICAL
        if attempt_ratio >= 0.6 or context_ratio >= 0.7:
            return ThreatLevel.HIGH
        if attempt_ratio >= 0.4 or context_ratio >= 0.5:
            return ThreatLevel.MEDIUM
        return ThreatLevel.LOW


# ─── ExecutionState — Aggregate Root ──────────────────────────────────


class NodePayload:
    """Stores input prompt and output result for a node execution."""

    def __init__(self, node_name: str):
        self.node_name = node_name
        self.input_prompt: str = ""
        self.output_result: str = ""
        self.output_data: dict[str, Any] = {}


class ExecutionState:
    """Thread-safe aggregate root for HUD semantic state.

    All state transitions go through apply(event), which dispatches
    to the appropriate _handle_* reducer. The HUD reads only the
    frozen HUDSnapshot produced by get_snapshot().
    """

    def __init__(
        self,
        quest_id: str,
        title: str,
        all_node_names: list[str],
        max_attempts_map: dict[str, int] | None = None,
        context_limit: int = 128_000,
    ):
        self.quest_id = quest_id
        self.title = title
        self.all_node_names = all_node_names
        self.max_attempts_map = max_attempts_map or {}
        self.context_limit = context_limit

        self._status = ExecutionStatus.PENDING
        self._start_time = time.monotonic()
        self._end_time: float | None = None

        # Per-node execution tracking (latest execution per node)
        self._executions: dict[str, dict[str, NodeExecution]] = {}

        # Per-node payload storage (for Node Inspector X-Ray)
        self._payloads: dict[str, NodePayload] = {}

        # Completed nodes (aggregated by node name)
        self._completed: dict[str, NodeStatus] = {}

        # Narrative event log
        self._narrative: list[NarrativeEvent] = []

        # Command history per node (for HUD panel)
        self._command_history: dict[str, dict[str, int]] = {}

        # Total gold spent
        self._gold_spent = 0.0

        # CLI v2 state
        self._planning_node: str = ""
        self._planning_done = False
        self._diagnostics: list[dict[str, Any]] = []
        self._gate_node: str = ""
        self._gate_questions: list[dict[str, Any]] = []
        self._checkpoint: dict[str, Any] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Execution control (pause/resume/step)
        self._is_paused = False
        self._step_mode = False
        self._intervention_text: dict[str, str] = {}

        # Wall-clock offset for converting monotonic timestamps to wall-clock
        self._monotonic_offset = time.time() - time.monotonic()
        self._wall_clock_start = time.time()
        self._monotonic_start = time.monotonic()

    def apply(self, event: Any) -> None:
        """Dispatch event to the appropriate reducer."""
        with self._lock:
            if isinstance(event, NodeStartedEvent):
                self._handle_node_started(event)
            elif isinstance(event, NodeCompletedEvent):
                self._handle_node_completed(event)
            elif isinstance(event, QuestCompletedEvent):
                self._handle_quest_completed(event)
            elif isinstance(event, QuestFailedEvent):
                self._handle_quest_failed(event)
            elif isinstance(event, QuestCancelledEvent):
                self._handle_quest_cancelled(event)
            elif isinstance(event, AgentActionEvent):
                self._handle_agent_action(event)
            elif isinstance(event, ToolStartedEvent):
                self._handle_tool_started(event)
            elif isinstance(event, ToolCompletedEvent):
                self._handle_tool_completed(event)
            elif isinstance(event, ToolFailedEvent):
                self._handle_tool_failed(event)
            elif isinstance(event, ResourceConsumedEvent):
                self._handle_resource_consumed(event)
            elif isinstance(event, TokenStreamEvent):
                self._handle_token_streamed(event)
            elif isinstance(event, CommandHistoryEvent):
                self._handle_command_history(event)
            elif isinstance(event, PlanningStartedEvent):
                self._handle_planning_started(event)
            elif isinstance(event, PlanningCompletedEvent):
                self._handle_planning_completed(event)
            elif isinstance(event, GateWaitingEvent):
                self._handle_gate_waiting(event)
            elif isinstance(event, GateResolvedEvent):
                self._handle_gate_resolved(event)
            elif isinstance(event, CheckpointEvent):
                self._handle_checkpoint(event)
            elif isinstance(event, DiagnosticEvent):
                self._handle_diagnostic(event)

    def _handle_node_started(self, event: NodeStartedEvent) -> None:
        if self._status == ExecutionStatus.PENDING:
            self._status = ExecutionStatus.RUNNING

        node_execs = self._executions.setdefault(event.node_name, {})
        exec_record = NodeExecution(
            execution_id=event.execution_id,
            node_name=event.node_name,
            attempt_number=event.attempt_number,
            start_time=event.timestamp,
            status=NodeStatus.ACTIVE,
            resources=ResourceTracker(attempts=event.attempt_number),
            thinking_buffer="",
        )
        node_execs[event.execution_id] = exec_record

        self._narrative.append(
            NarrativeEvent(
                timestamp=event.timestamp,
                icon=self._get_icon(event.node_name),
                role=self._get_role(event.node_name),
                node_name=event.node_name,
                action_type="enter",
                description=f"Entered {event.node_name} (attempt {event.attempt_number})",
                color=self._get_color(event.node_name),
            )
        )

    def _handle_node_completed(self, event: NodeCompletedEvent) -> None:
        node_execs = self._executions.get(event.node_name, {})
        if event.execution_id in node_execs:
            node_execs[event.execution_id] = dc_replace(
                node_execs[event.execution_id],
                end_time=event.timestamp,
                status=event.status,
                thinking_buffer="",
            )

        self._completed[event.node_name] = event.status

        status_word = "completed" if event.status == NodeStatus.COMPLETED else "failed"
        self._narrative.append(
            NarrativeEvent(
                timestamp=event.timestamp,
                icon=self._get_icon(event.node_name),
                role=self._get_role(event.node_name),
                node_name=event.node_name,
                action_type="exit",
                description=f"{status_word.capitalize()} {event.node_name}",
                color=self._get_color(event.node_name),
            )
        )

    def _handle_quest_completed(self, event: QuestCompletedEvent) -> None:
        self._status = ExecutionStatus.COMPLETED
        self._end_time = event.timestamp

    def _handle_quest_failed(self, event: QuestFailedEvent) -> None:
        self._status = ExecutionStatus.FAILED
        self._end_time = event.timestamp

    def _handle_quest_cancelled(self, event: QuestCancelledEvent) -> None:
        self._status = ExecutionStatus.CANCELLED
        self._end_time = event.timestamp

    def _handle_agent_action(self, event: AgentActionEvent) -> None:
        node_execs = self._executions.get(event.node_name, {})
        if event.execution_id in node_execs:
            old = node_execs[event.execution_id]
            node_execs[event.execution_id] = dc_replace(
                old,
                last_action=event.description,
                action_type=event.action_type,
            )

        self._narrative.append(
            NarrativeEvent(
                timestamp=event.timestamp,
                icon=self._get_icon(event.node_name),
                role=self._get_role(event.node_name),
                node_name=event.node_name,
                action_type=event.action_type,
                description=event.description,
                color=self._get_color(event.node_name),
            )
        )

    def _handle_tool_started(self, event: ToolStartedEvent) -> None:
        node_execs = self._executions.get(event.node_name, {})
        if event.execution_id in node_execs:
            old = node_execs[event.execution_id]
            target = ""
            for v in event.args.values():
                if isinstance(v, str) and ("/" in v or "\\" in v):
                    target = v.split("/")[-1].split("\\")[-1]
                    break
            desc = f"{event.tool_name}{f' {target}' if target else ''}"
            node_execs[event.execution_id] = dc_replace(
                old,
                last_action=desc,
                action_type=event.tool_name,
                tool_count=old.tool_count + 1,
            )

    def _handle_tool_completed(self, event: ToolCompletedEvent) -> None:
        pass

    def _handle_tool_failed(self, event: ToolFailedEvent) -> None:
        node_execs = self._executions.get(event.node_name, {})
        if event.execution_id in node_execs:
            old = node_execs[event.execution_id]
            node_execs[event.execution_id] = dc_replace(
                old,
                last_action=f"{event.tool_name} failed: {event.error}",
                action_type=event.tool_name,
            )

    def _handle_resource_consumed(self, event: ResourceConsumedEvent) -> None:
        self._gold_spent += event.gold

        node_execs = self._executions.get(event.node_name, {})
        if event.execution_id in node_execs:
            old = node_execs[event.execution_id]
            old_res = old.resources
            new_res = ResourceTracker(
                attempts=old_res.attempts,
                tokens=TokenUsage(
                    input_tokens=old_res.tokens.input_tokens + event.input_tokens,
                    output_tokens=old_res.tokens.output_tokens + event.output_tokens,
                    cached_tokens=old_res.tokens.cached_tokens + event.cached_tokens,
                ),
                context_tokens=old_res.context_tokens + event.input_tokens + event.output_tokens,
                gold_spent=old_res.gold_spent + event.gold,
            )
            node_execs[event.execution_id] = dc_replace(old, resources=new_res)

    def _handle_token_streamed(self, event: TokenStreamEvent) -> None:
        node_execs = self._executions.get(event.node_name, {})
        if event.execution_id in node_execs:
            old = node_execs[event.execution_id]
            # Cap buffer at 2000 chars to prevent memory bloat
            new_buffer = (old.thinking_buffer + event.token)[:2000]
            node_execs[event.execution_id] = dc_replace(
                old,
                thinking_buffer=new_buffer,
                action_type="thinking",
            )

    def _handle_command_history(self, event: CommandHistoryEvent) -> None:
        node_history = self._command_history.setdefault(event.node_name, {})
        key = f"{event.tool_name}:{event.target}"
        node_history[key] = {
            "tool_name": event.tool_name,
            "target": event.target,
            "count": event.count,
            "is_intercepted": event.is_intercepted,
        }

    def _handle_planning_started(self, event: PlanningStartedEvent) -> None:
        self._planning_node = event.architect_node
        self._planning_done = False
        if self._status == ExecutionStatus.PENDING:
            self._status = ExecutionStatus.PLANNING

    def _handle_planning_completed(self, event: PlanningCompletedEvent) -> None:
        self._planning_node = event.architect_node or self._planning_node
        self._planning_done = True

    def _handle_gate_waiting(self, event: GateWaitingEvent) -> None:
        self._gate_node = event.node_name
        self._gate_questions = list(event.questions)
        self._status = ExecutionStatus.WAITING_FOR_INPUT

    def _handle_gate_resolved(self, event: GateResolvedEvent) -> None:
        self._gate_node = ""
        self._gate_questions = []
        self._status = ExecutionStatus.RESUMING

    def _handle_checkpoint(self, event: CheckpointEvent) -> None:
        self._checkpoint = {
            "completed_nodes": list(event.completed_nodes),
            "active_node": event.active_node,
            "state_version": event.state_version,
        }

    def _handle_diagnostic(self, event: DiagnosticEvent) -> None:
        self._diagnostics.append({
            "severity": event.severity,
            "message": event.message,
            "node_name": event.node_name,
            "timestamp": event.timestamp,
        })

    # ─── Payload Management (Node Inspector X-Ray) ──────────────────

    def store_payload(
        self, node_name: str, input_prompt: str = "", output_result: str = "", output_data: dict[str, Any] | None = None
    ) -> None:
        """Store input/output payload for a node (for Node Inspector)."""
        with self._lock:
            if node_name not in self._payloads:
                self._payloads[node_name] = NodePayload(node_name)
            payload = self._payloads[node_name]
            if input_prompt:
                payload.input_prompt = input_prompt[:8000]
            if output_result:
                payload.output_result = output_result[:8000]
            if output_data:
                payload.output_data = dict(output_data)

    def get_payload(self, node_name: str) -> NodePayload | None:
        """Retrieve payload for a node."""
        with self._lock:
            return self._payloads.get(node_name)

    def get_all_payloads(self) -> dict[str, NodePayload]:
        """Get all stored payloads."""
        with self._lock:
            return dict(self._payloads)

    # ─── Execution Control (Breakpoints) ────────────────────────────

    def pause(self) -> None:
        """Pause execution."""
        with self._lock:
            self._is_paused = True

    def resume(self) -> None:
        """Resume execution."""
        with self._lock:
            self._is_paused = False
            self._step_mode = False

    def step(self) -> None:
        """Enable step-by-step mode (auto-pause after each node)."""
        with self._lock:
            self._is_paused = False
            self._step_mode = True

    @property
    def is_paused(self) -> bool:
        """Check if execution is paused."""
        with self._lock:
            return self._is_paused

    @property
    def step_mode(self) -> bool:
        """Check if step-by-step mode is active."""
        with self._lock:
            return self._step_mode

    def pause_after_step(self) -> None:
        """Pause after completing one node (called by engine in step mode)."""
        with self._lock:
            if self._step_mode:
                self._is_paused = True

    def add_intervention(self, node_name: str, text: str) -> None:
        """Store user intervention text for a node."""
        with self._lock:
            self._intervention_text[node_name] = text

    def get_intervention(self, node_name: str) -> str | None:
        """Retrieve and clear intervention text for a node."""
        with self._lock:
            return self._intervention_text.pop(node_name, None)

    def has_intervention(self, node_name: str) -> bool:
        """Check if there's pending intervention for a node."""
        with self._lock:
            return node_name in self._intervention_text

    # ─── Queries ────────────────────────────────────────────────────

    @property
    def active_party(self) -> list[NodeExecution]:
        """Return nodes currently executing (ACTIVE status)."""
        with self._lock:
            result = []
            for execs in self._executions.values():
                for exec_record in execs.values():
                    if exec_record.status == NodeStatus.ACTIVE:
                        result.append(exec_record)
            return result

    def get_topology(self) -> list[TopologyNode]:
        """Aggregated status by node name, handles fan-out."""
        with self._lock:
            result = []
            for node_name in self.all_node_names:
                phase = node_name.split(".")[0] if "." in node_name else node_name.split("-")[0]
                if node_name in self._completed:
                    status = self._completed[node_name].value
                    duration = self._get_node_duration(node_name)
                    result.append(
                        TopologyNode(
                            node_name=node_name,
                            phase=phase,
                            status=status,
                            duration_seconds=duration,
                        )
                    )
                else:
                    execs = self._executions.get(node_name, {})
                    has_active = any(e.status == NodeStatus.ACTIVE for e in execs.values())
                    if has_active:
                        result.append(
                            TopologyNode(
                                node_name=node_name,
                                phase=phase,
                                status=NodeStatus.ACTIVE.value,
                            )
                        )
                    else:
                        is_locked = self._is_locked(node_name)
                        status = NodeStatus.LOCKED.value if is_locked else NodeStatus.AVAILABLE.value
                        result.append(
                            TopologyNode(
                                node_name=node_name,
                                phase=phase,
                                status=status,
                            )
                        )
            return result

    def get_quest_summary(self) -> QuestSummary:
        """Post-match stats."""
        with self._lock:
            elapsed = (self._end_time or time.monotonic()) - self._start_time
            total_nodes = len(self.all_node_names)
            completed_nodes = sum(1 for s in self._completed.values() if s == NodeStatus.COMPLETED)
            failed_nodes = sum(1 for s in self._completed.values() if s == NodeStatus.FAILED)

            total_attempts = 0
            total_retries = 0
            total_inp = 0
            total_out = 0
            total_cached = 0
            bottleneck_node = None
            bottleneck_attempts = 0

            for node_name, execs in self._executions.items():
                for exec_record in execs.values():
                    total_attempts += exec_record.resources.attempts
                    total_inp += exec_record.resources.tokens.input_tokens
                    total_out += exec_record.resources.tokens.output_tokens
                    total_cached += exec_record.resources.tokens.cached_tokens
                    if exec_record.resources.attempts > bottleneck_attempts:
                        bottleneck_attempts = exec_record.resources.attempts
                        bottleneck_node = node_name

            total_retries = max(0, total_attempts - len(self._executions))

            mvp_node = None
            if self._completed:
                mvp_node = next(
                    (n for n, s in self._completed.items() if s == NodeStatus.COMPLETED),
                    None,
                )

            return QuestSummary(
                quest_id=self.quest_id,
                title=self.title,
                status=self._status.value,
                elapsed_seconds=elapsed,
                gold_spent=self._gold_spent,
                total_nodes=total_nodes,
                completed_nodes=completed_nodes,
                failed_nodes=failed_nodes,
                total_attempts=total_attempts,
                total_retries=total_retries,
                total_tokens_input=total_inp,
                total_tokens_output=total_out,
                total_tokens_cached=total_cached,
                bottleneck_node=bottleneck_node,
                bottleneck_attempts=bottleneck_attempts,
                mvp_node=mvp_node,
            )

    def get_snapshot(self) -> HUDSnapshot:
        """Frozen snapshot for HUD rendering."""
        with self._lock:
            elapsed = (self._end_time or time.monotonic()) - self._start_time
            now = time.monotonic()

            party = []
            for exec_record in self.active_party:
                max_att = self.max_attempts_map.get(exec_record.node_name, 2)
                role = self._get_role(exec_record.node_name)
                icon = self._get_icon(exec_record.node_name)
                color = self._get_color(exec_record.node_name)
                duration = now - exec_record.start_time
                threat = ThreatEvaluator.evaluate(exec_record.resources, max_att)

                # Last 120 chars of thinking buffer for HUD display
                thinking = exec_record.thinking_buffer[-120:] if exec_record.thinking_buffer else ""
                phase = exec_record.action_type or "idle"

                party.append(
                    PartyMemberSnapshot(
                        node_name=exec_record.node_name,
                        role=role,
                        icon=icon,
                        color=color,
                        attempt=exec_record.attempt_number,
                        attempts_max=max_att,
                        status=exec_record.status.value,
                        duration_seconds=duration,
                        stamina_current=exec_record.resources.attempts,
                        mana_current=exec_record.resources.context_tokens,
                        mana_max=self.context_limit,
                        last_action=exec_record.last_action or "initializing",
                        threat_level=threat.value,
                        thinking_preview=thinking,
                        tool_count=exec_record.tool_count,
                        phase_name=phase,
                    )
                )

            narrative_events = list(self._narrative[-12:])

            # Build command history entries from active nodes
            cmd_history_entries = []
            for node_name, entries in self._command_history.items():
                for key, data in entries.items():
                    cmd_history_entries.append(
                        CommandHistoryEntry(
                            tool_name=data["tool_name"],
                            target=data["target"],
                            count=data["count"],
                            is_intercepted=data["is_intercepted"],
                        )
                    )
            # Sort by count descending, take last 8 for HUD display
            cmd_history_entries.sort(key=lambda e: e.count, reverse=True)
            cmd_history_entries = cmd_history_entries[:8]

            summary = None
            if self._status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
                summary = self.get_quest_summary()

            return HUDSnapshot(
                quest_id=self.quest_id,
                quest_title=self.title,
                quest_status=self._status.value,
                elapsed_seconds=elapsed,
                gold_spent=self._gold_spent,
                topology=self.get_topology(),
                party=party,
                narrative=narrative_events,
                command_history=cmd_history_entries,
                quest_summary=summary,
                wall_clock_ref=self._wall_clock_start,
                monotonic_ref=self._monotonic_start,
                is_paused=self._is_paused,
                step_mode=self._step_mode,
            )

    # ─── ViewModel (CLI v2) ─────────────────────────────────────────

    def get_view_model(
        self,
        graph_id: str = "",
        work_item: str = "",
    ):
        """Reduce internal state to a presentation-agnostic ExecutionViewModel.

        This is the authoritative source for rendering. The ViewModel contains
        no ANSI codes, terminal formatting, or layout decisions.
        """
        from eng_loop.tools.cli_viewmodel import (
            CheckpointInfo,
            DiagnosticEntry,
            EssenceGateInfo,
            EssenceQuestion,
            ExecutionViewModel,
            GraphNodeInfo,
            NodeExecution,
            NodeVisualStatus,
            PipelineMetrics,
            PipelineStatus,
            ProgressInfo,
        )

        with self._lock:
            now = time.monotonic()
            total_elapsed_ms = int((self._end_time or now) - self._start_time) * 1000

            # ── Determine pipeline status ──────────────────────────
            if self._status == ExecutionStatus.WAITING_FOR_INPUT:
                pipeline_status = PipelineStatus.WAITING_FOR_INPUT
            elif self._status == ExecutionStatus.FAILED:
                pipeline_status = PipelineStatus.FAILED
            elif self._status == ExecutionStatus.CANCELLED:
                pipeline_status = PipelineStatus.CANCELLED
            elif self._status == ExecutionStatus.COMPLETED:
                pipeline_status = PipelineStatus.COMPLETED
            elif self._status == ExecutionStatus.RESUMING:
                pipeline_status = PipelineStatus.RESUMING
            elif self._status == ExecutionStatus.PAUSED:
                pipeline_status = PipelineStatus.PAUSED
            elif self._status == ExecutionStatus.PLANNING:
                pipeline_status = PipelineStatus.PLANNING
            elif self._status == ExecutionStatus.RUNNING:
                pipeline_status = PipelineStatus.RUNNING
            else:
                # PENDING or unknown
                pipeline_status = (
                    PipelineStatus.PLANNING
                    if not self._planning_done
                    else PipelineStatus.RUNNING
                )

            # ── Build graph nodes ───────────────────────────────────
            nodes: dict[str, GraphNodeInfo] = {}
            phases: dict[str, list[str]] = {}
            total_executions = 0
            total_attempts_count = 0

            for node_name in self.all_node_names:
                phase = (
                    node_name.split(".")[0]
                    if "." in node_name
                    else node_name.split("-")[0]
                )
                phases.setdefault(phase, []).append(node_name)

                # Determine visual status
                if node_name in self._completed:
                    completed_status = self._completed[node_name]
                    if completed_status == NodeStatus.COMPLETED:
                        visual = NodeVisualStatus.SUCCESS
                    elif completed_status == NodeStatus.FAILED:
                        visual = NodeVisualStatus.FAILED
                    elif completed_status == NodeStatus.SKIPPED:
                        visual = NodeVisualStatus.CANCELLED
                    else:
                        visual = NodeVisualStatus.SUCCESS
                else:
                    execs = self._executions.get(node_name, {})
                    has_active = any(
                        e.status == NodeStatus.ACTIVE for e in execs.values()
                    )
                    if has_active:
                        visual = NodeVisualStatus.RUNNING
                    else:
                        visual = NodeVisualStatus.PENDING

                # Build execution records
                execs = self._executions.get(node_name, {})
                node_execs: list[NodeExecution] = []
                node_total_ms = 0
                node_tool_count = 0
                error_msg: str | None = None

                for exec_id, exec_record in execs.items():
                    ne = NodeExecution(
                        execution_id=exec_id,
                        start_ms=exec_record.start_time,
                        end_ms=exec_record.end_time,
                        result=(
                            "success"
                            if exec_record.status == NodeStatus.COMPLETED
                            else "failed"
                        ),
                    )
                    ne.attempts.append(
                        type("AttemptRecord", (), {
                            "attempt_num": exec_record.attempt_number,
                            "duration_ms": int(
                                (exec_record.end_time or now - exec_record.start_time)
                                * 1000
                            ),
                            "result": (
                                "success"
                                if exec_record.status == NodeStatus.COMPLETED
                                else "failed"
                            ),
                        })()
                    )
                    node_execs.append(ne)
                    total_executions += 1
                    total_attempts_count += exec_record.attempt_number
                    node_tool_count += exec_record.tool_count

                    if exec_record.end_time:
                        node_total_ms += int(
                            (exec_record.end_time - exec_record.start_time) * 1000
                        )

                    if exec_record.status == NodeStatus.FAILED:
                        error_msg = f"Node {node_name} failed"

                # Detect container nodes
                is_container = False
                children: list[str] = []
                for other in self.all_node_names:
                    if other != node_name and other.startswith(node_name + "."):
                        is_container = True
                        children.append(other)

                nodes[node_name] = GraphNodeInfo(
                    id=node_name,
                    phase=phase,
                    is_container=is_container,
                    children=children,
                    visual_status=visual,
                    executions=node_execs,
                    total_duration_ms=node_total_ms,
                    error_message=error_msg,
                    tool_count=node_tool_count,
                )

            # ── Derive container status from children ───────────────
            for node_id, node_info in nodes.items():
                if node_info.is_container and node_info.visual_status == NodeVisualStatus.PENDING:
                    # Derive from children
                    child_statuses = [
                        nodes[c].visual_status for c in node_info.children if c in nodes
                    ]
                    if any(
                        s == NodeVisualStatus.RUNNING for s in child_statuses
                    ):
                        node_info.visual_status = NodeVisualStatus.RUNNING
                    elif all(
                        s == NodeVisualStatus.SUCCESS for s in child_statuses
                    ):
                        node_info.visual_status = NodeVisualStatus.SUCCESS

            # ── Metrics ────────────────────────────────────────────
            total_nodes = len(self.all_node_names)
            completed_count = sum(
                1 for s in self._completed.values() if s == NodeStatus.COMPLETED
            )
            failed_count = sum(
                1 for s in self._completed.values() if s == NodeStatus.FAILED
            )
            running_count = len(self.active_party)
            pending_count = (
                total_nodes - completed_count - failed_count - running_count
            )
            retries = max(0, total_attempts_count - len(self._executions))

            metrics = PipelineMetrics(
                total_nodes=total_nodes,
                completed_nodes=completed_count,
                running_nodes=running_count,
                failed_nodes=failed_count,
                pending_nodes=pending_count,
                total_executions=total_executions,
                total_attempts=total_attempts_count,
                retries=retries,
            )

            progress = ProgressInfo(
                current=completed_count,
                total=total_nodes,
            )

            # ── Current execution ──────────────────────────────────
            current_node_id: str | None = None
            current_attempt = 0
            current_elapsed_ms = 0
            current_tool_count = 0

            for exec_record in self.active_party:
                current_node_id = exec_record.node_name
                current_attempt = exec_record.attempt_number
                current_elapsed_ms = int(
                    (now - exec_record.start_time) * 1000
                )
                current_tool_count = exec_record.tool_count

            # ── History (completed nodes, ordered) ─────────────────
            history: list[GraphNodeInfo] = []
            for node_name in self.all_node_names:
                if node_name in nodes and nodes[node_name].visual_status in (
                    NodeVisualStatus.SUCCESS,
                    NodeVisualStatus.FAILED,
                    NodeVisualStatus.CANCELLED,
                ):
                    history.append(nodes[node_name])

            # ── Planning ───────────────────────────────────────────
            planning_node_id: str | None = self._planning_node or None
            planning_status = (
                NodeVisualStatus.SUCCESS
                if self._planning_done
                else NodeVisualStatus.RUNNING
                if self._planning_node
                else NodeVisualStatus.PENDING
            )

            # ── Checkpoint ─────────────────────────────────────────
            checkpoint: CheckpointInfo | None = None
            if self._checkpoint:
                checkpoint = CheckpointInfo(
                    completed_nodes=self._checkpoint.get("completed_nodes", []),
                    active_node=self._checkpoint.get("active_node") or None,
                    state_version=self._checkpoint.get("state_version", 0),
                    graph_id=graph_id,
                )

            # ── Essence Gate ───────────────────────────────────────
            essence_gate: EssenceGateInfo | None = None
            if self._gate_questions:
                questions = [
                    EssenceQuestion(
                        id=q.get("id", f"q_{i}"),
                        severity=q.get("severity", "medium"),
                        question=q.get("question", ""),
                        finding_summary=q.get("finding_summary", ""),
                        options=q.get("options", []),
                        input_type="choice" if q.get("options") else "text",
                    )
                    for i, q in enumerate(self._gate_questions)
                ]
                essence_gate = EssenceGateInfo(
                    stage=self._gate_node,
                    questions=questions,
                    clarification_count=len(questions),
                )

            # ── Diagnostics ────────────────────────────────────────
            diagnostics = [
                DiagnosticEntry(
                    severity=d.get("severity", "INFO"),
                    message=d.get("message", ""),
                    node_id=d.get("node_name") or None,
                    timestamp=d.get("timestamp", 0.0),
                )
                for d in self._diagnostics
            ]

            return ExecutionViewModel(
                pipeline_status=pipeline_status,
                work_item=work_item or self.title,
                graph_id=graph_id or self.quest_id,
                planning_node_id=planning_node_id,
                planning_status=planning_status,
                nodes=nodes,
                phases=phases,
                current_node_id=current_node_id,
                current_attempt=current_attempt,
                current_elapsed_ms=current_elapsed_ms,
                current_tool_count=current_tool_count,
                metrics=metrics,
                progress=progress,
                history=history,
                checkpoint=checkpoint,
                essence_gate=essence_gate,
                diagnostics=diagnostics,
                total_elapsed_ms=total_elapsed_ms,
            )

    def _get_node_duration(self, node_name: str) -> float | None:
        execs = self._executions.get(node_name, {})
        total = 0.0
        for e in execs.values():
            if e.end_time:
                total += e.end_time - e.start_time
        return total if total > 0 else None

    def _is_locked(self, node_name: str) -> bool:
        completed_ordered = []
        for n in self.all_node_names:
            if n in self._completed:
                completed_ordered.append(n)

        if not completed_ordered:
            return node_name != self.all_node_names[0] if self.all_node_names else True

        idx = self.all_node_names.index(node_name) if node_name in self.all_node_names else -1
        if idx <= 0:
            return False

        last_completed = completed_ordered[-1]
        last_idx = self.all_node_names.index(last_completed) if last_completed in self.all_node_names else -1
        return idx > last_idx + 1

    @staticmethod
    def _get_role(node_name: str) -> str:
        mapping = {
            "init": "MAGE",
            "design": "DESIGNER",
            "arch": "ARCHITECT",
            "impl": "WARRIOR",
            "verify": "INSPECTOR",
            "e2e": "ALCHMIST",
            "qa.security": "GUARD",
            "qa.api-contract": "SCRIBE",
            "qa.performance": "SPEEDSTER",
            "deploy": "PILOT",
            "smoke": "ALCHMIST",
            "doc": "CHRONICLER",
            "post": "HERO",
        }
        for key, role in mapping.items():
            if node_name.startswith(key):
                return role
        return "NPC"

    @staticmethod
    def _get_icon(node_name: str) -> str:
        icons = {
            "MAGE": "G",
            "DESIGNER": "D",
            "ARCHITECT": "A",
            "WARRIOR": "W",
            "CHRONICLER": "C",
            "INSPECTOR": "I",
            "ALCHMIST": "E",
            "GUARD": "S",
            "SCRIBE": "R",
            "SPEEDSTER": "P",
            "PILOT": "Z",
            "HERO": "H",
        }
        role = ExecutionState._get_role(node_name)
        return icons.get(role, "?")

    @staticmethod
    def _get_color(node_name: str) -> str:
        mapping = {
            "init": "blue",
            "design": "cyan",
            "arch": "magenta",
            "impl": "green",
            "verify": "yellow",
            "e2e": "bright_magenta",
            "qa.security": "red",
            "qa.api-contract": "cyan",
            "qa.performance": "bright_yellow",
            "deploy": "bright_blue",
            "smoke": "bright_magenta",
            "doc": "white",
            "post": "white",
        }
        for key, color in mapping.items():
            if node_name.startswith(key):
                return color
        return "white"

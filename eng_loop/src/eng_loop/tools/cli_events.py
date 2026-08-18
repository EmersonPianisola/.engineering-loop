from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PipelineEvent:
    """A domain event representing a fact in the execution pipeline.

    Events are facts, not rendering instructions. They contain no ANSI codes,
    terminal formatting, or renderer-specific semantics.
    """

    timestamp: float
    event_id: str
    graph_id: str = ""
    node_id: str = ""
    execution_id: str = ""
    attempt: int = 0
    event_type: str = ""
    status: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        event_type: str,
        *,
        graph_id: str = "",
        node_id: str = "",
        execution_id: str = "",
        attempt: int = 0,
        status: str = "",
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PipelineEvent:
        return cls(
            timestamp=time.monotonic(),
            event_id=uuid.uuid4().hex[:12],
            graph_id=graph_id,
            node_id=node_id,
            execution_id=execution_id,
            attempt=attempt,
            event_type=event_type,
            status=status,
            message=message,
            metadata=metadata or {},
        )


# ─── Event type constants ──────────────────────────────────────────

# Planning
EVENT_PLANNING_STARTED = "planning.started"
EVENT_PLANNING_COMPLETED = "planning.completed"

# Node lifecycle
EVENT_NODE_STARTED = "node.started"
EVENT_NODE_COMPLETED = "node.completed"
EVENT_NODE_FAILED = "node.failed"
EVENT_NODE_SKIPPED = "node.skipped"

# Attempt lifecycle
EVENT_ATTEMPT_STARTED = "attempt.started"
EVENT_ATTEMPT_COMPLETED = "attempt.completed"

# Essence Gate
EVENT_GATE_WAITING = "gate.waiting"
EVENT_GATE_RESOLVED = "gate.resolved"

# Pipeline lifecycle
EVENT_PIPELINE_STARTED = "pipeline.started"
EVENT_PIPELINE_COMPLETED = "pipeline.completed"
EVENT_PIPELINE_FAILED = "pipeline.failed"
EVENT_PIPELINE_CANCELLED = "pipeline.cancelled"
EVENT_PIPELINE_PAUSED = "pipeline.paused"
EVENT_PIPELINE_RESUMING = "pipeline.resuming"

# Checkpoint
EVENT_CHECKPOINT_SAVED = "checkpoint.saved"

# Diagnostics
EVENT_DIAGNOSTIC_INFO = "diagnostic.info"
EVENT_DIAGNOSTIC_WARNING = "diagnostic.warning"
EVENT_DIAGNOSTIC_ERROR = "diagnostic.error"
EVENT_DIAGNOSTIC_FATAL = "diagnostic.fatal"


# ─── Convenience constructors ──────────────────────────────────────


def planning_started(graph_id: str, architect_node: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PLANNING_STARTED,
        graph_id=graph_id,
        node_id=architect_node,
        status="planning",
        message="Topology planning started",
    )


def planning_completed(
    graph_id: str,
    *,
    nodes: list[str],
    phases: dict[str, list[str]] | None = None,
    architect_node: str = "",
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PLANNING_COMPLETED,
        graph_id=graph_id,
        node_id=architect_node,
        status="planning",
        message=f"Topology proposed: {len(nodes)} nodes",
        metadata={"nodes": nodes, "phases": phases or {}},
    )


def node_started(
    graph_id: str,
    node_id: str,
    *,
    execution_id: str = "",
    attempt: int = 1,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_NODE_STARTED,
        graph_id=graph_id,
        node_id=node_id,
        execution_id=execution_id,
        attempt=attempt,
        status="running",
        message=f"Node {node_id} started (attempt {attempt})",
    )


def node_completed(
    graph_id: str,
    node_id: str,
    *,
    execution_id: str = "",
    attempt: int = 1,
    duration_ms: int = 0,
    tool_count: int = 0,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_NODE_COMPLETED,
        graph_id=graph_id,
        node_id=node_id,
        execution_id=execution_id,
        attempt=attempt,
        status="success",
        message=f"Node {node_id} completed",
        metadata={"duration_ms": duration_ms, "tool_count": tool_count},
    )


def node_failed(
    graph_id: str,
    node_id: str,
    *,
    execution_id: str = "",
    attempt: int = 1,
    error: str = "",
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_NODE_FAILED,
        graph_id=graph_id,
        node_id=node_id,
        execution_id=execution_id,
        attempt=attempt,
        status="failed",
        message=f"Node {node_id} failed: {error}",
        metadata={"error": error},
    )


def node_skipped(
    graph_id: str,
    node_id: str,
    *,
    reason: str = "",
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_NODE_SKIPPED,
        graph_id=graph_id,
        node_id=node_id,
        status="skipped",
        message=f"Node {node_id} skipped: {reason}",
        metadata={"reason": reason},
    )


def attempt_started(
    graph_id: str,
    node_id: str,
    *,
    execution_id: str = "",
    attempt: int = 1,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_ATTEMPT_STARTED,
        graph_id=graph_id,
        node_id=node_id,
        execution_id=execution_id,
        attempt=attempt,
        status="running",
        message=f"Attempt {attempt} for {node_id}",
    )


def attempt_completed(
    graph_id: str,
    node_id: str,
    *,
    execution_id: str = "",
    attempt: int = 1,
    result: str = "success",
    duration_ms: int = 0,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_ATTEMPT_COMPLETED,
        graph_id=graph_id,
        node_id=node_id,
        execution_id=execution_id,
        attempt=attempt,
        status=result,
        message=f"Attempt {attempt} for {node_id}: {result}",
        metadata={"result": result, "duration_ms": duration_ms},
    )


def gate_waiting(
    graph_id: str,
    node_id: str,
    *,
    questions: list[dict[str, Any]],
    reason: str = "",
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_GATE_WAITING,
        graph_id=graph_id,
        node_id=node_id,
        status="waiting_for_input",
        message=f"Essence Gate waiting at {node_id}: {len(questions)} questions",
        metadata={"questions": questions, "reason": reason},
    )


def gate_resolved(
    graph_id: str,
    node_id: str,
    *,
    clarifications_applied: int = 0,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_GATE_RESOLVED,
        graph_id=graph_id,
        node_id=node_id,
        status="resolved",
        message=f"Essence Gate resolved at {node_id}: {clarifications_applied} clarifications",
        metadata={"clarifications_applied": clarifications_applied},
    )


def pipeline_started(graph_id: str, work_item: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PIPELINE_STARTED,
        graph_id=graph_id,
        status="running",
        message=f"Pipeline started: {work_item}",
        metadata={"work_item": work_item},
    )


def pipeline_completed(
    graph_id: str,
    *,
    total_nodes: int = 0,
    total_executions: int = 0,
    total_attempts: int = 0,
    duration_ms: int = 0,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PIPELINE_COMPLETED,
        graph_id=graph_id,
        status="completed",
        message="Pipeline completed successfully",
        metadata={
            "total_nodes": total_nodes,
            "total_executions": total_executions,
            "total_attempts": total_attempts,
            "duration_ms": duration_ms,
        },
    )


def pipeline_failed(
    graph_id: str,
    *,
    node_id: str = "",
    reason: str = "",
    attempts: int = 0,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PIPELINE_FAILED,
        graph_id=graph_id,
        node_id=node_id,
        status="failed",
        message=f"Pipeline failed: {reason}",
        metadata={"reason": reason, "attempts": attempts},
    )


def pipeline_cancelled(graph_id: str, reason: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PIPELINE_CANCELLED,
        graph_id=graph_id,
        status="cancelled",
        message=f"Pipeline cancelled: {reason}",
        metadata={"reason": reason},
    )


def pipeline_paused(graph_id: str, reason: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PIPELINE_PAUSED,
        graph_id=graph_id,
        status="paused",
        message=f"Pipeline paused: {reason}",
        metadata={"reason": reason},
    )


def pipeline_resuming(
    graph_id: str,
    *,
    checkpoint_stage: str = "",
    invalidated_stages: list[str] | None = None,
    preserved_stages: list[str] | None = None,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_PIPELINE_RESUMING,
        graph_id=graph_id,
        status="resuming",
        message=f"Pipeline resuming from {checkpoint_stage}",
        metadata={
            "checkpoint_stage": checkpoint_stage,
            "invalidated_stages": invalidated_stages or [],
            "preserved_stages": preserved_stages or [],
        },
    )


def checkpoint_saved(
    graph_id: str,
    *,
    completed_nodes: list[str],
    active_node: str = "",
    state_version: int = 0,
) -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_CHECKPOINT_SAVED,
        graph_id=graph_id,
        node_id=active_node,
        status="checkpoint",
        message=f"Checkpoint: {len(completed_nodes)} completed nodes",
        metadata={
            "completed_nodes": completed_nodes,
            "active_node": active_node,
            "state_version": state_version,
        },
    )


def diagnostic_info(node_id: str = "", message: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_DIAGNOSTIC_INFO,
        node_id=node_id,
        status="info",
        message=message,
    )


def diagnostic_warning(node_id: str = "", message: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_DIAGNOSTIC_WARNING,
        node_id=node_id,
        status="warning",
        message=message,
    )


def diagnostic_error(node_id: str = "", message: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_DIAGNOSTIC_ERROR,
        node_id=node_id,
        status="error",
        message=message,
    )


def diagnostic_fatal(node_id: str = "", message: str = "") -> PipelineEvent:
    return PipelineEvent.new(
        EVENT_DIAGNOSTIC_FATAL,
        node_id=node_id,
        status="fatal",
        message=message,
    )

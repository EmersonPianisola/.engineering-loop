from __future__ import annotations

import dataclasses

from eng_loop.tools.cli_events import (
    PipelineEvent,
    attempt_completed,
    attempt_started,
    checkpoint_saved,
    diagnostic_error,
    diagnostic_fatal,
    diagnostic_info,
    diagnostic_warning,
    gate_resolved,
    gate_waiting,
    node_completed,
    node_failed,
    node_skipped,
    node_started,
    pipeline_cancelled,
    pipeline_completed,
    pipeline_failed,
    pipeline_paused,
    pipeline_resuming,
    pipeline_started,
    planning_completed,
    planning_started,
)


class TestPipelineEvent:
    def test_new_event(self):
        event = PipelineEvent.new(
            "test.event",
            graph_id="g-1",
            node_id="init",
            status="running",
            message="test message",
        )
        assert event.event_type == "test.event"
        assert event.graph_id == "g-1"
        assert event.node_id == "init"
        assert event.status == "running"
        assert event.message == "test message"
        assert event.timestamp > 0
        assert len(event.event_id) == 12

    def test_event_is_frozen(self):
        event = PipelineEvent.new("test", status="ok")
        import pytest

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.status = "changed"  # type: ignore

    def test_default_metadata(self):
        event = PipelineEvent.new("test")
        assert event.metadata == {}

    def test_custom_metadata(self):
        event = PipelineEvent.new("test", metadata={"key": "value"})
        assert event.metadata == {"key": "value"}


class TestPlanningEvents:
    def test_planning_started(self):
        event = planning_started(graph_id="g-1", architect_node="dynamic.architect")
        assert event.event_type == "planning.started"
        assert event.node_id == "dynamic.architect"
        assert event.status == "planning"

    def test_planning_completed(self):
        nodes = ["init", "impl.code", "post"]
        event = planning_completed(
            graph_id="g-1",
            nodes=nodes,
            phases={"INIT": ["init"], "IMPL": ["impl.code"], "POST": ["post"]},
        )
        assert event.event_type == "planning.completed"
        assert event.metadata["nodes"] == nodes
        assert "INIT" in event.metadata["phases"]


class TestNodeEvents:
    def test_node_started(self):
        event = node_started("g-1", "init", execution_id="exec-1", attempt=1)
        assert event.event_type == "node.started"
        assert event.node_id == "init"
        assert event.attempt == 1
        assert event.status == "running"

    def test_node_completed(self):
        event = node_completed("g-1", "init", duration_ms=5000, tool_count=3)
        assert event.event_type == "node.completed"
        assert event.status == "success"
        assert event.metadata["duration_ms"] == 5000
        assert event.metadata["tool_count"] == 3

    def test_node_failed(self):
        event = node_failed("g-1", "init", error="test failed")
        assert event.event_type == "node.failed"
        assert event.status == "failed"
        assert event.metadata["error"] == "test failed"

    def test_node_skipped(self):
        event = node_skipped("g-1", "init", reason="already done")
        assert event.event_type == "node.skipped"
        assert event.metadata["reason"] == "already done"


class TestAttemptEvents:
    def test_attempt_started(self):
        event = attempt_started("g-1", "init", attempt=2)
        assert event.event_type == "attempt.started"
        assert event.attempt == 2

    def test_attempt_completed(self):
        event = attempt_completed("g-1", "init", attempt=2, result="success", duration_ms=3000)
        assert event.event_type == "attempt.completed"
        assert event.status == "success"
        assert event.metadata["duration_ms"] == 3000


class TestGateEvents:
    def test_gate_waiting(self):
        questions = [{"id": "q1", "question": "What type?"}]
        event = gate_waiting("g-1", "post", questions=questions)
        assert event.event_type == "gate.waiting"
        assert event.status == "waiting_for_input"
        assert len(event.metadata["questions"]) == 1

    def test_gate_resolved(self):
        event = gate_resolved("g-1", "post", clarifications_applied=3)
        assert event.event_type == "gate.resolved"
        assert event.metadata["clarifications_applied"] == 3


class TestPipelineEvents:
    def test_pipeline_started(self):
        event = pipeline_started("g-1", work_item="Add feature")
        assert event.event_type == "pipeline.started"
        assert event.metadata["work_item"] == "Add feature"

    def test_pipeline_completed(self):
        event = pipeline_completed("g-1", total_nodes=5, total_executions=7, total_attempts=11)
        assert event.event_type == "pipeline.completed"
        assert event.metadata["total_nodes"] == 5

    def test_pipeline_failed(self):
        event = pipeline_failed("g-1", node_id="impl.code", reason="validation_failed")
        assert event.event_type == "pipeline.failed"
        assert event.metadata["reason"] == "validation_failed"

    def test_pipeline_cancelled(self):
        event = pipeline_cancelled("g-1", reason="user interrupted")
        assert event.event_type == "pipeline.cancelled"

    def test_pipeline_paused(self):
        event = pipeline_paused("g-1", reason="breakpoint")
        assert event.event_type == "pipeline.paused"

    def test_pipeline_resuming(self):
        event = pipeline_resuming(
            "g-1",
            checkpoint_stage="post",
            invalidated_stages=["post"],
            preserved_stages=["init", "impl.code"],
        )
        assert event.event_type == "pipeline.resuming"
        assert event.metadata["checkpoint_stage"] == "post"


class TestCheckpointEvents:
    def test_checkpoint_saved(self):
        event = checkpoint_saved(
            "g-1",
            completed_nodes=["init", "impl.code"],
            active_node="post",
            state_version=3,
        )
        assert event.event_type == "checkpoint.saved"
        assert len(event.metadata["completed_nodes"]) == 2


class TestDiagnosticEvents:
    def test_diagnostic_info(self):
        event = diagnostic_info(node_id="init", message="Starting init")
        assert event.event_type == "diagnostic.info"

    def test_diagnostic_warning(self):
        event = diagnostic_warning(node_id="init", message="Fallback used")
        assert event.event_type == "diagnostic.warning"

    def test_diagnostic_error(self):
        event = diagnostic_error(node_id="init", message="File not found")
        assert event.event_type == "diagnostic.error"

    def test_diagnostic_fatal(self):
        event = diagnostic_fatal(node_id="init", message="Required file missing")
        assert event.event_type == "diagnostic.fatal"

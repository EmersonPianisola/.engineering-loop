from __future__ import annotations

"""Tests for ExecutionState, EventNormalizer, and ThreatEvaluator."""

import time

from eng_loop.tools.event_normalizer import EventNormalizer, HUDTelemetryCallback
from eng_loop.tools.execution_state import (
    AgentActionEvent,
    ExecutionState,
    ExecutionStatus,
    HUDSnapshot,
    NodeCompletedEvent,
    NodeStartedEvent,
    NodeStatus,
    QuestCancelledEvent,
    QuestCompletedEvent,
    QuestFailedEvent,
    QuestSummary,
    ResourceConsumedEvent,
    ResourceTracker,
    ThreatEvaluator,
    ThreatLevel,
    TokenUsage,
    ToolFailedEvent,
    ToolStartedEvent,
)

# ============================================================
# THREAT EVALUATOR
# ============================================================


class TestThreatEvaluator:
    def test_low_threat(self):
        resources = ResourceTracker(attempts=1, tokens=TokenUsage(input_tokens=100, output_tokens=50))
        level = ThreatEvaluator.evaluate(resources, 5)
        assert level == ThreatLevel.LOW

    def test_medium_threat(self):
        resources = ResourceTracker(attempts=2, tokens=TokenUsage(input_tokens=100, output_tokens=50))
        level = ThreatEvaluator.evaluate(resources, 5)
        assert level == ThreatLevel.MEDIUM

    def test_high_threat(self):
        resources = ResourceTracker(attempts=3, tokens=TokenUsage(input_tokens=100, output_tokens=50))
        level = ThreatEvaluator.evaluate(resources, 5)
        assert level == ThreatLevel.HIGH

    def test_critical_threat(self):
        resources = ResourceTracker(attempts=4, tokens=TokenUsage(input_tokens=100, output_tokens=50))
        level = ThreatEvaluator.evaluate(resources, 5)
        assert level == ThreatLevel.CRITICAL

    def test_zero_max_attempts(self):
        resources = ResourceTracker(attempts=10)
        level = ThreatEvaluator.evaluate(resources, 0)
        assert level == ThreatLevel.LOW

    def test_context_ratio_high_threat(self):
        resources = ResourceTracker(
            attempts=1,
            tokens=TokenUsage(input_tokens=1000, output_tokens=100),
            context_tokens=750,
        )
        level = ThreatEvaluator.evaluate(resources, 10)
        assert level == ThreatLevel.HIGH


# ============================================================
# EXECUTION STATE
# ============================================================


class TestExecutionState:
    def test_initial_state(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test Quest",
            all_node_names=["init", "impl-code", "verify", "post"],
        )
        assert es._status == ExecutionStatus.PENDING
        assert es.title == "Test Quest"

    def test_node_started_transitions_to_running(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "post"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        assert es._status == ExecutionStatus.RUNNING

    def test_node_completed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "post"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            NodeCompletedEvent(
                node_name="init",
                execution_id="e-1",
                status=NodeStatus.COMPLETED,
                timestamp=time.monotonic(),
            )
        )
        assert es._completed["init"] == NodeStatus.COMPLETED

    def test_quest_completed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(QuestCompletedEvent(reason="done"))
        assert es._status == ExecutionStatus.COMPLETED

    def test_quest_failed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(QuestFailedEvent(reason="error"))
        assert es._status == ExecutionStatus.FAILED

    def test_quest_cancelled(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(QuestCancelledEvent(reason="user"))
        assert es._status == ExecutionStatus.CANCELLED

    def test_active_party(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "post"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        party = es.active_party
        assert len(party) == 1
        assert party[0].node_name == "init"

    def test_active_party_empty_after_completion(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            NodeCompletedEvent(
                node_name="init",
                execution_id="e-1",
                status=NodeStatus.COMPLETED,
                timestamp=time.monotonic(),
            )
        )
        party = es.active_party
        assert len(party) == 0

    def test_topology(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "impl-code", "verify", "post"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            NodeCompletedEvent(
                node_name="init",
                execution_id="e-1",
                status=NodeStatus.COMPLETED,
                timestamp=time.monotonic(),
            )
        )
        topo = es.get_topology()
        assert len(topo) == 4
        init_node = next(n for n in topo if n.node_name == "init")
        assert init_node.status == "completed"

    def test_snapshot(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test Quest",
            all_node_names=["init", "post"],
            max_attempts_map={"init": 3},
        )
        snapshot = es.get_snapshot()
        assert isinstance(snapshot, HUDSnapshot)
        assert snapshot.quest_id == "q-1"
        assert snapshot.quest_title == "Test Quest"
        assert snapshot.quest_status == "pending"

    def test_quest_summary(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "post"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            NodeCompletedEvent(
                node_name="init",
                execution_id="e-1",
                status=NodeStatus.COMPLETED,
                timestamp=time.monotonic(),
            )
        )
        es.apply(QuestCompletedEvent(reason="done"))
        summary = es.get_quest_summary()
        assert isinstance(summary, QuestSummary)
        assert summary.completed_nodes == 1
        assert summary.total_nodes == 2

    def test_resource_consumed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            ResourceConsumedEvent(
                node_name="init",
                execution_id="e-1",
                input_tokens=100,
                output_tokens=50,
                cached_tokens=10,
                gold=0.01,
                timestamp=time.monotonic(),
            )
        )
        assert es._gold_spent == 0.01

    def test_agent_action(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            AgentActionEvent(
                node_name="init",
                execution_id="e-1",
                action_type="reading",
                description="Reading file",
                timestamp=time.monotonic(),
            )
        )
        assert len(es._narrative) == 2

    def test_tool_started(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            ToolStartedEvent(
                node_name="init",
                execution_id="e-1",
                tool_name="read",
                args={"file_path": "/src/main.py"},
                timestamp=time.monotonic(),
            )
        )

    def test_tool_failed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        es.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="e-1",
                attempt_number=1,
                timestamp=time.monotonic(),
            )
        )
        es.apply(
            ToolFailedEvent(
                node_name="init",
                execution_id="e-1",
                tool_name="read",
                error="file not found",
                timestamp=time.monotonic(),
            )
        )


# ============================================================
# EVENT NORMALIZER
# ============================================================


class TestEventNormalizer:
    def test_node_entered(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "post"],
        )
        norm = EventNormalizer(es, ["init", "post"])
        exec_id = norm.node_entered("init")
        assert exec_id.startswith("init-")
        assert es._status == ExecutionStatus.RUNNING

    def test_node_completed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init", "post"],
        )
        norm = EventNormalizer(es, ["init", "post"])
        norm.node_entered("init")
        from eng_loop.tools.execution_state import NodeStatus as NS

        norm.node_completed("init", NS.COMPLETED)
        assert es._completed["init"] == NS.COMPLETED

    def test_attempt_counter_increments(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.node_entered("init")
        norm.node_entered("init")
        assert norm._attempt_counter["init"] == 2

    def test_agent_action(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.node_entered("init")
        norm.agent_action("init", "reading", "Reading file.py")
        assert len(es._narrative) == 2

    def test_tool_lifecycle(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.node_entered("init")
        norm.tool_started("init", "read", {"file_path": "main.py"})
        norm.tool_completed("init", "read", "success")

    def test_tokens_consumed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.node_entered("init")
        norm.tokens_consumed("init", input_tokens=100, output_tokens=50, gold=0.01)
        assert es._gold_spent == 0.01

    def test_quest_lifecycle(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.quest_completed("done")
        assert es._status == ExecutionStatus.COMPLETED

    def test_quest_failed(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.quest_failed("error")
        assert es._status == ExecutionStatus.FAILED

    def test_quest_cancelled(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        norm.quest_cancelled("user")
        assert es._status == ExecutionStatus.CANCELLED


# ============================================================
# HUD TELEMETRY CALLBACK
# ============================================================


class TestHUDTelemetryCallback:
    def test_extract_node_name(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        cb = HUDTelemetryCallback(norm)
        node = cb._extract_node_name(["langgraph_node:init", "other"])
        assert node == "init"

    def test_extract_node_name_none(self):
        es = ExecutionState(
            quest_id="q-1",
            title="Test",
            all_node_names=["init"],
        )
        norm = EventNormalizer(es, ["init"])
        cb = HUDTelemetryCallback(norm)
        node = cb._extract_node_name(["no_match"])
        assert node is None

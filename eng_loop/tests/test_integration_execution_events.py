from __future__ import annotations

"""Integration tests: execution state + event normalizer lifecycle.

Validates the full event-sourced execution tracking:
  node_entered -> tool_started -> tool_completed -> agent_action -> node_completed
"""

from eng_loop.tools.event_normalizer import EventNormalizer
from eng_loop.tools.execution_state import (
    AgentActionEvent,
    ExecutionState,
    ExecutionStatus,
    NodeCompletedEvent,
    NodeStartedEvent,
    NodeStatus,
    QuestCancelledEvent,
    QuestCompletedEvent,
    QuestFailedEvent,
    ResourceConsumedEvent,
    ToolCompletedEvent,
    ToolStartedEvent,
)


class TestExecutionStateLifecycle:
    """Full lifecycle: quest start -> node execution -> quest complete."""

    def test_quest_lifecycle(self):
        state = ExecutionState(
            quest_id="test-quest",
            title="Test Feature",
            all_node_names=["init", "impl.code", "post"],
        )

        # Status is private (_status), accessed via snapshot
        assert state._status == ExecutionStatus.PENDING

        normalizer = EventNormalizer(state, ["init", "impl.code", "post"])

        # Execute nodes (first node_start transitions from PENDING to RUNNING)
        exec_id_init = normalizer.node_entered("init")
        assert state._status == ExecutionStatus.RUNNING
        normalizer.node_completed("init", NodeStatus.COMPLETED)

        exec_id_impl = normalizer.node_entered("impl.code")
        normalizer.node_completed("impl.code", NodeStatus.COMPLETED)

        exec_id_post = normalizer.node_entered("post")
        normalizer.node_completed("post", NodeStatus.COMPLETED)

        # Complete quest
        state.apply(QuestCompletedEvent())
        assert state._status == ExecutionStatus.COMPLETED

        # Verify completed nodes via _completed dict
        assert "init" in state._completed
        assert "impl.code" in state._completed
        assert "post" in state._completed

    def test_node_retry_tracking(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        normalizer = EventNormalizer(state, ["init"])

        # First attempt
        normalizer.node_entered("init")
        normalizer.node_completed("init", NodeStatus.COMPLETED)

        # Retry
        normalizer.node_entered("init")
        normalizer.node_completed("init", NodeStatus.COMPLETED)

    def test_node_failure_tracking(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        normalizer = EventNormalizer(state, ["init"])

        normalizer.node_entered("init")
        normalizer.node_completed("init", NodeStatus.FAILED)

        assert state._completed["init"] == NodeStatus.FAILED

    def test_tool_event_tracking(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["impl.code"])
        normalizer = EventNormalizer(state, ["impl.code"])

        exec_id = normalizer.node_entered("impl.code")

        state.apply(
            ToolStartedEvent(
                node_name="impl.code",
                execution_id=exec_id,
                tool_name="read",
                args={"file_path": "test.py"},
            )
        )
        state.apply(
            ToolCompletedEvent(
                node_name="impl.code",
                execution_id=exec_id,
                tool_name="read",
            )
        )

        execs = state._executions.get("impl.code", {})
        node_exec = execs.get(exec_id)
        assert node_exec is not None
        assert node_exec.tool_count >= 1

    def test_agent_action_tracking(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["impl.code"])
        normalizer = EventNormalizer(state, ["impl.code"])

        exec_id = normalizer.node_entered("impl.code")
        state.apply(
            AgentActionEvent(
                node_name="impl.code",
                execution_id=exec_id,
                action_type="writing",
                description="Writing file src/main.py",
            )
        )

        execs = state._executions.get("impl.code", {})
        node_exec = execs.get(exec_id)
        assert node_exec is not None
        assert node_exec.last_action == "Writing file src/main.py"
        assert node_exec.action_type == "writing"

    def test_resource_consumption_tracking(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["impl.code"])
        normalizer = EventNormalizer(state, ["impl.code"])

        exec_id = normalizer.node_entered("impl.code")
        state.apply(
            ResourceConsumedEvent(
                node_name="impl.code",
                execution_id=exec_id,
                input_tokens=1000,
                output_tokens=500,
            )
        )

        execs = state._executions.get("impl.code", {})
        node_exec = execs.get(exec_id)
        assert node_exec is not None
        assert node_exec.resources.tokens.input_tokens == 1000
        assert node_exec.resources.tokens.output_tokens == 500

    def test_quest_failure(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        normalizer = EventNormalizer(state, ["init"])

        normalizer.node_entered("init")
        normalizer.node_completed("init", NodeStatus.FAILED)
        state.apply(QuestFailedEvent(reason="Max attempts exceeded"))

        assert state._status == ExecutionStatus.FAILED

    def test_quest_cancellation(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        normalizer = EventNormalizer(state, ["init"])

        normalizer.node_entered("init")
        state.apply(QuestCancelledEvent(reason="User cancelled"))

        assert state._status == ExecutionStatus.CANCELLED

    def test_multiple_nodes_parallel(self):
        state = ExecutionState(
            quest_id="test",
            title="Test",
            all_node_names=["qa.security", "qa.api-contract", "deploy.prepare"],
        )
        normalizer = EventNormalizer(state, ["qa.security", "qa.api-contract", "deploy.prepare"])

        exec_id_sec = normalizer.node_entered("qa.security")
        exec_id_api = normalizer.node_entered("qa.api-contract")

        # Both should be active
        sec_execs = state._executions.get("qa.security", {})
        api_execs = state._executions.get("qa.api-contract", {})
        assert sec_execs[exec_id_sec].status == NodeStatus.ACTIVE
        assert api_execs[exec_id_api].status == NodeStatus.ACTIVE

        normalizer.node_completed("qa.security", NodeStatus.COMPLETED)
        normalizer.node_completed("qa.api-contract", NodeStatus.COMPLETED)

        assert state._completed["qa.security"] == NodeStatus.COMPLETED
        assert state._completed["qa.api-contract"] == NodeStatus.COMPLETED

    def test_execution_id_correlation(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["impl.code"])
        normalizer = EventNormalizer(state, ["impl.code"])

        exec_id = normalizer.node_entered("impl.code")
        assert exec_id is not None
        assert len(exec_id) > 0

        state.apply(
            ToolStartedEvent(
                node_name="impl.code",
                execution_id=exec_id,
                tool_name="read",
            )
        )
        state.apply(
            ToolCompletedEvent(
                node_name="impl.code",
                execution_id=exec_id,
                tool_name="read",
            )
        )

        execs = state._executions.get("impl.code", {})
        node_exec = execs.get(exec_id)
        assert node_exec is not None
        assert node_exec.execution_id == exec_id


class TestExecutionStateSnapshots:
    """Snapshots and narrative events."""

    def test_narrative_events_recorded(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        normalizer = EventNormalizer(state, ["init"])

        normalizer.node_entered("init")
        normalizer.node_completed("init", NodeStatus.COMPLETED)

        assert len(state._narrative) >= 2

    def test_get_snapshot(self):
        state = ExecutionState(quest_id="test-quest", title="Test Feature", all_node_names=["init", "post"])
        normalizer = EventNormalizer(state, ["init", "post"])

        normalizer.node_entered("init")
        normalizer.node_completed("init", NodeStatus.COMPLETED)

        snapshot = state.get_snapshot()
        assert snapshot.quest_id == "test-quest"
        assert snapshot.quest_title == "Test Feature"


class TestEventNormalizerEdgeCases:
    """Edge cases in event normalization."""

    def test_tool_event_before_node_entered(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["impl.code"])
        normalizer = EventNormalizer(state, ["impl.code"])

        normalizer.tool_started("impl.code", "read")

    def test_agent_action_before_node_entered(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["impl.code"])
        normalizer = EventNormalizer(state, ["impl.code"])

        normalizer.agent_action("impl.code", "thinking", "Planning")

    def test_node_completed_without_enter(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["unknown"])
        normalizer = EventNormalizer(state, ["unknown"])

        normalizer.node_completed("unknown", NodeStatus.FAILED)

    def test_unknown_node_handling(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        normalizer = EventNormalizer(state, ["init"])

        normalizer.node_entered("unexpected_node")

    def test_max_attempts_map(self):
        state = ExecutionState(
            quest_id="test",
            title="Test",
            all_node_names=["init"],
            max_attempts_map={"init": 3},
        )
        normalizer = EventNormalizer(state, ["init"], max_attempts_map={"init": 3})

        normalizer.node_entered("init")
        assert state.max_attempts_map.get("init") == 3


class TestExecutionStateDirectEvents:
    """Apply events directly to ExecutionState."""

    def test_apply_node_started_event(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])

        state.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="exec-1",
                attempt_number=1,
            )
        )

        assert state._status == ExecutionStatus.RUNNING
        execs = state._executions.get("init", {})
        assert "exec-1" in execs

    def test_apply_node_completed_event(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])

        state.apply(
            NodeStartedEvent(
                node_name="init",
                execution_id="exec-1",
                attempt_number=1,
            )
        )
        state.apply(
            NodeCompletedEvent(
                node_name="init",
                execution_id="exec-1",
                status=NodeStatus.COMPLETED,
            )
        )

        assert state._completed["init"] == NodeStatus.COMPLETED

    def test_apply_quest_completed(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        state.apply(QuestCompletedEvent())
        assert state._status == ExecutionStatus.COMPLETED

    def test_apply_quest_failed(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        state.apply(QuestFailedEvent(reason="error"))
        assert state._status == ExecutionStatus.FAILED

    def test_apply_quest_cancelled(self):
        state = ExecutionState(quest_id="test", title="Test", all_node_names=["init"])
        state.apply(QuestCancelledEvent(reason="cancelled"))
        assert state._status == ExecutionStatus.CANCELLED


class TestThreatEvaluator:
    """Threat level computation based on attempts and resources."""

    def test_low_threat_first_attempt(self):
        from eng_loop.tools.execution_state import ResourceTracker, ThreatEvaluator, ThreatLevel

        resources = ResourceTracker(attempts=1)
        level = ThreatEvaluator.evaluate(resources, attempts_max=3)
        assert level == ThreatLevel.LOW

    def test_critical_threat_near_limit(self):
        from eng_loop.tools.execution_state import ResourceTracker, ThreatEvaluator, ThreatLevel

        resources = ResourceTracker(attempts=3)
        level = ThreatEvaluator.evaluate(resources, attempts_max=3)
        assert level == ThreatLevel.CRITICAL

    def test_high_threat_two_thirds(self):
        """2/3 attempts (0.667) >= 0.6 threshold -> HIGH."""
        from eng_loop.tools.execution_state import ResourceTracker, ThreatEvaluator, ThreatLevel

        resources = ResourceTracker(attempts=2)
        level = ThreatEvaluator.evaluate(resources, attempts_max=3)
        assert level == ThreatLevel.HIGH

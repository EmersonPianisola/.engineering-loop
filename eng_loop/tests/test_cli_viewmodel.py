from __future__ import annotations

import pytest

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
    AttemptRecord,
    ResumeInfo,
)


class TestPipelineStatus:
    def test_all_statuses(self):
        statuses = [
            PipelineStatus.PLANNING,
            PipelineStatus.RUNNING,
            PipelineStatus.PAUSED,
            PipelineStatus.WAITING_FOR_INPUT,
            PipelineStatus.RESUMING,
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
            PipelineStatus.CANCELLED,
        ]
        assert len(statuses) == 8
        # All are strings
        for s in statuses:
            assert isinstance(s.value, str)


class TestNodeVisualStatus:
    def test_all_statuses(self):
        statuses = [
            NodeVisualStatus.PENDING,
            NodeVisualStatus.RUNNING,
            NodeVisualStatus.SUCCESS,
            NodeVisualStatus.WARNING,
            NodeVisualStatus.FAILED,
            NodeVisualStatus.PAUSED,
            NodeVisualStatus.CANCELLED,
        ]
        assert len(statuses) == 7


class TestProgressInfo:
    def test_fraction(self):
        p = ProgressInfo(current=3, total=5)
        assert abs(p.fraction - 0.6) < 0.001

    def test_percentage(self):
        p = ProgressInfo(current=3, total=5)
        assert p.percentage == 60

    def test_zero_total(self):
        p = ProgressInfo(current=0, total=0)
        assert p.fraction == 0.0
        assert p.percentage == 0

    def test_full_progress(self):
        p = ProgressInfo(current=5, total=5)
        assert p.fraction == 1.0
        assert p.percentage == 100


class TestPipelineMetrics:
    def test_defaults(self):
        m = PipelineMetrics()
        assert m.total_nodes == 0
        assert m.completed_nodes == 0
        assert m.retries == 0


class TestGraphNodeInfo:
    def test_defaults(self):
        n = GraphNodeInfo(id="init")
        assert n.id == "init"
        assert n.visual_status == NodeVisualStatus.PENDING
        assert n.is_container is False
        assert n.children == []


class TestExecutionViewModel:
    def test_default_consistent(self):
        vm = ExecutionViewModel()
        violations = vm.assert_consistent()
        assert violations == []

    def test_completed_with_questions_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.COMPLETED,
            essence_gate=EssenceGateInfo(
                questions=[EssenceQuestion(id="q1", severity="high", question="What?")]
            ),
        )
        violations = vm.assert_consistent()
        assert any("COMPLETED with pending" in v for v in violations)

    def test_completed_with_running_nodes_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.COMPLETED,
            metrics=PipelineMetrics(running_nodes=1),
        )
        violations = vm.assert_consistent()
        assert any("COMPLETED with active" in v for v in violations)

    def test_completed_with_failed_nodes_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.COMPLETED,
            metrics=PipelineMetrics(failed_nodes=1),
        )
        violations = vm.assert_consistent()
        assert any("COMPLETED with failed" in v for v in violations)

    def test_waiting_without_questions_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
        )
        violations = vm.assert_consistent()
        assert any("WAITING_FOR_INPUT without" in v for v in violations)

    def test_waiting_with_active_nodes_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
            essence_gate=EssenceGateInfo(
                questions=[EssenceQuestion(id="q1", severity="high", question="What?")]
            ),
            metrics=PipelineMetrics(running_nodes=1),
        )
        violations = vm.assert_consistent()
        assert any("WAITING_FOR_INPUT with active" in v for v in violations)

    def test_progress_exceeds_total_violates(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5),
            progress=ProgressInfo(current=7, total=5),
        )
        violations = vm.assert_consistent()
        assert any("progress.current" in v for v in violations)

    def test_progress_denominator_mismatch_violates(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5),
            progress=ProgressInfo(current=3, total=7),
        )
        violations = vm.assert_consistent()
        assert any("progress.total" in v for v in violations)

    def test_completed_greater_than_total_violates(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5, completed_nodes=7),
        )
        violations = vm.assert_consistent()
        assert any("completed_nodes" in v for v in violations)

    def test_running_without_active_nodes_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RUNNING,
            metrics=PipelineMetrics(running_nodes=0),
        )
        violations = vm.assert_consistent()
        assert any("RUNNING with no active" in v for v in violations)

    def test_valid_completed_state(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.COMPLETED,
            metrics=PipelineMetrics(
                total_nodes=5,
                completed_nodes=5,
                running_nodes=0,
                failed_nodes=0,
            ),
            progress=ProgressInfo(current=5, total=5),
        )
        violations = vm.assert_consistent()
        assert violations == []

    def test_valid_waiting_state(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
            essence_gate=EssenceGateInfo(
                stage="post",
                questions=[EssenceQuestion(id="q1", severity="high", question="What?")],
            ),
            metrics=PipelineMetrics(running_nodes=0),
        )
        violations = vm.assert_consistent()
        assert violations == []

    def test_valid_running_state(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RUNNING,
            metrics=PipelineMetrics(total_nodes=5, running_nodes=1),
            progress=ProgressInfo(current=2, total=5),
        )
        violations = vm.assert_consistent()
        assert violations == []


class TestEssenceQuestion:
    def test_choice_type(self):
        q = EssenceQuestion(
            id="q1",
            severity="high",
            question="What type?",
            options=["vanilla", "chocolate"],
        )
        assert q.input_type == "text"  # default
        assert len(q.options) == 2


class TestResumeInfo:
    def test_defaults(self):
        r = ResumeInfo()
        assert r.clarifications_applied == 0
        assert r.invalidated_stages == []
        assert r.preserved_stages == []


class TestCheckpointInfo:
    def test_defaults(self):
        c = CheckpointInfo()
        assert c.completed_nodes == []
        assert c.active_node is None


class TestDiagnosticEntry:
    def test_creation(self):
        d = DiagnosticEntry(severity="ERROR", message="Something failed", node_id="init")
        assert d.severity == "ERROR"
        assert d.node_id == "init"

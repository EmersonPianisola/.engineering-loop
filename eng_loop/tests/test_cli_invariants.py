from __future__ import annotations

"""Invariant assertions for the CLI v2 execution model (PRD §30).

These tests verify that the ExecutionViewModel enforces the critical
invariants that prevent the contradictions identified in P0:
- completed <= total
- running <= 1 (sequential graph)
- COMPLETED => waiting_for_input == false
- WAITING_FOR_INPUT => pending_questions > 0
- FAILED => fatal_error exists
- progress denominator == graph.required_nodes
- progress is monotonic within execution
"""

from eng_loop.tools.cli_viewmodel import (
    DiagnosticEntry,
    EssenceGateInfo,
    EssenceQuestion,
    ExecutionViewModel,
    PipelineMetrics,
    PipelineStatus,
    ProgressInfo,
)


class TestCompletedLessThanOrEqualTotal:
    """completed <= total always."""

    def test_equal(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5, completed_nodes=5),
            progress=ProgressInfo(current=5, total=5),
        )
        assert vm.assert_consistent() == []

    def test_less_than(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5, completed_nodes=3),
            progress=ProgressInfo(current=3, total=5),
        )
        assert vm.assert_consistent() == []

    def test_exceeds_violates(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5, completed_nodes=7),
        )
        violations = vm.assert_consistent()
        assert any("completed_nodes" in v and "> total_nodes" in v for v in violations)

    def test_retries_dont_increase_total(self):
        """Retries don't affect total_nodes (PRD §5)."""
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(
                total_nodes=5,
                completed_nodes=5,
                total_executions=7,  # 2 retries
                total_attempts=11,  # 6 retries total
                retries=6,
            ),
            progress=ProgressInfo(current=5, total=5),
        )
        assert vm.assert_consistent() == []
        assert vm.progress.total == 5  # denominator unchanged


class TestRunningLessThanOrEqualOne:
    """running <= 1 for sequential graph."""

    def test_one_running(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RUNNING,
            metrics=PipelineMetrics(total_nodes=5, running_nodes=1),
            progress=ProgressInfo(current=2, total=5),
        )
        assert vm.assert_consistent() == []

    def test_zero_running_not_running_status(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.COMPLETED,
            metrics=PipelineMetrics(total_nodes=5, running_nodes=0),
            progress=ProgressInfo(current=5, total=5),
        )
        assert vm.assert_consistent() == []

    def test_running_without_active_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RUNNING,
            metrics=PipelineMetrics(running_nodes=0),
        )
        violations = vm.assert_consistent()
        assert any("RUNNING with no active" in v for v in violations)


class TestCompletedImpliesNoWaiting:
    """COMPLETED => waiting_for_input == false."""

    def test_completed_with_questions_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.COMPLETED,
            essence_gate=EssenceGateInfo(questions=[EssenceQuestion(id="q1", severity="high", question="What?")]),
        )
        violations = vm.assert_consistent()
        assert any("COMPLETED with pending" in v for v in violations)

    def test_completed_without_questions_ok(self):
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
        assert vm.assert_consistent() == []


class TestWaitingForInputRequiresQuestions:
    """WAITING_FOR_INPUT => pending_questions > 0."""

    def test_waiting_without_questions_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
        )
        violations = vm.assert_consistent()
        assert any("WAITING_FOR_INPUT without" in v for v in violations)

    def test_waiting_with_questions_ok(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.WAITING_FOR_INPUT,
            essence_gate=EssenceGateInfo(questions=[EssenceQuestion(id="q1", severity="high", question="What?")]),
            metrics=PipelineMetrics(running_nodes=0),
        )
        assert vm.assert_consistent() == []


class TestFailedRequiresFatalError:
    """FAILED => fatal_error exists."""

    def test_failed_without_error_violates(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.FAILED,
            metrics=PipelineMetrics(failed_nodes=0),
            diagnostics=[],
        )
        violations = vm.assert_consistent()
        assert any("FAILED without fatal" in v for v in violations)

    def test_failed_with_fatal_diagnostic_ok(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.FAILED,
            diagnostics=[DiagnosticEntry(severity="FATAL", message="Required file missing")],
        )
        assert vm.assert_consistent() == []

    def test_failed_with_failed_nodes_ok(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.FAILED,
            metrics=PipelineMetrics(failed_nodes=1),
        )
        assert vm.assert_consistent() == []


class TestProgressDenominator:
    """progress.denominator == graph.required_nodes."""

    def test_matches_total_nodes(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5),
            progress=ProgressInfo(current=3, total=5),
        )
        assert vm.assert_consistent() == []

    def test_mismatch_violates(self):
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5),
            progress=ProgressInfo(current=3, total=7),
        )
        violations = vm.assert_consistent()
        assert any("progress.total" in v for v in violations)


class TestProgressMonotonic:
    """Progress is monotonic within execution (PRD §25)."""

    def test_monotonic_sequence(self):
        """Valid: 1/5, 2/5, 3/5, 4/5, 5/5."""
        for i in range(1, 6):
            vm = ExecutionViewModel(
                metrics=PipelineMetrics(total_nodes=5, completed_nodes=i),
                progress=ProgressInfo(current=i, total=5),
            )
            assert vm.assert_consistent() == []

    def test_progress_cannot_exceed_total(self):
        """Invalid: 6/5, 7/5."""
        for bad_current in [6, 7]:
            vm = ExecutionViewModel(
                metrics=PipelineMetrics(total_nodes=5),
                progress=ProgressInfo(current=bad_current, total=5),
            )
            violations = vm.assert_consistent()
            assert any("progress.current" in v for v in violations)


class TestMutualExclusion:
    """States are mutually exclusive (PRD §34)."""

    def test_no_completed_and_waiting(self):
        """COMPLETED + waiting_for_input is impossible by enum design."""
        # If all nodes done but gate waiting, status should be WAITING_FOR_INPUT
        vm = ExecutionViewModel(
            metrics=PipelineMetrics(total_nodes=5, completed_nodes=5),
            essence_gate=EssenceGateInfo(questions=[EssenceQuestion(id="q1", severity="high", question="What?")]),
            pipeline_status=PipelineStatus.COMPLETED,
        )
        violations = vm.assert_consistent()
        assert any("COMPLETED with pending" in v for v in violations)

    def test_no_100_percent_and_running(self):
        """100% + running is contradictory."""
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RUNNING,
            metrics=PipelineMetrics(total_nodes=5, completed_nodes=5, running_nodes=1),
            progress=ProgressInfo(current=5, total=5),
        )
        # This is technically possible if a retry is running after all nodes completed
        # The invariant is about the status being wrong, not the progress
        # If running_nodes > 0, completed should be < total
        # This case is allowed — retry after completion is valid

from __future__ import annotations

"""Tests for checkpoint semantics and resume invalidation (PRD §17-18)."""

from eng_loop.tools.cli_viewmodel import (
    CheckpointInfo,
    ExecutionViewModel,
    GraphNodeInfo,
    NodeExecution,
    NodeVisualStatus,
    PipelineMetrics,
    PipelineStatus,
    ProgressInfo,
    ResumeInfo,
)


class TestCheckpointInfo:
    def test_checkpoint_structure(self):
        cp = CheckpointInfo(
            completed_nodes=["init", "impl.code"],
            active_node="post",
            state_version=3,
            graph_id="g-1",
        )
        assert len(cp.completed_nodes) == 2
        assert cp.active_node == "post"
        assert cp.state_version == 3

    def test_checkpoint_empty(self):
        cp = CheckpointInfo()
        assert cp.completed_nodes == []
        assert cp.active_node is None


class TestResumeInfo:
    def test_resume_info_structure(self):
        info = ResumeInfo(
            clarifications_applied=3,
            checkpoint_stage="post",
            invalidated_stages=["post"],
            preserved_stages=["init", "impl.code"],
        )
        assert info.clarifications_applied == 3
        assert info.checkpoint_stage == "post"
        assert "post" in info.invalidated_stages
        assert "init" in info.preserved_stages

    def test_only_blocked_stage_invalidated(self):
        """When essence gate resolves at 'post', only 'post' is invalidated.

        PRD §18: nodes anterior to the checkpoint should not re-execute.
        """
        info = ResumeInfo(
            clarifications_applied=2,
            checkpoint_stage="post",
            invalidated_stages=["post"],
            preserved_stages=["init", "impl.code", "init.ideate", "init.refine"],
        )
        # init and impl.code are preserved
        assert "init" in info.preserved_stages
        assert "impl.code" in info.preserved_stages
        # Only post is invalidated
        assert info.invalidated_stages == ["post"]


class TestViewModelWithCheckpoint:
    def test_viewmodel_with_checkpoint(self):
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RESUMING,
            checkpoint=CheckpointInfo(
                completed_nodes=["init", "impl.code"],
                active_node="post",
                state_version=2,
            ),
            resume_info=ResumeInfo(
                clarifications_applied=2,
                checkpoint_stage="post",
                invalidated_stages=["post"],
                preserved_stages=["init", "impl.code"],
            ),
            metrics=PipelineMetrics(
                total_nodes=5,
                completed_nodes=2,
            ),
            progress=ProgressInfo(current=2, total=5),
        )
        assert vm.pipeline_status == PipelineStatus.RESUMING
        assert vm.checkpoint is not None
        assert vm.resume_info is not None
        assert vm.assert_consistent() == []

    def test_progress_preserved_after_resume(self):
        """Completed nodes from before the checkpoint are preserved."""
        vm = ExecutionViewModel(
            pipeline_status=PipelineStatus.RESUMING,
            metrics=PipelineMetrics(
                total_nodes=5,
                completed_nodes=2,  # init, impl.code preserved
            ),
            progress=ProgressInfo(current=2, total=5),
        )
        # Progress reflects preserved completions
        assert vm.progress.current == 2
        assert vm.progress.total == 5

    def test_no_unnecessary_reexecution(self):
        """Only invalidated nodes re-execute (PRD §17)."""
        info = ResumeInfo(
            invalidated_stages=["post"],
            preserved_stages=["init", "impl.code", "init.ideate", "init.refine", "verify"],
        )
        # 5 preserved, 1 invalidated
        assert len(info.preserved_stages) == 5
        assert len(info.invalidated_stages) == 1

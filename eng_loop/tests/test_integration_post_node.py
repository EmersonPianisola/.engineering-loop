from __future__ import annotations

"""Integration tests for post node honest status propagation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from eng_loop.nodes.post import post_node
from eng_loop.state import make_initial_state


class TestPostNodeHonestStatus:
    def _make_state(self, **kwargs) -> tuple[dict, str]:
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        state = make_initial_state(
            {},
            {
                "artifact_root": artifact_root,
                "project_root": tmp,
                "framework_stage_root": "stages",
            },
        )
        state["complexity"] = "small"
        state["ui_project"] = False
        state["work_type"] = "documentation"
        state["work_item"] = {
            "title": "Test",
            "acceptance_criteria": ["Criterion 1"],
            "code_map": ["artifacts/test-output.md"],
        }
        state["stages"]["init"]["done"] = True
        state["stages"]["init"]["attempts"] = 1
        state["stages"]["impl.code"]["done"] = True
        state["stages"]["impl.code"]["attempts"] = 1
        state["config"] = {
            "agent": {"max_agent_iterations": 5},
            "lessons": {"enabled": False},
        }
        state.update(kwargs)
        return state, tmp

    def _mock_agent_result(self, data: dict, error: str | None = None) -> MagicMock:
        mock = MagicMock()
        mock.data = data
        mock.error = error
        return mock

    def test_post_node_returns_failed_on_agent_error(self):
        """When the post agent errors, status should be 'failed', not 'done'."""
        state, tmp = self._make_state()
        mock_result = self._mock_agent_result({}, "agent_stalled: read loop detected")

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            cmd = post_node(state)

        assert cmd.update["status"] == "failed"
        assert cmd.update["task_outcome"] == "failed"
        assert cmd.goto == "__end__"

    def test_post_node_returns_done_on_success(self):
        """When the post agent succeeds, status should be 'done'."""
        state, tmp = self._make_state()
        mock_result = self._mock_agent_result(
            {
                "summary": "All tasks completed successfully",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 0,
            }
        )

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            cmd = post_node(state)

        assert cmd.update["status"] == "done"
        assert cmd.update["task_outcome"] == "done"

    def test_post_node_returns_partial_on_incomplete_stages(self):
        """When some stages are incomplete, status should be 'partial'."""
        state, tmp = self._make_state()
        state["stages"]["impl.code"]["done"] = False
        state["stages"]["impl.code"]["attempts"] = 3

        mock_result = self._mock_agent_result(
            {
                "summary": "Some work completed",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 0,
            }
        )

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            cmd = post_node(state)

        assert cmd.update["status"] == "partial"

    def test_post_node_returns_done_with_warnings_on_retries(self):
        """When stages retried but completed, status should include warnings."""
        state, tmp = self._make_state()
        state["stages"]["init"]["attempts"] = 2
        state["stages"]["impl.code"]["attempts"] = 2

        mock_result = self._mock_agent_result(
            {
                "summary": "Completed with retries",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 0,
            }
        )

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            cmd = post_node(state)

        assert cmd.update["status"] == "done_with_warnings"

    def test_post_node_skips_if_already_done(self):
        """If post stage is already done, skip to end."""
        state, tmp = self._make_state()
        state["stages"]["post"]["done"] = True

        cmd = post_node(state)
        assert cmd.goto == "__end__"

    def test_post_node_builds_artifact_evidence(self):
        """Post node should track artifact evidence."""
        state, tmp = self._make_state()
        artifact_root = state["paths"]["artifact_root"]

        # Create an expected artifact
        expected_path = os.path.join(artifact_root, "test-output.md")
        Path(expected_path).write_text("test content", encoding="utf-8")

        # Use absolute path in code_map so os.path.exists works
        state["work_item"]["code_map"] = [expected_path]

        mock_result = self._mock_agent_result(
            {
                "summary": "Done",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 0,
            }
        )

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            cmd = post_node(state)

        evidence = cmd.update.get("artifact_evidence", {})
        assert expected_path in evidence
        assert evidence[expected_path]["exists"] is True

    def test_post_node_tracks_missing_artifacts(self):
        """Post node should detect missing artifacts."""
        state, tmp = self._make_state()
        state["work_item"] = {
            "title": "Test",
            "acceptance_criteria": ["Criterion 1"],
            "code_map": ["artifacts/nonexistent.md"],
        }

        mock_result = self._mock_agent_result(
            {
                "summary": "Done",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 0,
            }
        )

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            cmd = post_node(state)

        evidence = cmd.update.get("artifact_evidence", {})
        assert "artifacts/nonexistent.md" in evidence
        assert evidence["artifacts/nonexistent.md"]["exists"] is False

    def test_post_node_writes_summary_artifact(self):
        """Post node writes summary to post-loop-summary.md."""
        state, tmp = self._make_state()
        artifact_root = state["paths"]["artifact_root"]

        mock_result = self._mock_agent_result(
            {
                "summary": "Test summary content",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 0,
            }
        )

        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.nodes.post.create_model_from_config"),
        ):
            post_node(state)

        summary_path = os.path.join(artifact_root, "post-loop-summary.md")
        assert os.path.exists(summary_path)
        assert Path(summary_path).read_text(encoding="utf-8") == "Test summary content"

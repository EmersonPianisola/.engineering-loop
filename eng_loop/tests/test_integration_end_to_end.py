from __future__ import annotations

"""End-to-end integration tests simulating full pipeline execution."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from eng_loop.graph_builder import GraphBuilder
from eng_loop.nodes.post import post_node
from eng_loop.schemas import (
    EdgeDefinition,
    GraphTopologyProposal,
    PhaseGroup,
)
from eng_loop.state import compute_task_outcome, make_initial_state, make_stage
from eng_loop.tools.autosizing import classify_work_type, deactivate_for_work_type
from eng_loop.tools.policy_resolver import authorize_topology


class TestEndToEndDocumentationPipeline:
    def _setup(self):
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        state = make_initial_state({}, {
            "artifact_root": artifact_root,
            "project_root": tmp,
            "framework_stage_root": "stages",
        })
        state["complexity"] = "small"
        state["ui_project"] = False
        state["work_type"] = "documentation"
        state["work_item"] = {
            "title": "Write Project Summary",
            "intent": "Create project summary document",
            "acceptance_criteria": [
                "1. Read and analyze key project files",
                "2. Create artifacts/project-summary.md",
                "3. Summary should be concise but informative",
            ],
            "code_map": ["artifacts/project-summary.md"],
        }
        state["config"] = {
            "agent": {"max_agent_iterations": 5},
            "lessons": {"enabled": False},
        }
        return state, tmp, artifact_root

    def _mock_agent_result(self, data: dict, error: str | None = None) -> MagicMock:
        mock = MagicMock()
        mock.data = data
        mock.error = error
        return mock

    def test_full_documentation_pipeline_success(self):
        """Full pipeline: classify -> propose -> build -> execute -> verify."""
        state, tmp, artifact_root = self._setup()

        # Step 1: Work type classification
        work_type = classify_work_type(state["work_item"]["title"])
        assert work_type == "documentation"

        # Step 2: Stage deactivation for work type
        deactivated = deactivate_for_work_type(state["stages"], "documentation")
        assert deactivated["impl.design"]["done"] is True
        assert deactivated["verify"]["done"] is True
        assert deactivated["impl.code"]["done"] is False

        # Step 3: Topology proposal
        proposal = GraphTopologyProposal(
            plan_id="doc-pipeline",
            work_type="documentation",
            complexity="small",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Documentation pipeline",
        )

        authorized = authorize_topology(proposal, state)
        assert "impl.code" in authorized.authorized_stages

        # Step 4: Graph build
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        assert "init" in topology.active_nodes
        assert "impl.code" in topology.active_nodes
        assert "post" in topology.active_nodes
        assert "verify" not in topology.active_nodes
        assert "impl.design" not in topology.active_nodes

        # Step 5: Simulate post node with success
        mock_result = self._mock_agent_result({
            "summary": "Pipeline completed successfully",
            "final_status": "done",
            "complete": True,
            "lessons_to_share": 0,
        })

        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            with patch("eng_loop.nodes.post.create_model_from_config"):
                cmd = post_node(state)

        assert cmd.update["status"] == "done"
        assert cmd.update["task_outcome"] == "done"

    def test_full_documentation_pipeline_failure(self):
        """Full pipeline with post failure should report FAILED."""
        state, tmp, artifact_root = self._setup()

        mock_result = self._mock_agent_result({}, "agent_stalled: read loop detected")

        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            with patch("eng_loop.nodes.post.create_model_from_config"):
                cmd = post_node(state)

        assert cmd.update["status"] == "failed"
        assert cmd.update["task_outcome"] == "failed"

    def test_full_pipeline_artifact_verification(self):
        """Pipeline verifies artifact was actually created."""
        state, tmp, artifact_root = self._setup()

        # Create the expected artifact
        artifact_path = os.path.join(artifact_root, "project-summary.md")
        Path(artifact_path).write_text("# Project Summary\n\nContent here.", encoding="utf-8")

        # Use absolute path in code_map
        state["work_item"]["code_map"] = [artifact_path]

        mock_result = self._mock_agent_result({
            "summary": "Artifact created and verified",
            "final_status": "done",
            "complete": True,
            "lessons_to_share": 0,
        })

        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            with patch("eng_loop.nodes.post.create_model_from_config"):
                cmd = post_node(state)

        evidence = cmd.update.get("artifact_evidence", {})
        assert artifact_path in evidence
        assert evidence[artifact_path]["exists"] is True


class TestEndToEndOperationalPipeline:
    def test_operational_excludes_impl_code(self):
        """Operational tasks should exclude impl.code."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        state = make_initial_state({}, {
            "artifact_root": artifact_root,
            "project_root": tmp,
            "framework_stage_root": "stages",
        })
        state["complexity"] = "small"
        state["ui_project"] = False
        state["work_type"] = "operational"
        state["config"] = {"agent": {"max_agent_iterations": 5}, "lessons": {"enabled": False}}

        proposal = GraphTopologyProposal(
            plan_id="ops-pipeline",
            work_type="operational",
            complexity="small",
            required_stages=("init", "impl.code", "post"),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="IMPL", stages=("impl.code",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Operational pipeline",
        )

        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        assert "impl.code" not in topology.active_nodes
        assert "init" in topology.active_nodes
        assert "post" in topology.active_nodes


class TestEndToEndFeaturePipeline:
    def test_feature_includes_all_stages(self):
        """Feature tasks should include all applicable stages."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        state = make_initial_state({}, {
            "artifact_root": artifact_root,
            "project_root": tmp,
            "framework_stage_root": "stages",
        })
        state["complexity"] = "medium"
        state["ui_project"] = False
        state["work_type"] = "feature"
        state["config"] = {"agent": {"max_agent_iterations": 5}, "lessons": {"enabled": False}}

        proposal = GraphTopologyProposal(
            plan_id="feature-pipeline",
            work_type="feature",
            complexity="medium",
            required_stages=(
                "init", "arch.requirements", "impl.design",
                "impl.code", "doc.update", "verify", "post",
            ),
            edges=(
                EdgeDefinition(from_stage="init", to_stage="arch.requirements", edge_type="fixed"),
                EdgeDefinition(from_stage="arch.requirements", to_stage="impl.design", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.design", to_stage="impl.code", edge_type="fixed"),
                EdgeDefinition(from_stage="impl.code", to_stage="doc.update", edge_type="fixed"),
                EdgeDefinition(from_stage="doc.update", to_stage="verify", edge_type="fixed"),
                EdgeDefinition(from_stage="verify", to_stage="post", edge_type="fixed"),
            ),
            phase_groups=(
                PhaseGroup(name="INIT", stages=("init",)),
                PhaseGroup(name="ARCH", stages=("arch.requirements",)),
                PhaseGroup(name="IMPL", stages=("impl.design", "impl.code", "doc.update")),
                PhaseGroup(name="VERIFY", stages=("verify",)),
                PhaseGroup(name="POST", stages=("post",)),
            ),
            rationale="Feature pipeline",
        )

        authorized = authorize_topology(proposal, state)
        builder = GraphBuilder()
        _graph, topology = builder.build(state, authorized_topology=authorized)

        assert "init" in topology.active_nodes
        assert "arch.requirements" in topology.active_nodes
        assert "impl.design" in topology.active_nodes
        assert "impl.code" in topology.active_nodes
        assert "verify" in topology.active_nodes
        assert "post" in topology.active_nodes


class TestEndToEndStatusIntegrity:
    def test_status_cannot_be_done_when_post_failed(self):
        """DONE is impossible when post stage failed."""
        stages = {
            "init": make_stage(), "impl.code": make_stage(),
            "verify": make_stage(), "post": make_stage(),
        }
        for sid in stages:
            stages[sid]["done"] = True
            stages[sid]["attempts"] = 1
        stages["post"]["output"] = json.dumps({
            "summary": "Artifact missing",
            "final_status": "failed",
        })

        outcome = compute_task_outcome(stages, "failed")
        assert outcome == "failed"

    def test_status_cannot_be_done_when_stages_incomplete(self):
        """DONE is impossible when active stages are incomplete."""
        stages = {
            "init": make_stage(), "impl.code": make_stage(), "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["done"] = False
        stages["impl.code"]["attempts"] = 3
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        outcome = compute_task_outcome(stages, "done")
        assert outcome == "partial"

    def test_status_done_with_warnings_on_retries(self):
        """Warnings are reported when stages retried."""
        stages = {
            "init": make_stage(), "impl.code": make_stage(),
            "verify": make_stage(), "post": make_stage(),
        }
        for sid in stages:
            stages[sid]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["attempts"] = 3
        stages["verify"]["attempts"] = 2
        stages["post"]["attempts"] = 1

        outcome = compute_task_outcome(stages, "done")
        assert outcome == "done_with_warnings"

    def test_clean_done_when_all_succeed_first_attempt(self):
        """Clean DONE when everything succeeds on first attempt."""
        stages = {
            "init": make_stage(), "impl.code": make_stage(), "post": make_stage(),
        }
        for sid in stages:
            stages[sid]["done"] = True
            stages[sid]["attempts"] = 1

        outcome = compute_task_outcome(stages, "done")
        assert outcome == "done"

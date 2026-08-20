from __future__ import annotations

"""Integration tests: node handler critical paths.

Validates critical execution paths through node handlers:
  - impl.code fix-mode loop
  - verify PASS/FAIL routing
  - qa-dispatcher fan-out with Send API
  - qa-join fan-in with gap aggregation
  - meta-executor step cursor advancement
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from langgraph.types import Command

from eng_loop.nodes.qa_parallel import (
    COMPLEXITY_ORDER,
    QA_STAGE_DEFINITIONS,
    _get_active_qa_nodes,
    qa_dispatcher_node,
    qa_join_node,
)
from eng_loop.state import make_initial_state, rollback_to_stage
from eng_loop.tools.agent_runner import AgentResult


def _make_state(
    complexity: str = "small",
    ui_project: bool = False,
    work_type: str = "feature",
    work_item: str = "Add new feature",
    stages_override: dict | None = None,
    extra: dict | None = None,
) -> dict:
    tmpdir = tempfile.mkdtemp()
    artifact_root = str(Path(tmpdir) / "artifacts")
    state = make_initial_state(
        {"constraints": {}, "agent": {"max_agent_iterations": 5}, "lessons": {"enabled": False}},
        {"project_root": tmpdir, "artifact_root": artifact_root},
    )
    state["complexity"] = complexity
    state["ui_project"] = ui_project
    state["work_type"] = work_type
    state["work_item"] = work_item
    state["_tmpdir"] = tmpdir
    if stages_override:
        for k, v in stages_override.items():
            state["stages"][k] = dict(state["stages"].get(k, {}), **v)
    if extra:
        state.update(extra)
    return state


def _mark_done(state: dict, stage_id: str) -> dict:
    stages = {k: dict(v) for k, v in state["stages"].items()}
    stages[stage_id] = dict(stages[stage_id], done=True, attempts=max(stages[stage_id].get("attempts", 0), 1))
    return dict(state, stages=stages, current_stage=stage_id)


def _apply_update(state: dict, update: dict) -> dict:
    result = dict(state)
    for k, v in update.items():
        if k == "stages" and isinstance(v, dict):
            merged = {sk: dict(sv) for sk, sv in state.get("stages", {}).items()}
            for sk, sv in v.items():
                if isinstance(sv, dict):
                    merged[sk] = dict(merged.get(sk, {}), **sv)
                else:
                    merged[sk] = sv
            result[k] = merged
        else:
            result[k] = v
    return result


class TestImplCodeNode:
    """impl.code node: code generation, fix-mode, test execution."""

    def test_impl_code_success_routes_to_doc_update(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "implementation_summary": "Implemented the feature with comprehensive test coverage and full documentation",
                "files_created": ["src/main.py", "tests/test_main.py"],
                "tests_passed": True,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.implementation import impl_code_node

            state = _make_state("small")
            result = impl_code_node(state)
            assert isinstance(result, Command)
            assert result.goto == "doc-update"

    def test_impl_code_fail_routes_to_retry(self):
        mock_result = AgentResult(
            data={
                "complete": False,
                "implementation_summary": "Short",
                "files_created": [],
                "tests_passed": False,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.implementation import impl_code_node

            state = _make_state("small")
            result = impl_code_node(state)
            assert isinstance(result, Command)
            assert result.goto == "impl-code"

    def test_impl_code_max_attempts_blocks(self):
        mock_result = AgentResult(
            data={
                "complete": False,
                "implementation_summary": "Short",
                "files_created": [],
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.implementation import impl_code_node

            state = _make_state("small")
            state["stages"]["impl.code"]["attempts"] = 3
            state["stages"]["impl.code"]["done"] = False
            state["current_stage"] = "impl.code"
            state["config"]["constraints"] = {"max_impl_code_attempts": 3}

            result = impl_code_node(state)
            assert isinstance(result, Command)
            assert result.goto == "__end__"

    def test_impl_code_fix_mode_with_qa_gaps(self):
        """impl.code receives fix_tasks from qa-join rollback."""
        mock_result = AgentResult(
            data={
                "complete": True,
                "implementation_summary": "Fixed the QA issues with comprehensive test coverage and documentation",
                "files_created": ["src/fix.py"],
                "tests_passed": True,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.implementation import impl_code_node

            state = _make_state("medium")
            state["fix_tasks"] = [{"source": "qa.security", "gap": "SQL injection", "severity": "critical"}]
            state["fix_iteration"] = 1
            result = impl_code_node(state)
            assert isinstance(result, Command)
            assert result.goto == "doc-update"


class TestVerifyNode:
    """verify node: PASS/FAIL verdict routing."""

    def test_verify_pass_routes_to_qa_or_deploy(self):
        mock_result = AgentResult(
            data={
                "verdict": "PASS",
                "tests_passed": True,
                "per_ac_evidence": ["AC1 -> file.py:10", "AC2 -> file.py:20"],
                "gaps": [],
                "discrimination_sensor": "pass",
                "coverage_audit": "pass",
            }
        )
        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.tools.file_ops.write_file"),
        ):
            from eng_loop.nodes.verification import verify_node

            state = _make_state("small")
            state = _mark_done(state, "impl.code")
            state = _mark_done(state, "doc.update")
            result = verify_node(state)
            assert isinstance(result, Command)
            assert result.goto == "qa-static"

    def test_verify_fail_routes_to_impl_code(self):
        mock_result = AgentResult(
            data={
                "verdict": "FAIL",
                "tests_passed": False,
                "per_ac_evidence": [],
                "gaps": ["missing test coverage for edge case"],
                "discrimination_sensor": "pass",
                "coverage_audit": "fail",
            }
        )
        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.tools.file_ops.write_file"),
        ):
            from eng_loop.nodes.verification import verify_node

            state = _make_state("small")
            state["stages"]["verify"]["attempts"] = 1
            result = verify_node(state)
            assert isinstance(result, Command)
            assert result.goto == "impl-code"

    def test_verify_max_attempts_blocks(self):
        mock_result = AgentResult(
            data={
                "verdict": "FAIL",
                "gaps": ["persistent issue"],
            }
        )
        with (
            patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result),
            patch("eng_loop.tools.file_ops.write_file"),
        ):
            from eng_loop.nodes.verification import verify_node

            state = _make_state("small")
            state["stages"]["verify"]["attempts"] = 3
            state["stages"]["verify"]["done"] = False
            state["current_stage"] = "verify"
            state["config"]["constraints"] = {"max_verify_attempts": 3}

            result = verify_node(state)
            assert isinstance(result, Command)
            assert result.goto == "__end__"


class TestQADispatcherNode:
    """qa-dispatcher: fan-out with Send API."""

    def test_small_complexity_base_qa(self):
        state = _make_state("small")
        active = _get_active_qa_nodes(state)
        assert "qa-static" in active
        assert "qa-unit" in active
        assert "qa-integration" not in active

    def test_medium_complexity_fans_out(self):
        state = _make_state("medium")
        result = qa_dispatcher_node(state)
        assert isinstance(result, Command)
        assert isinstance(result.goto, list)
        node_names = [s.node for s in result.goto]
        assert "qa-static" in node_names
        assert "qa-unit" in node_names
        assert "qa-integration" in node_names
        assert "qa-security" in node_names
        assert "qa-performance" not in node_names

    def test_complex_complexity_all_qa(self):
        state = _make_state("complex")
        result = qa_dispatcher_node(state)
        assert isinstance(result, Command)
        assert isinstance(result.goto, list)
        node_names = [s.node for s in result.goto]
        assert "qa-static" in node_names
        assert "qa-unit" in node_names
        assert "qa-integration" in node_names
        assert "qa-security" in node_names
        assert "qa-performance" in node_names
        assert "qa-human-flow" in node_names

    def test_active_qa_nodes_by_complexity(self):
        state = _make_state("small")
        active = _get_active_qa_nodes(state)
        assert "qa-static" in active
        assert "qa-unit" in active
        assert "qa-integration" not in active

        state = _make_state("medium")
        active = _get_active_qa_nodes(state)
        assert "qa-security" in active
        assert "qa-integration" in active
        assert "qa-human-flow" in active

        state = _make_state("complex")
        active = _get_active_qa_nodes(state)
        assert "qa-security" in active
        assert "qa-performance" in active
        assert "qa-human-flow" in active


class TestQAJoinNode:
    """qa-join: fan-in with gap aggregation."""

    @staticmethod
    def _set_all_qa_pass(state):
        """Set all active QA nodes to PASS for clean test setup."""
        from eng_loop.nodes.qa_parallel import _get_active_qa_nodes

        active = _get_active_qa_nodes(state)
        for qa_node in active:
            qa_id = qa_node.replace("-", ".", 1)
            # Heuristic stages need friction_score and confidence in output
            if qa_id in ("qa.human.flow", "qa.human.ux"):
                state["stages"][qa_id] = dict(
                    state["stages"].get(qa_id, {}),
                    done=True,
                    verdict="PASS",
                    attempts=1,
                    output=json.dumps({"verdict": "PASS", "friction_score": 2.0, "confidence": 0.9}),
                )
            else:
                state["stages"][qa_id] = dict(
                    state["stages"].get(qa_id, {}),
                    done=True,
                    verdict="PASS",
                    attempts=1,
                )

    def test_all_qa_pass_routes_to_deploy(self):
        state = _make_state("medium")
        self._set_all_qa_pass(state)

        result = qa_join_node(state)
        assert isinstance(result, Command)
        assert result.goto == "deploy-prepare"

    def test_one_qa_fail_rolls_back_to_impl_code(self):
        state = _make_state("medium")
        self._set_all_qa_pass(state)
        state["stages"]["qa.security"] = dict(
            state["stages"]["qa.security"],
            done=True,
            verdict="FAIL",
            severity="critical",
            output=json.dumps({"findings": ["SQL injection vulnerability"], "verdict": "FAIL", "severity": "critical"}),
        )

        result = qa_join_node(state)
        assert isinstance(result, Command)
        assert result.goto == "impl-code"
        assert "fix_tasks" in result.update
        assert len(result.update["fix_tasks"]) > 0

    def test_all_qa_fail_aggregates_all_gaps(self):
        state = _make_state("medium")
        self._set_all_qa_pass(state)
        fail_security = json.dumps(
            {"findings": ["SQL injection", "XSS vulnerability"], "verdict": "FAIL", "severity": "critical"}
        )
        state["stages"]["qa.security"] = dict(
            state["stages"]["qa.security"],
            done=True,
            verdict="FAIL",
            severity="critical",
            attempts=1,
            output=fail_security,
        )

        result = qa_join_node(state)
        assert isinstance(result, Command)
        assert result.goto == "impl-code"
        fix_tasks = result.update["fix_tasks"]
        assert len(fix_tasks) >= 2

    def test_qa_blocked_halts_pipeline(self):
        state = _make_state("medium")
        self._set_all_qa_pass(state)
        state["stages"]["qa.security"] = dict(
            state["stages"]["qa.security"],
            status="blocked",
        )

        result = qa_join_node(state)
        assert isinstance(result, Command)
        assert result.goto == "__end__"
        assert result.update["status"] == "blocked"

    def test_fix_iteration_limit_blocks(self):
        state = _make_state("medium")
        self._set_all_qa_pass(state)
        state["fix_iteration"] = 3
        state["config"]["constraints"] = {"max_fix_iterations": 3}
        state["stages"]["qa.security"] = dict(
            state["stages"]["qa.security"],
            done=True,
            verdict="FAIL",
            severity="critical",
            output=json.dumps({"findings": ["persistent issue"], "verdict": "FAIL", "severity": "critical"}),
        )

        result = qa_join_node(state)
        assert isinstance(result, Command)
        assert result.goto == "__end__"
        assert result.update["status"] == "blocked"

    def test_no_active_qa_routes_to_deploy(self):
        state = _make_state("small")
        # Small complexity now has qa-static and qa-unit active
        self._set_all_qa_pass(state)
        result = qa_join_node(state)
        assert isinstance(result, Command)
        assert result.goto == "deploy-prepare"

    def test_qa_verdict_from_output_json(self):
        """QA verdict is parsed from JSON output when not in stage metadata."""
        state = _make_state("medium")
        self._set_all_qa_pass(state)
        state["stages"]["qa.security"] = dict(
            state["stages"]["qa.security"],
            done=True,
            verdict="",
            output=json.dumps({"verdict": "FAIL", "findings": ["issue"], "severity": "critical"}),
        )

        result = qa_join_node(state)
        assert result.goto == "impl-code"


class TestRollbackToStage:
    """rollback_to_stage resets stages for fix loop."""

    def test_rollback_resets_from_target(self):
        stages = {
            "impl.code": {"done": True, "attempts": 1},
            "doc.update": {"done": True, "attempts": 1},
            "verify": {"done": True, "attempts": 1},
            "qa.security": {"done": True, "attempts": 1},
        }
        result = rollback_to_stage(stages, "qa-security", reset_from="impl.code")
        assert result["impl.code"]["done"] is False
        assert result["doc.update"]["done"] is False

    def test_rollback_preserves_earlier_stages(self):
        stages = {
            "init": {"done": True, "attempts": 1},
            "impl.design": {"done": True, "attempts": 1},
            "impl.code": {"done": True, "attempts": 1},
        }
        result = rollback_to_stage(stages, "qa-security", reset_from="impl.code")
        assert result["init"]["done"] is True
        assert result["impl.design"]["done"] is True


class TestInitNodes:
    """Init phase nodes: work item validation, ideation, refinement."""

    def test_init_node_success(self):
        mock_result = AgentResult(
            data={
                "valid": True,
                "complete": True,
                "work_item_refined": "Refined work item",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.init import init_node

            state = _make_state("small")
            result = init_node(state)
            assert isinstance(result, Command)
            assert result.goto == "init-ideate"

    def test_init_ideate_node_success(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "ideation_results": "Comprehensive ideation covering all requirements and approaches",
                "decomposed_tasks": ["task1", "task2"],
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.init import init_ideate_node

            state = _make_state("small")
            state = _mark_done(state, "init")
            result = init_ideate_node(state)
            assert isinstance(result, Command)

    def test_init_refine_node_success(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "refined_work_item": "Refined specification",
                "ready_for_architecture": True,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.init import init_refine_node

            state = _make_state("small")
            state = _mark_done(state, "init")
            state = _mark_done(state, "init.ideate")
            result = init_refine_node(state)
            assert isinstance(result, Command)


class TestDeployNode:
    """deploy.prepare node: deployment preparation."""

    def test_deploy_prepare_success(self):
        mock_result = AgentResult(
            data={
                "verdict": "PASS",
                "build_status": "pass",
                "lint_status": "pass",
                "complete": True,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.deploy import deploy_prepare_node

            state = _make_state("small")
            result = deploy_prepare_node(state)
            assert isinstance(result, Command)


class TestPostNode:
    """post node: loop completion, lessons, summary."""

    def test_post_node_success(self):
        mock_result = AgentResult(
            data={
                "summary": "Loop completed successfully",
                "final_status": "done",
                "complete": True,
                "lessons_to_share": 2,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.post import post_node

            state = _make_state("small")
            result = post_node(state)
            assert isinstance(result, Command)
            assert result.update["status"] == "done"
            assert result.update["task_outcome"] == "done"

    def test_post_node_failure(self):
        mock_result = AgentResult(data={}, error="agent_stalled")
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.post import post_node

            state = _make_state("small")
            result = post_node(state)
            assert isinstance(result, Command)
            assert result.update["status"] == "failed"


class TestArchitectureNodes:
    """Architecture phase nodes."""

    def test_arch_requirements_success(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "architecture_output": "Architecture requirements documented with key decisions and constraints",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.architecture import arch_node

            state = _make_state("medium")
            handler = arch_node("arch.requirements")
            result = handler(state)
            assert isinstance(result, Command)

    def test_arch_solution_success(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "architecture_output": "Architecture solution with technology choices and design patterns",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.architecture import arch_node

            state = _make_state("medium")
            state = _mark_done(state, "arch.requirements")
            state["stages"]["arch.solution"]["done"] = False
            state["current_stage"] = "arch.solution"
            handler = arch_node("arch.solution")
            result = handler(state)
            assert isinstance(result, Command)


class TestDocumentationNodes:
    """Documentation phase nodes."""

    def test_doc_decisions_success(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "decision_log": "Decisions consolidated",
                "decisions_count": 3,
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.documentation import doc_decisions_node

            state = _make_state("medium")
            result = doc_decisions_node(state)
            assert isinstance(result, Command)

    def test_doc_project_success(self):
        mock_result = AgentResult(
            data={
                "complete": True,
                "readme": "README content",
            }
        )
        with patch("eng_loop.tools.agent_runner.run_agent", return_value=mock_result):
            from eng_loop.nodes.documentation import doc_project_node

            state = _make_state("medium")
            result = doc_project_node(state)
            assert isinstance(result, Command)


class TestComplexityOrder:
    """Verify complexity ordering for QA activation."""

    def test_complexity_order(self):
        assert COMPLEXITY_ORDER["small"] < COMPLEXITY_ORDER["medium"]
        assert COMPLEXITY_ORDER["medium"] < COMPLEXITY_ORDER["large"]
        assert COMPLEXITY_ORDER["large"] < COMPLEXITY_ORDER["complex"]

    def test_all_qa_definitions_have_min_complexity(self):
        for qa_def in QA_STAGE_DEFINITIONS:
            assert "min_complexity" in qa_def
            assert qa_def["min_complexity"] in COMPLEXITY_ORDER

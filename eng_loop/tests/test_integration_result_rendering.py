from __future__ import annotations

"""Integration tests for evidence-based result rendering.

Tests that the result panel correctly reflects execution outcome,
artifact evidence, and topology fidelity.
"""

from io import StringIO

from rich.console import Console

from eng_loop.state import make_stage
from eng_loop.tools.progress import UIManager


class TestResultRenderingStatusStyles:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_done_status_renders(self):
        """DONE status renders correctly."""
        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="done",
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "Engineering Loop Complete" in text

    def test_failed_status_renders(self):
        """FAILED status renders correctly."""
        ui, output = self._make_ui()
        ui.render_result(
            status="failed",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="failed",
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "FAILED" in text

    def test_partial_status_renders(self):
        """PARTIAL status renders correctly."""
        ui, output = self._make_ui()
        ui.render_result(
            status="partial",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"init": make_stage(), "impl.code": make_stage()},
            task_outcome="partial",
            active_nodes=["init", "impl.code"],
        )
        text = output.getvalue()
        assert "PARTIAL" in text

    def test_done_with_warnings_renders(self):
        """DONE with warnings renders correctly."""
        ui, output = self._make_ui()
        ui.render_result(
            status="done_with_warnings",
            blocking_condition="",
            iterations=5,
            decisions=[],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="done_with_warnings",
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "Warnings" in text

    def test_blocked_status_renders(self):
        """BLOCKED status renders correctly."""
        ui, output = self._make_ui()
        ui.render_result(
            status="blocked",
            blocking_condition="missing dependency",
            iterations=2,
            decisions=[],
            stages={"init": make_stage()},
            task_outcome="blocked",
        )
        text = output.getvalue()
        assert "BLOCKED" in text


class TestResultRenderingArtifactEvidence:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_artifact_evidence_displayed(self):
        """Artifact evidence should be displayed in result."""
        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="done",
            artifact_evidence={
                "artifacts/test.md": {"exists": True, "verified": False},
                "artifacts/missing.md": {"exists": False, "verified": False},
            },
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "Artifact Delivery" in text
        assert "artifacts/test.md" in text

    def test_artifact_evidence_shows_missing(self):
        """Missing artifacts should be shown."""
        ui, output = self._make_ui()
        ui.render_result(
            status="failed",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"post": make_stage()},
            task_outcome="failed",
            artifact_evidence={
                "artifacts/missing.md": {"exists": False, "verified": False},
            },
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "artifacts/missing.md" in text


class TestResultRenderingActiveStages:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_active_stages_counted_not_all(self):
        """Only active stages should be counted, not all 26."""
        # Create noise stages that shouldn't appear in the result
        stages = {}
        for i in range(26):
            stages[f"stage-{i}"] = make_stage()
        # Add the actual active stages
        stages["init"] = make_stage()
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"] = make_stage()
        stages["impl.code"]["done"] = True
        stages["impl.code"]["attempts"] = 1
        stages["post"] = make_stage()
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages=stages,
            task_outcome="done",
            active_nodes=["init", "impl.code", "post"],
        )
        text = output.getvalue()
        # New design: pipeline panel shows active stages grouped by phase
        assert "Pipeline" in text
        # Active stages should appear as completed in their phases
        assert "INIT" in text
        assert "IMPL" in text
        assert "POST" in text


class TestResultRenderingPostFailure:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_post_failure_details_shown(self):
        """Post stage failure details should be displayed."""
        stages = {
            "init": make_stage(),
            "post": make_stage(),
        }
        stages["post"]["done"] = True
        stages["post"]["output"] = "{'summary': 'artifact validation failed', 'final_status': 'failed'}"

        ui, output = self._make_ui()
        ui.render_result(
            status="failed",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages=stages,
            task_outcome="failed",
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "Post Stage Failed" in text


class TestResultRenderingTopologyFidelity:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_topology_fidelity_warning_displayed(self):
        """Topology fidelity warnings should be displayed."""
        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="done",
            active_nodes=["init", "post"],
            topology_fidelity={
                "proposed": ["init", "impl.code", "verify", "post"],
                "compiled": ["init", "impl.code", "post"],
                "dropped": ["verify"],
                "added": [],
                "integrity": "warning",
            },
        )
        text = output.getvalue()
        assert "Topology Fidelity" in text
        assert "dropped" in text

    def test_topology_fidelity_clean_not_displayed(self):
        """Clean topology fidelity should not show warning."""
        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=3,
            decisions=[],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="done",
            active_nodes=["init", "post"],
            topology_fidelity={
                "proposed": ["init", "post"],
                "compiled": ["init", "post"],
                "dropped": [],
                "added": [],
                "integrity": "clean",
            },
        )
        text = output.getvalue()
        assert "Topology Fidelity Warning" not in text


class TestResultRenderingTroubledStages:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_troubled_stages_shown_for_failed(self):
        """Troubled stages should be shown for failed outcome."""
        stages = {
            "init": make_stage(),
            "impl.code": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["impl.code"]["done"] = False
        stages["impl.code"]["attempts"] = 3
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        ui, output = self._make_ui()
        ui.render_result(
            status="failed",
            blocking_condition="",
            iterations=5,
            decisions=[],
            stages=stages,
            task_outcome="failed",
            active_nodes=["init", "impl.code", "post"],
        )
        text = output.getvalue()
        assert "Troubled Stages" in text

    def test_troubled_stages_not_shown_for_clean_done(self):
        """Troubled stages should NOT be shown for clean done."""
        stages = {
            "init": make_stage(),
            "post": make_stage(),
        }
        stages["init"]["done"] = True
        stages["init"]["attempts"] = 1
        stages["post"]["done"] = True
        stages["post"]["attempts"] = 1

        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=2,
            decisions=[],
            stages=stages,
            task_outcome="done",
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "Troubled Stages" not in text


class TestResultRenderingDecisions:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_decisions_displayed(self):
        """Decisions should be displayed in result."""
        ui, output = self._make_ui()
        ui.render_result(
            status="done",
            blocking_condition="",
            iterations=3,
            decisions=["AD-001: Use React", "AD-002: Use Firebase"],
            stages={"init": make_stage(), "post": make_stage()},
            task_outcome="done",
            active_nodes=["init", "post"],
        )
        text = output.getvalue()
        assert "Decisions" in text


class TestResultRenderingBlocking:
    def _make_ui(self) -> tuple[UIManager, StringIO]:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        ui = UIManager()
        ui.console = console
        return ui, output

    def test_blocking_condition_displayed(self):
        """Blocking condition should be displayed."""
        ui, output = self._make_ui()
        ui.render_result(
            status="blocked",
            blocking_condition="missing dependency: npm not installed",
            iterations=2,
            decisions=[],
            stages={"init": make_stage()},
            task_outcome="blocked",
        )
        text = output.getvalue()
        assert "missing dependency" in text

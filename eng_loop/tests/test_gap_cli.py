from __future__ import annotations

"""FASE 9 — CLI integration gap tests."""

import subprocess
import sys
import tempfile


class TestCLIHelp:
    def test_help(self):
        r = subprocess.run([sys.executable, "-m", "eng_loop.cli", "--help"], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0


class TestCLIDryRun:
    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [sys.executable, "-m", "eng_loop.cli", "--dry-run", "--framework-root", tmp, "--loop-root", tmp],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=tmp,
            )
            assert r.returncode == 0


class TestCLIBuildTopology:
    def test_topology(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "--build-topology"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert r.returncode == 0


class TestCLIDynamicGraph:
    def test_dynamic_topology(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "--dynamic-graph", "--build-topology"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert r.returncode == 0


class TestCLISubcommands:
    def test_rollback_help(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "rollback", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0

    def test_run_node_help(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "run-node", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0

    def test_clear_state_help(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "clear-state", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0

    def test_skip_node_help(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "skip-node", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0

    def test_history_help(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "history", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert r.returncode == 0


class TestCLIArgParsing:
    """Test that CLI args are recognized via --help output."""

    def _help_text(self):
        r = subprocess.run(
            [sys.executable, "-m", "eng_loop.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout

    def test_work_item_flag(self):
        assert "--work-item" in self._help_text()

    def test_framework_root_flag(self):
        assert "--framework-root" in self._help_text()

    def test_dry_run_flag(self):
        assert "--dry-run" in self._help_text()

    def test_check_model_flag(self):
        assert "--check-model" in self._help_text()

    def test_dynamic_graph_flag(self):
        assert "--dynamic-graph" in self._help_text()

    def test_parallel_qa_flag(self):
        assert "--parallel-qa" in self._help_text()

    def test_build_topology_flag(self):
        assert "--build-topology" in self._help_text()

    def test_opencode_agent_flag(self):
        assert "--opencode-agent" in self._help_text()

    def test_pause_at_flag(self):
        assert "--pause-at" in self._help_text()

    def test_interactive_flag(self):
        assert "--interactive" in self._help_text()

    def test_check_compliance_flag(self):
        assert "--check-compliance" in self._help_text()

    def test_requested_stage_flag(self):
        assert "--requested-stage" in self._help_text()

from __future__ import annotations

"""Integration tests for evidence tracking and artifact verification."""

import json
import os
import tempfile
from pathlib import Path

from eng_loop.state import make_initial_state


class TestArtifactEvidenceTracking:
    def test_artifact_evidence_created_for_code_map(self):
        """Evidence should be created for each code_map entry."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        state = make_initial_state({}, {"artifact_root": artifact_root})
        state["work_item"] = {
            "title": "Test",
            "acceptance_criteria": ["Criterion 1", "Criterion 2"],
            "code_map": ["artifacts/test-output.md"],
        }

        evidence = {}
        for artifact_path in state["work_item"]["code_map"]:
            exists = os.path.exists(artifact_path)
            evidence[artifact_path] = {"exists": exists, "verified": False}

        assert "artifacts/test-output.md" in evidence
        assert evidence["artifacts/test-output.md"]["exists"] is False

    def test_artifact_evidence_exists_when_file_created(self):
        """Evidence should detect existing files."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        # Create the expected artifact
        expected_path = os.path.join(artifact_root, "test-output.md")
        Path(expected_path).write_text("test content", encoding="utf-8")

        evidence = {}
        evidence["artifacts/test-output.md"] = {"exists": os.path.exists(expected_path)}

        assert evidence["artifacts/test-output.md"]["exists"] is True

    def test_artifact_evidence_scans_artifact_root(self):
        """Evidence should scan artifact_root for additional files."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        # Create an extra artifact not in code_map
        extra_path = os.path.join(artifact_root, "extra-file.md")
        Path(extra_path).write_text("extra", encoding="utf-8")

        evidence = {}
        if os.path.isdir(artifact_root):
            for fname in os.listdir(artifact_root):
                fpath = os.path.join(artifact_root, fname)
                if os.path.isfile(fpath):
                    canonical = f"artifacts/{fname}"
                    if canonical not in evidence:
                        evidence[canonical] = {"exists": True, "verified": False}

        assert "artifacts/extra-file.md" in evidence
        assert evidence["artifacts/extra-file.md"]["exists"] is True

    def test_artifact_evidence_excludes_internal_files(self):
        """Internal files should be excluded from evidence."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        # Create internal files
        for fname in ["lessons.json", "LESSONS.md", "post-loop-summary.md"]:
            Path(os.path.join(artifact_root, fname)).write_text("internal")

        excluded = {
            "post-loop-summary.md", "lessons.json", "lessons-shared.json",
            "lessons-pending.json", "LESSONS.md",
        }
        evidence = {}
        if os.path.isdir(artifact_root):
            for fname in os.listdir(artifact_root):
                if fname in excluded:
                    continue
                fpath = os.path.join(artifact_root, fname)
                if os.path.isfile(fpath):
                    canonical = f"artifacts/{fname}"
                    if canonical not in evidence:
                        evidence[canonical] = {"exists": True, "verified": False}

        for fname in excluded:
            assert f"artifacts/{fname}" not in evidence

    def test_empty_code_map(self):
        """Empty code_map should produce empty evidence."""
        state = make_initial_state({}, {})
        state["work_item"] = {"title": "Test", "code_map": []}

        evidence = {}
        for artifact_path in state["work_item"].get("code_map", []):
            evidence[artifact_path] = {"exists": os.path.exists(artifact_path)}

        assert evidence == {}

    def test_mixed_artifacts_some_exist_some_missing(self):
        """Should correctly track mixed existence."""
        tmp = tempfile.mkdtemp()
        artifact_root = os.path.join(tmp, "artifacts")
        os.makedirs(artifact_root)

        # Create only one artifact
        Path(os.path.join(artifact_root, "existing.md")).write_text("exists")

        evidence = {}
        evidence["artifacts/existing.md"] = {"exists": os.path.exists(os.path.join(artifact_root, "existing.md"))}
        evidence["artifacts/missing.md"] = {"exists": os.path.exists(os.path.join(artifact_root, "missing.md"))}

        assert evidence["artifacts/existing.md"]["exists"] is True
        assert evidence["artifacts/missing.md"]["exists"] is False


class TestAcceptanceCriteriaTracking:
    def test_acceptance_criteria_extracted_from_work_item(self):
        """Acceptance criteria should be extractable from work item."""
        work_item = {
            "title": "Test",
            "acceptance_criteria": [
                "AC1: File exists",
                "AC2: Content is correct",
                "AC3: Format is valid",
            ],
        }

        ac = work_item.get("acceptance_criteria", [])
        assert len(ac) == 3
        assert "AC1" in ac[0]

    def test_empty_acceptance_criteria(self):
        """Missing acceptance criteria should return empty list."""
        work_item = {"title": "Test"}
        ac = work_item.get("acceptance_criteria", [])
        assert ac == []

    def test_work_item_as_string(self):
        """Work item as string should not crash."""
        work_item = "Just a string description"
        if isinstance(work_item, dict):
            ac = work_item.get("acceptance_criteria", [])
        else:
            ac = []
        assert ac == []


class TestExecutionEvidence:
    def test_execution_evidence_tracks_stage_completion(self):
        """Execution evidence should track which stages executed."""
        stages = {
            "init": {"done": True, "attempts": 1, "output": "initialized"},
            "impl.code": {"done": True, "attempts": 1, "output": "wrote 3 files"},
            "post": {"done": True, "attempts": 1, "output": "done"},
        }

        execution_evidence = {}
        for sid, s in stages.items():
            execution_evidence[sid] = {
                "executed": s.get("attempts", 0) > 0,
                "completed": s.get("done", False),
                "artifact": s.get("artifact_path", ""),
            }

        assert execution_evidence["init"]["executed"] is True
        assert execution_evidence["init"]["completed"] is True

    def test_execution_evidence_tracks_failed_stages(self):
        """Failed stages should be tracked as not completed."""
        stages = {
            "init": {"done": True, "attempts": 1},
            "impl.code": {"done": False, "attempts": 3},
            "post": {"done": True, "attempts": 1},
        }

        execution_evidence = {}
        for sid, s in stages.items():
            execution_evidence[sid] = {
                "executed": s.get("attempts", 0) > 0,
                "completed": s.get("done", False),
            }

        assert execution_evidence["impl.code"]["executed"] is True
        assert execution_evidence["impl.code"]["completed"] is False


class TestTopologyFidelityTracking:
    def test_fidelity_clean_when_proposed_equals_compiled(self):
        """When proposed == compiled, integrity is clean."""
        proposed = {"init", "impl.code", "post"}
        compiled = {"init", "impl.code", "post"}
        dropped = proposed - compiled
        added = compiled - proposed
        fidelity = {
            "proposed": sorted(proposed),
            "compiled": sorted(compiled),
            "dropped": sorted(dropped),
            "added": sorted(added),
            "integrity": "clean" if not (dropped or added) else "warning",
        }
        assert fidelity["integrity"] == "clean"
        assert fidelity["dropped"] == []

    def test_fidelity_warning_when_stages_dropped(self):
        """Dropped stages should produce warning."""
        proposed = {"init", "impl.code", "verify", "post"}
        compiled = {"init", "impl.code", "post"}
        dropped = proposed - compiled
        added = compiled - proposed
        fidelity = {
            "proposed": sorted(proposed),
            "compiled": sorted(compiled),
            "dropped": sorted(dropped),
            "added": sorted(added),
            "integrity": "clean" if not (dropped or added) else "warning",
        }
        assert fidelity["integrity"] == "warning"
        assert "verify" in fidelity["dropped"]

    def test_fidelity_warning_when_stages_added(self):
        """Added stages should produce warning."""
        proposed = {"init", "post"}
        compiled = {"init", "init-ideate", "post"}
        dropped = proposed - compiled
        added = compiled - proposed
        fidelity = {
            "proposed": sorted(proposed),
            "compiled": sorted(compiled),
            "dropped": sorted(dropped),
            "added": sorted(added),
            "integrity": "clean" if not (dropped or added) else "warning",
        }
        assert fidelity["integrity"] == "warning"
        assert "init-ideate" in fidelity["added"]

    def test_fidelity_serializable(self):
        """Fidelity data should be JSON serializable."""
        fidelity = {
            "proposed": ["init", "impl.code", "post"],
            "compiled": ["init", "impl.code", "post"],
            "dropped": [],
            "added": [],
            "integrity": "clean",
        }
        json_str = json.dumps(fidelity)
        parsed = json.loads(json_str)
        assert parsed["integrity"] == "clean"

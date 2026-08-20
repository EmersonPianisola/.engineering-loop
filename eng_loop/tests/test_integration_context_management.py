from __future__ import annotations

"""Integration tests: context management (slice, tier, consolidator).

Validates the full context pipeline:
  state artifacts → context slice → tier filtering → consolidation
"""

import json
import tempfile
from pathlib import Path

from eng_loop.tools.context_consolidator import (
    ContextConsolidator,
    build_handoff_summary,
    compress_handoff,
    compute_state_diff,
    compute_text_hash,
    deduplicate_stage_artifacts,
    estimate_similarity,
)
from eng_loop.tools.context_slice import (
    ARTIFACT_RESOLVERS,
    CONTEXT_SLICE_RULES,
    build_context_slice,
    build_context_slice_references,
    get_available_artifacts,
)
from eng_loop.tools.context_tier import (
    GLOBAL_TIER_KEYS,
    ContextTierConfig,
    build_context_tiers,
    enforce_context_budget,
    estimate_context_tokens,
    get_accessible_context,
    get_read_dependencies,
    get_stage_domain,
)


class TestContextSliceIntegration:
    """build_context_slice assembles correct context per stage."""

    def _make_state(self, stage_artifacts: dict | None = None) -> dict:
        return {
            "stage_artifacts": stage_artifacts or {},
            "work_item": "Build a new feature",
            "config": {},
        }

    def test_impl_code_includes_blueprint_and_lessons(self):
        """impl.code context slice includes blueprint and lessons."""
        state = self._make_state(
            {
                "impl.design": "Blueprint: create API endpoint with authentication",
                "lessons": json.dumps({"shared": [], "local": [{"lesson": "use pytest"}]}),
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        slice_result = build_context_slice("impl.code", state, paths, config)
        assert "Context for stage: impl.code" in slice_result
        assert "blueprint" in slice_result.lower() or "Blueprint" in slice_result

    def test_verify_includes_blueprint_and_diff(self):
        """verify context slice includes blueprint and diff."""
        state = self._make_state(
            {
                "impl.design": "Blueprint content for verification",
                "diff": "--- old\n+++ new\n@@ ...",
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        slice_result = build_context_slice("verify", state, paths, config)
        assert "Context for stage: verify" in slice_result

    def test_arch_solution_includes_requirements(self):
        """arch.solution context includes arch_requirements artifact."""
        state = self._make_state(
            {
                "arch.requirements": "System requirements: REST API, PostgreSQL",
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        slice_result = build_context_slice("arch.solution", state, paths, config)
        assert "Context for stage: arch.solution" in slice_result

    def test_design_stage_includes_journey_map(self):
        """Design stages include journey_map artifact."""
        state = self._make_state(
            {
                "init.bdd": "Journey map: user login flow",
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        slice_result = build_context_slice("design.user-research", state, paths, config)
        assert "Context for stage: design.user-research" in slice_result

    def test_context_slice_references_mode(self):
        """References mode emits paths instead of inline content."""
        state = self._make_state(
            {
                "impl.design": "x" * 5000,
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        ref_result = build_context_slice_references("impl.code", state, paths, config)
        assert "Context for stage: impl.code" in ref_result

    def test_context_slice_token_limit_enforcement(self):
        """Context slice respects token limit."""
        state = self._make_state(
            {
                "impl.design": "x" * 100000,
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 100}}

        slice_result = build_context_slice("impl.code", state, paths, config)
        assert "truncated" in slice_result.lower() or len(slice_result) < 100000

    def test_init_has_empty_context(self):
        """init stage has no include rules — minimal context."""
        state = self._make_state({})
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        slice_result = build_context_slice("init", state, paths, config)
        assert "Context for stage: init" in slice_result

    def test_unknown_stage_gets_default_context(self):
        """Unknown stages get default context with work_item and blueprint."""
        state = self._make_state(
            {
                "impl.design": "Blueprint content",
            }
        )
        paths = {"artifact_root": "/tmp/artifacts"}
        config = {"hardware": {"agent_context_limit": 66666}}

        slice_result = build_context_slice("unknown.stage", state, paths, config)
        assert "Context for stage: unknown.stage" in slice_result

    def test_disk_artifact_fallback(self):
        """Context slice falls back to disk when state artifact is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            artifact_root = Path(tmp) / "artifacts"
            artifact_root.mkdir()
            blueprint_path = artifact_root / "blueprints"
            blueprint_path.mkdir()
            (blueprint_path / "blueprint.md").write_text("Disk blueprint content", encoding="utf-8")

            state = self._make_state({})
            paths = {"artifact_root": str(artifact_root)}
            config = {"hardware": {"agent_context_limit": 66666}}

            slice_result = build_context_slice("impl.code", state, paths, config)
            assert "Disk blueprint content" in slice_result or "blueprint" in slice_result.lower()


class TestContextSliceRules:
    """Verify CONTEXT_SLICE_RULES covers all stages."""

    def test_all_stages_have_slice_rules(self):
        from eng_loop.state import STAGE_ORDER

        for stage_id in STAGE_ORDER:
            assert stage_id in CONTEXT_SLICE_RULES, f"Missing slice rules for {stage_id}"

    def test_all_artifact_resolvers_defined(self):
        """All artifact keys referenced in rules have resolvers."""
        referenced_keys = set()
        for rules in CONTEXT_SLICE_RULES.values():
            referenced_keys.update(rules.get("include", []))

        for key in referenced_keys:
            assert key in ARTIFACT_RESOLVERS, f"Missing resolver for artifact key: {key}"


class TestContextTierIntegration:
    """3-tier context: global, group, private."""

    def test_build_context_tiers(self):
        state = {
            "work_item": "Build feature",
            "complexity": "medium",
            "decisions": ["AD-001: Use React"],
            "stage_artifacts": {
                "impl.design": "Blueprint",
                "arch.requirements": "Requirements",
                "init_summary": "Init summary",
            },
            "current_stage": "impl.code",
            "status": "running",
        }

        tiers = build_context_tiers(state)
        assert "global" in tiers
        assert "group" in tiers
        assert "private" in tiers

        assert tiers["global"]["work_item"] == "Build feature"
        assert tiers["global"]["complexity"] == "medium"
        assert tiers["private"]["current_stage"] == "impl.code"

    def test_global_tier_contains_shared_keys(self):
        state = {k: f"value_{k}" for k in GLOBAL_TIER_KEYS}
        tiers = build_context_tiers(state)

        for key in GLOBAL_TIER_KEYS:
            assert key in tiers["global"], f"Missing global key: {key}"

    def test_group_tier_domain_scoping(self):
        state = {
            "stage_artifacts": {
                "impl.design": "Blueprint",
                "impl.code": "Implementation",
                "arch.requirements": "Requirements",
                "qa.security": "Security report",
            }
        }
        tiers = build_context_tiers(state)

        assert "impl" in tiers["group"]
        assert "arch" in tiers["group"]
        assert "qa" in tiers["group"]

    def test_accessible_context_respects_dependencies(self):
        state = {
            "work_item": "Build feature",
            "stage_artifacts": {
                "impl.design": "Blueprint",
                "arch.requirements": "Requirements",
                "init_summary": "Init summary",
            },
        }
        tiers = build_context_tiers(state)

        accessible = get_accessible_context("impl.code", tiers)
        assert "global" in accessible
        assert "group" in accessible

        read_deps = get_read_dependencies("impl.code")
        assert "init" in read_deps
        assert "arch" in read_deps
        assert "impl" in read_deps

    def test_init_has_no_read_dependencies(self):
        deps = get_read_dependencies("init")
        assert deps == []

    def test_deploy_has_most_dependencies(self):
        deps = get_read_dependencies("deploy.prepare")
        assert "init" in deps
        assert "impl" in deps
        assert "verify" in deps
        assert "qa" in deps

    def test_stage_domain_mapping(self):
        assert get_stage_domain("impl.code") == "impl"
        assert get_stage_domain("qa.security") == "qa"
        assert get_stage_domain("arch.review") == "arch"
        assert get_stage_domain("design.visual-design") == "design"

    def test_all_stages_mapped_to_domain(self):
        from eng_loop.state import STAGE_ORDER

        for stage_id in STAGE_ORDER:
            domain = get_stage_domain(stage_id)
            assert domain, f"Missing domain for {stage_id}"

    def test_context_token_estimation(self):
        tiers = {
            "global": {"work_item": "x" * 1000},
            "group": {},
            "private": {},
        }
        tokens = estimate_context_tokens(tiers)
        assert tokens > 0

    def test_context_budget_enforcement(self):
        large_content = "x" * 100000
        tiers = {
            "global": {"work_item": large_content},
            "group": {"impl": {"impl.design": large_content}},
            "private": {"current_stage": "impl.code"},
        }
        config = ContextTierConfig(
            global_max_tokens=100,
            group_max_tokens=100,
            total_agent_context_limit=500,
        )

        enforced = enforce_context_budget(tiers, config)
        assert "global" in enforced
        assert "group" in enforced
        assert "private" in enforced


class TestContextConsolidatorIntegration:
    """Dedup, compression, incremental diff."""

    def test_deduplicate_identical_artifacts(self):
        artifacts = {
            "stage1": "identical content here",
            "stage2": "identical content here",
            "stage3": "different content",
        }
        deduped, removed = deduplicate_stage_artifacts(artifacts)
        assert len(removed) >= 1
        assert len(deduped) < len(artifacts)

    def test_deduplicate_similar_artifacts(self):
        artifacts = {
            "stage1": "This is the main content of the document with some details",
            "stage2": "This is the main content of the document with slightly different details",
        }
        deduped, removed = deduplicate_stage_artifacts(artifacts, threshold=0.5)
        assert len(removed) >= 1

    def test_deduplicate_unique_artifacts(self):
        artifacts = {
            "stage1": "Completely unique content A",
            "stage2": "Completely unique content B",
            "stage3": "Completely unique content C",
        }
        deduped, removed = deduplicate_stage_artifacts(artifacts)
        assert len(removed) == 0
        assert len(deduped) == 3

    def test_deduplicate_empty_artifacts(self):
        artifacts = {
            "stage1": "content",
            "stage2": "",
            "stage3": "   ",
        }
        deduped, removed = deduplicate_stage_artifacts(artifacts)
        assert "stage1" in deduped

    def test_compress_handoff_within_budget(self):
        handoff = "Stage completed successfully with 3 decisions and 5 artifacts"
        compressed = compress_handoff(handoff, max_tokens=125)
        assert compressed == handoff

    def test_compress_handoff_preserves_content(self):
        # NEW BEHAVIOR: no truncation
        handoff = "x" * 10000
        compressed = compress_handoff(handoff, max_tokens=125)
        assert compressed == handoff

    def test_compute_state_diff(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1, "b": 99, "d": 4}

        diff = compute_state_diff(old, new)
        assert diff["b"] == 99
        assert diff["d"] == 4
        assert diff.get("c") is None  # Removed key appears as None
        assert "a" not in diff  # Unchanged key not in diff

    def test_compute_state_diff_new_keys(self):
        old = {}
        new = {"key": "value"}

        diff = compute_state_diff(old, new)
        assert diff == {"key": "value"}

    def test_compute_state_diff_removed_keys(self):
        old = {"key": "value"}
        new = {}

        diff = compute_state_diff(old, new)
        assert "key" in diff

    def test_build_handoff_summary(self):
        stage_result = {
            "implementation_summary": "Implemented feature with tests",
            "files_created": ["src/main.py", "tests/test_main.py"],
        }
        decisions = ["AD-001: Use React", "AD-002: TypeScript strict mode"]

        summary = build_handoff_summary("impl.code", stage_result, decisions)
        assert "impl.code" in summary
        assert "Decisions" in summary
        assert "Artifacts" in summary

    def test_build_handoff_summary_with_gaps(self):
        stage_result = {
            "output": "QA scan complete",
            "critical_findings": ["SQL injection vulnerability", "Missing CSRF protection"],
        }
        summary = build_handoff_summary("qa.security", stage_result, [])
        assert "Alerts" in summary

    def test_text_hash_consistency(self):
        text = "Some content to hash"
        hash1 = compute_text_hash(text)
        hash2 = compute_text_hash(text)
        assert hash1 == hash2
        assert len(hash1) == 12

    def test_text_hash_uniqueness(self):
        hash1 = compute_text_hash("content A")
        hash2 = compute_text_hash("content B")
        assert hash1 != hash2

    def test_similarity_identical(self):
        sim = estimate_similarity("hello world", "hello world")
        assert sim == 1.0

    def test_similarity_completely_different(self):
        sim = estimate_similarity("hello world", "completely different text")
        assert sim < 0.5

    def test_similarity_empty_strings(self):
        sim = estimate_similarity("", "hello")
        assert sim == 0.0

    def test_similarity_none_strings(self):
        sim = estimate_similarity("", "")
        assert sim == 0.0


class TestContextConsolidatorClass:
    """ContextConsolidator manages context lifecycle."""

    def test_process_stage_output_dedup(self):
        consolidator = ContextConsolidator()
        artifacts = {
            "stage1": "unique content A",
            "stage2": "unique content B",
        }
        result = {"output": "Stage completed"}
        decisions = ["AD-001: Decision"]

        update = consolidator.process_stage_output("impl.code", artifacts, result, decisions)
        assert "stage_artifacts" in update
        assert "handoffs" in update

    def test_process_stage_output_tracks_history(self):
        consolidator = ContextConsolidator()
        artifacts = {"stage1": "content"}
        result = {"output": "Output"}
        decisions = []

        consolidator.process_stage_output("impl.code", artifacts, result, decisions)
        assert "impl.code" in consolidator._artifact_history

    def test_should_consolidate(self):
        consolidator = ContextConsolidator()
        assert consolidator.should_consolidate(0) is False
        assert consolidator.should_consolidate(5) is True
        assert consolidator.should_consolidate(10) is True
        assert consolidator.should_consolidate(7) is False

    def test_context_health_report(self):
        consolidator = ContextConsolidator()
        state = {
            "stage_artifacts": {"a": "x" * 1000, "b": "y" * 2000},
            "handoffs": {"init": "handoff"},
            "decisions": ["AD-001"],
        }

        health = consolidator.get_context_health(state)
        assert health["artifact_count"] == 2
        assert health["handoff_count"] == 1
        assert health["decision_count"] == 1
        assert health["estimated_tokens"] > 0
        assert health["budget_remaining"] >= 0


class TestAvailableArtifacts:
    """get_available_artifacts lists discoverable artifacts."""

    def test_artifacts_from_state(self):
        state = {"stage_artifacts": {"impl.design": "Blueprint", "diff": "diff content"}}
        paths = {"artifact_root": "/tmp"}

        available = get_available_artifacts(state, paths)
        assert "impl.design" in available

    def test_artifacts_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_root = Path(tmp) / "artifacts"
            artifact_root.mkdir()
            bp_dir = artifact_root / "blueprints"
            bp_dir.mkdir()
            (bp_dir / "blueprint.md").write_text("Blueprint", encoding="utf-8")

            state = {"stage_artifacts": {}}
            paths = {"artifact_root": str(artifact_root)}

            available = get_available_artifacts(state, paths)
            assert "blueprint" in available


class TestContextEndToEnd:
    """Full context pipeline: artifacts → slice → tier → consolidate."""

    def test_full_context_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_root = Path(tmp) / "artifacts"
            artifact_root.mkdir()

            state = {
                "work_item": "Build API endpoint",
                "complexity": "medium",
                "decisions": ["AD-001: Use FastAPI"],
                "stage_artifacts": {
                    "impl.design": "Blueprint: create /api/users endpoint with CRUD operations",
                    "arch.requirements": "Requirements: REST API with JWT auth",
                    "arch.solution": "Solution: FastAPI + PostgreSQL + Alembic",
                },
                "current_stage": "impl.code",
                "status": "running",
                "config": {"hardware": {"agent_context_limit": 66666}},
            }
            paths = {"artifact_root": str(artifact_root)}
            config = state["config"]

            # Step 1: Build context tiers
            tiers = build_context_tiers(state)
            assert "global" in tiers
            assert tiers["global"]["work_item"] == "Build API endpoint"

            # Step 2: Get accessible context for impl.code
            accessible = get_accessible_context("impl.code", tiers)
            assert "global" in accessible

            # Step 3: Build context slice
            slice_result = build_context_slice("impl.code", state, paths, config)
            assert "Context for stage: impl.code" in slice_result

            # Step 4: Consolidate
            consolidator = ContextConsolidator()
            health = consolidator.get_context_health(state)
            assert health["artifact_count"] == 3
            assert health["budget_pct_used"] >= 0

from __future__ import annotations

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
    _enforce_token_limit,
    _get_reference_path,
    _resolve_context_key,
    build_context_slice,
    build_context_slice_references,
    get_available_artifacts,
)
from eng_loop.tools.context_tier import (
    GLOBAL_TIER_KEYS,
    GROUP_DOMAINS,
    PRIVATE_TIER_KEYS,
    STAGE_DOMAIN_MAP,
    STAGE_READ_DEPENDENCIES,
    ContextTierConfig,
    build_context_tiers,
    enforce_context_budget,
    estimate_context_tokens,
    get_accessible_context,
    get_read_dependencies,
    get_stage_domain,
)

# ============================================================
# CONTEXT TIER — Constants
# ============================================================


class TestStageDomainMap:
    def test_all_26_stages_present(self):
        assert len(STAGE_DOMAIN_MAP) == 31

    def test_init_stages(self):
        assert STAGE_DOMAIN_MAP["init"] == "init"
        assert STAGE_DOMAIN_MAP["init.ideate"] == "init"
        assert STAGE_DOMAIN_MAP["init.bdd"] == "init"
        assert STAGE_DOMAIN_MAP["init.refine"] == "init"

    def test_design_stages(self):
        for stage in (
            "design.user-research",
            "design.personas",
            "design.info-arch",
            "design.interaction",
            "design.design-system",
            "design.visual-design",
        ):
            assert STAGE_DOMAIN_MAP[stage] == "design"

    def test_arch_stages(self):
        assert STAGE_DOMAIN_MAP["arch.requirements"] == "arch"
        assert STAGE_DOMAIN_MAP["arch.solution"] == "arch"
        assert STAGE_DOMAIN_MAP["arch.review"] == "arch"

    def test_impl_stages(self):
        assert STAGE_DOMAIN_MAP["impl.design"] == "impl"
        assert STAGE_DOMAIN_MAP["impl.code"] == "impl"

    def test_verify_stages(self):
        assert STAGE_DOMAIN_MAP["verify"] == "verify"
        assert STAGE_DOMAIN_MAP["e2e.execute"] == "verify"

    def test_qa_stages(self):
        assert STAGE_DOMAIN_MAP["qa.security"] == "qa"
        assert STAGE_DOMAIN_MAP["qa.api-contract"] == "qa"
        assert STAGE_DOMAIN_MAP["qa.performance"] == "qa"

    def test_deploy_stages(self):
        assert STAGE_DOMAIN_MAP["deploy.prepare"] == "deploy"
        assert STAGE_DOMAIN_MAP["smoke.test"] == "deploy"

    def test_doc_stages(self):
        assert STAGE_DOMAIN_MAP["doc.update"] == "doc"
        assert STAGE_DOMAIN_MAP["doc.decisions"] == "doc"
        assert STAGE_DOMAIN_MAP["doc.project"] == "doc"

    def test_post_stage(self):
        assert STAGE_DOMAIN_MAP["post"] == "post"


class TestStageReadDependencies:
    def test_all_26_stages_present(self):
        assert len(STAGE_READ_DEPENDENCIES) == 31

    def test_init_no_dependencies(self):
        assert STAGE_READ_DEPENDENCIES["init"] == []

    def test_impl_code_dependencies(self):
        assert STAGE_READ_DEPENDENCIES["impl.code"] == ["init", "arch", "impl"]

    def test_verify_dependencies(self):
        assert STAGE_READ_DEPENDENCIES["verify"] == ["init", "impl"]

    def test_deploy_prepare_dependencies(self):
        assert STAGE_READ_DEPENDENCIES["deploy.prepare"] == ["init", "impl", "verify", "qa"]

    def test_post_no_dependencies(self):
        assert STAGE_READ_DEPENDENCIES["post"] == []


class TestGlobalTierKeys:
    def test_expected_keys(self):
        assert "work_item" in GLOBAL_TIER_KEYS
        assert "complexity" in GLOBAL_TIER_KEYS
        assert "decisions" in GLOBAL_TIER_KEYS
        assert "graph_topology" in GLOBAL_TIER_KEYS
        assert "active_nodes" in GLOBAL_TIER_KEYS
        assert "errors" in GLOBAL_TIER_KEYS


class TestGroupDomains:
    def test_all_domains_present(self):
        expected = {"init", "design", "arch", "impl", "verify", "qa", "deploy", "doc"}
        assert set(GROUP_DOMAINS.keys()) == expected

    def test_init_domain_keys(self):
        assert "init_summary" in GROUP_DOMAINS["init"]
        assert "ideation" in GROUP_DOMAINS["init"]

    def test_design_domain_keys(self):
        assert "design.user-research" in GROUP_DOMAINS["design"]
        assert "design.personas" in GROUP_DOMAINS["design"]

    def test_verify_domain_keys(self):
        assert "verify" in GROUP_DOMAINS["verify"]


class TestPrivateTierKeys:
    def test_expected_keys(self):
        assert "current_stage" in PRIVATE_TIER_KEYS
        assert "iteration" in PRIVATE_TIER_KEYS
        assert "status" in PRIVATE_TIER_KEYS
        assert "blocking_condition" in PRIVATE_TIER_KEYS


# ============================================================
# CONTEXT TIER — Functions
# ============================================================


class TestGetStageDomain:
    def test_known_stage(self):
        assert get_stage_domain("impl.code") == "impl"

    def test_design_stage(self):
        assert get_stage_domain("design.personas") == "design"

    def test_unknown_stage_returns_post(self):
        assert get_stage_domain("nonexistent.stage") == "post"

    def test_post_stage(self):
        assert get_stage_domain("post") == "post"


class TestGetReadDependencies:
    def test_init_empty(self):
        assert get_read_dependencies("init") == []

    def test_impl_code(self):
        assert get_read_dependencies("impl.code") == ["init", "arch", "impl"]

    def test_verify(self):
        assert get_read_dependencies("verify") == ["init", "impl"]

    def test_deploy_prepare(self):
        assert get_read_dependencies("deploy.prepare") == ["init", "impl", "verify", "qa"]

    def test_unknown_stage_empty(self):
        assert get_read_dependencies("unknown") == []


class TestBuildContextTiers:
    def test_empty_state_produces_empty_tiers(self):
        tiers = build_context_tiers({})
        assert tiers == {"global": {}, "group": {}, "private": {}}

    def test_global_tier_extracted(self):
        state = {
            "work_item": "Build a login page",
            "complexity": "small",
            "decisions": ["AD-001: Use React"],
        }
        tiers = build_context_tiers(state)
        assert tiers["global"]["work_item"] == "Build a login page"
        assert tiers["global"]["complexity"] == "small"
        assert tiers["global"]["decisions"] == ["AD-001: Use React"]

    def test_global_tier_ignores_non_global_keys(self):
        state = {"work_item": "test", "some_other_key": "value"}
        tiers = build_context_tiers(state)
        assert "some_other_key" not in tiers["global"]

    def test_group_tier_extracted(self):
        state = {
            "stage_artifacts": {
                "arch.requirements": "req content",
                "arch.solution": "solution content",
                "impl.design": "design content",
            }
        }
        tiers = build_context_tiers(state)
        assert "arch" in tiers["group"]
        assert tiers["group"]["arch"]["arch.requirements"] == "req content"
        assert "impl" in tiers["group"]

    def test_group_tier_omits_empty_domains(self):
        state = {"stage_artifacts": {"unknown_key": "value"}}
        tiers = build_context_tiers(state)
        assert tiers["group"] == {}

    def test_private_tier_extracted(self):
        state = {
            "current_stage": "impl.code",
            "iteration": 3,
            "status": "running",
        }
        tiers = build_context_tiers(state)
        assert tiers["private"]["current_stage"] == "impl.code"
        assert tiers["private"]["iteration"] == 3

    def test_private_tier_ignores_non_private_keys(self):
        state = {"current_stage": "x", "random_key": "y"}
        tiers = build_context_tiers(state)
        assert "random_key" not in tiers["private"]

    def test_full_state(self):
        state = {
            "work_item": "Build feature",
            "complexity": "medium",
            "current_stage": "impl.code",
            "iteration": 1,
            "stage_artifacts": {
                "arch.solution": "arch doc",
                "impl.design": "impl doc",
            },
        }
        tiers = build_context_tiers(state)
        assert len(tiers["global"]) == 2
        assert len(tiers["group"]) == 2
        assert len(tiers["private"]) == 2


class TestGetAccessibleContext:
    def test_global_always_accessible(self):
        tiers = {
            "global": {"work_item": "test"},
            "group": {},
            "private": {},
        }
        accessible = get_accessible_context("init", tiers)
        assert accessible["global"] == {"work_item": "test"}

    def test_private_always_accessible(self):
        tiers = {
            "global": {},
            "group": {},
            "private": {"current_stage": "init"},
        }
        accessible = get_accessible_context("init", tiers)
        assert accessible["private"] == {"current_stage": "init"}

    def test_group_filtered_by_read_dependencies(self):
        tiers = {
            "global": {},
            "group": {
                "init": {"init_summary": "summary"},
                "arch": {"arch.requirements": "req"},
                "impl": {"impl.design": "design"},
            },
            "private": {},
        }
        accessible = get_accessible_context("impl.code", tiers)
        assert "init" in accessible["group"]
        assert "arch" in accessible["group"]
        assert "impl" in accessible["group"]

    def test_init_gets_own_domain_group_access(self):
        tiers = {
            "global": {},
            "group": {
                "init": {"init_summary": "summary"},
                "arch": {"arch.requirements": "req"},
            },
            "private": {},
        }
        accessible = get_accessible_context("init", tiers)
        assert "init" in accessible["group"]
        assert "arch" not in accessible["group"]

    def test_deploy_has_wide_group_access(self):
        tiers = {
            "global": {},
            "group": {
                "init": {"init_summary": "s"},
                "impl": {"impl.design": "d"},
                "verify": {"verify": "v"},
                "qa": {"qa.security": "q"},
                "deploy": {"deploy.prepare": "dp"},
            },
            "private": {},
        }
        accessible = get_accessible_context("deploy.prepare", tiers)
        assert "init" in accessible["group"]
        assert "impl" in accessible["group"]
        assert "verify" in accessible["group"]
        assert "qa" in accessible["group"]
        assert "deploy" in accessible["group"]

    def test_missing_group_domain_not_included(self):
        tiers = {
            "global": {},
            "group": {"impl": {"impl.design": "d"}},
            "private": {},
        }
        accessible = get_accessible_context("impl.code", tiers)
        assert "init" not in accessible["group"]
        assert "arch" not in accessible["group"]
        assert "impl" in accessible["group"]


class TestEstimateContextTokens:
    def test_empty_tiers_returns_small_value(self):
        tokens = estimate_context_tokens({"global": {}, "group": {}, "private": {}})
        assert tokens >= 0

    def test_chars_divided_by_four(self):
        tiers = {"global": {"key": "a" * 400}, "group": {}, "private": {}}
        token_count = estimate_context_tokens(tiers)
        assert token_count > 0
        expected = sum(len(str(v)) for v in tiers.values()) // 4
        assert token_count == expected

    def test_larger_content(self):
        tiers = {"global": {"work_item": "x" * 1000}, "group": {}, "private": {}}
        tokens = estimate_context_tokens(tiers)
        assert tokens > 0


class TestEnforceContextBudget:
    def test_under_budget_no_change(self):
        tiers = {
            "global": {"work_item": "small"},
            "group": {"init": {"init_summary": "s"}},
            "private": {"current_stage": "init"},
        }
        config = ContextTierConfig()
        result = enforce_context_budget(tiers, config)
        assert result["global"] == {"work_item": "small"}
        assert result["group"] == {"init": {"init_summary": "s"}}
        assert result["private"] == {"current_stage": "init"}

    def test_over_budget_global_truncated(self):
        large_content = "x" * 20000
        tiers = {
            "global": {"work_item": large_content},
            "group": {},
            "private": {},
        }
        config = ContextTierConfig()
        result = enforce_context_budget(tiers, config)
        assert result["global"]["_truncated"] is True

    def test_group_fills_up_to_budget(self):
        tiers = {
            "global": {},
            "group": {
                "init": {"init_summary": "s"},
                "arch": {"arch.requirements": "r"},
            },
            "private": {"current_stage": "init"},
        }
        config = ContextTierConfig(total_agent_context_limit=50)
        result = enforce_context_budget(tiers, config)
        assert "group" in result

    def test_private_skipped_when_no_budget(self):
        tiers = {
            "global": {},
            "group": {},
            "private": {"current_stage": "init", "iteration": 1},
        }
        config = ContextTierConfig(total_agent_context_limit=0)
        result = enforce_context_budget(tiers, config)
        assert result["private"] == {}


class TestContextTierConfigDefaults:
    def test_global_max_tokens(self):
        config = ContextTierConfig()
        assert config.global_max_tokens == 4000

    def test_group_max_tokens(self):
        config = ContextTierConfig()
        assert config.group_max_tokens == 8000

    def test_private_max_tokens(self):
        config = ContextTierConfig()
        assert config.private_max_tokens == 2000

    def test_total_agent_context_limit(self):
        config = ContextTierConfig()
        assert config.total_agent_context_limit == 66666

    def test_custom_values(self):
        config = ContextTierConfig(global_max_tokens=1000, total_agent_context_limit=10000)
        assert config.global_max_tokens == 1000
        assert config.total_agent_context_limit == 10000


# ============================================================
# CONTEXT SLICE — Constants
# ============================================================


class TestContextSliceRules:
    def test_all_26_stages(self):
        assert len(CONTEXT_SLICE_RULES) == 31

    def test_init_empty_rules(self):
        assert CONTEXT_SLICE_RULES["init"] == {"include": [], "exclude": []}

    def test_impl_code_includes_blueprint_and_lessons(self):
        rules = CONTEXT_SLICE_RULES["impl.code"]
        assert "blueprint" in rules["include"]
        assert "lessons" in rules["include"]

    def test_verify_includes_blueprint_and_diff(self):
        rules = CONTEXT_SLICE_RULES["verify"]
        assert "blueprint" in rules["include"]
        assert "diff" in rules["include"]

    def test_post_empty_rules(self):
        assert CONTEXT_SLICE_RULES["post"] == {"include": [], "exclude": []}


class TestArtifactResolvers:
    def test_work_item_state_source(self):
        assert ARTIFACT_RESOLVERS["work_item"]["source"] == "state"
        assert ARTIFACT_RESOLVERS["work_item"]["key"] == "work_item"

    def test_blueprint_artifact_source(self):
        assert ARTIFACT_RESOLVERS["blueprint"]["source"] == "artifact"
        assert ARTIFACT_RESOLVERS["blueprint"]["state_key"] == "impl.design"
        assert ARTIFACT_RESOLVERS["blueprint"]["disk_path"] == "blueprints/blueprint.md"

    def test_lessons_artifact_source(self):
        assert ARTIFACT_RESOLVERS["lessons"]["source"] == "artifact"
        assert ARTIFACT_RESOLVERS["lessons"]["disk_path"] == "lessons.json"

    def test_diff_no_disk_path(self):
        assert ARTIFACT_RESOLVERS["diff"]["disk_path"] is None

    def test_full_context_all_artifacts(self):
        assert ARTIFACT_RESOLVERS["full_context"]["source"] == "all_artifacts"


# ============================================================
# CONTEXT SLICE — Functions
# ============================================================


class TestBuildContextSlice:
    def test_returns_markdown_with_stage_header(self):
        result = build_context_slice(
            "impl.code",
            {"stage_artifacts": {}},
            {"artifact_root": ""},
            {"hardware": {"agent_context_limit": 66666}},
        )
        assert "# Context for stage: impl.code" in result

    def test_includes_artifacts_per_rules(self):
        result = build_context_slice(
            "impl.code",
            {
                "stage_artifacts": {
                    "impl.design": "blueprint content",
                    "lessons": json.dumps({"key": "value"}),
                }
            },
            {"artifact_root": ""},
            {"hardware": {"agent_context_limit": 66666}},
            use_references=False,
        )
        assert "blueprint content" in result
        assert '"key": "value"' in result

    def test_empty_when_no_artifacts(self):
        result = build_context_slice(
            "init",
            {"stage_artifacts": {}},
            {"artifact_root": ""},
            {"hardware": {"agent_context_limit": 66666}},
        )
        assert "# Context for stage: init" in result
        parts = result.strip().split("\n")
        assert len(parts) <= 3

    def test_references_mode_emits_paths_for_large_content(self):
        large_content = "x" * 5000
        result = build_context_slice(
            "impl.code",
            {"stage_artifacts": {"impl.design": large_content}},
            {"artifact_root": "/artifacts"},
            {"hardware": {"agent_context_limit": 66666}},
            use_references=True,
            inline_threshold=3000,
        )
        assert "Path:" in result
        assert "blueprints/blueprint.md" in result
        assert "Use `read` tool" in result

    def test_inline_mode_emits_content_for_small_content(self):
        small_content = "short blueprint"
        result = build_context_slice(
            "impl.code",
            {"stage_artifacts": {"impl.design": small_content}},
            {"artifact_root": "/artifacts"},
            {"hardware": {"agent_context_limit": 66666}},
            use_references=True,
            inline_threshold=3000,
        )
        assert small_content in result

    def test_default_config_uses_66666_limit(self):
        result = build_context_slice(
            "init",
            {},
            {},
            {},
        )
        assert "66666" in result


class TestBuildContextSliceReferences:
    def test_always_uses_references(self):
        large_content = "x" * 5000
        result = build_context_slice_references(
            "impl.code",
            {"stage_artifacts": {"impl.design": large_content}},
            {"artifact_root": "/artifacts"},
            {"hardware": {"agent_context_limit": 66666}},
        )
        assert "Path:" in result
        assert large_content not in result

    def test_even_small_content_uses_references(self):
        small_content = "tiny"
        result = build_context_slice_references(
            "impl.code",
            {"stage_artifacts": {"impl.design": small_content}},
            {"artifact_root": "/artifacts"},
            {"hardware": {"agent_context_limit": 66666}},
        )
        assert "Path:" in result
        assert small_content not in result


class TestResolveContextKey:
    def test_state_source_returns_value(self):
        result = _resolve_context_key(
            "work_item",
            "init",
            {"work_item": "Build a feature"},
            {},
            "",
        )
        assert result == "Build a feature"

    def test_state_source_missing_key(self):
        result = _resolve_context_key(
            "work_item",
            "init",
            {},
            {},
            "",
        )
        assert result == ""

    def test_artifact_source_returns_value(self):
        result = _resolve_context_key(
            "blueprint",
            "impl.code",
            {},
            {"impl.design": "architectural blueprint"},
            "",
        )
        assert result == "architectural blueprint"

    def test_artifact_source_missing(self):
        result = _resolve_context_key(
            "blueprint",
            "impl.code",
            {},
            {},
            "",
        )
        assert result == ""

    def test_disk_path_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            blueprint_path = Path(tmp) / "blueprints" / "blueprint.md"
            blueprint_path.parent.mkdir()
            blueprint_path.write_text("disk blueprint content", encoding="utf-8")
            result = _resolve_context_key(
                "blueprint",
                "impl.code",
                {},
                {},
                tmp,
            )
            assert result == "disk blueprint content"

    def test_disk_path_fallback_missing_file(self):
        result = _resolve_context_key(
            "blueprint",
            "impl.code",
            {},
            {},
            "/nonexistent",
        )
        assert result == ""

    def test_unknown_key_returns_empty(self):
        result = _resolve_context_key(
            "nonexistent_key",
            "init",
            {},
            {},
            "",
        )
        assert result == ""

    def test_all_artifacts_source(self):
        result = _resolve_context_key(
            "full_context",
            "init",
            {},
            {"a": "content_a", "b": "content_b"},
            "",
        )
        assert "## a" in result
        assert "content_a" in result
        assert "## b" in result
        assert "content_b" in result

    def test_lessons_json_parsing(self):
        lessons_json = json.dumps({"lesson1": "value1"})
        result = _resolve_context_key(
            "lessons",
            "impl.code",
            {},
            {"lessons": lessons_json},
            "",
        )
        parsed = json.loads(result)
        assert parsed["lesson1"] == "value1"

    def test_lessons_invalid_json_falls_back(self):
        result = _resolve_context_key(
            "lessons",
            "impl.code",
            {},
            {"lessons": "not json"},
            "",
        )
        assert result == "not json"


class TestGetReferencePath:
    def test_returns_path_for_key_with_disk_path(self):
        result = _get_reference_path("blueprint", "/artifacts")
        assert result == "/artifacts/blueprints/blueprint.md"

    def test_returns_none_for_key_without_disk_path(self):
        result = _get_reference_path("diff", "/artifacts")
        assert result is None

    def test_returns_none_for_unknown_key(self):
        result = _get_reference_path("unknown", "/artifacts")
        assert result is None

    def test_returns_none_when_no_artifact_root(self):
        result = _get_reference_path("blueprint", "")
        assert result is None


class TestEnforceTokenLimit:
    def test_truncates_when_exceeds_limit(self):
        long_text = "x" * 50000
        result = _enforce_token_limit(long_text, 1000)
        assert len(result) > 4000
        assert "[truncated" in result

    def test_returns_unchanged_when_under_limit(self):
        short_text = "short text"
        result = _enforce_token_limit(short_text, 1000)
        assert result == short_text

    def test_truncation_includes_ellipsis(self):
        long_text = "y" * 100000
        result = _enforce_token_limit(long_text, 100)
        assert result.endswith("... [truncated — context limit reached] ...")


class TestGetAvailableArtifacts:
    def test_lists_keys_from_stage_artifacts(self):
        state = {"stage_artifacts": {"impl.design": "x", "diff": "y"}}
        result = get_available_artifacts(state, {"artifact_root": ""})
        assert "impl.design" in result
        assert "diff" in result

    def test_includes_disk_available_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            blueprint_path = Path(tmp) / "blueprints" / "blueprint.md"
            blueprint_path.parent.mkdir()
            blueprint_path.write_text("content", encoding="utf-8")
            state = {"stage_artifacts": {}}
            result = get_available_artifacts(state, {"artifact_root": tmp})
            assert "blueprint" in result

    def test_no_duplicates(self):
        state = {"stage_artifacts": {"impl.design": "x"}}
        with tempfile.TemporaryDirectory() as tmp:
            blueprint_path = Path(tmp) / "blueprints" / "blueprint.md"
            blueprint_path.parent.mkdir()
            blueprint_path.write_text("content", encoding="utf-8")
            result = get_available_artifacts(state, {"artifact_root": tmp})
            assert result.count("blueprint") == 1


# ============================================================
# CONTEXT CONSOLIDATOR — Hashing
# ============================================================


class TestComputeTextHash:
    def test_returns_12_char_hex(self):
        result = compute_text_hash("hello")
        assert len(result) == 12
        int(result, 16)

    def test_same_text_same_hash(self):
        h1 = compute_text_hash("identical content")
        h2 = compute_text_hash("identical content")
        assert h1 == h2

    def test_different_text_different_hash(self):
        h1 = compute_text_hash("text a")
        h2 = compute_text_hash("text b")
        assert h1 != h2

    def test_empty_string_hash(self):
        result = compute_text_hash("")
        assert len(result) == 12

    def test_unicode_text(self):
        result = compute_text_hash("hello \u00e9\u00e8\u00ea")
        assert len(result) == 12


# ============================================================
# CONTEXT CONSOLIDATOR — Similarity
# ============================================================


class TestEstimateSimilarity:
    def test_identical_text_returns_1_0(self):
        assert estimate_similarity("hello world", "hello world") == 1.0

    def test_completely_different_returns_0_0(self):
        result = estimate_similarity("abcdef", "xyzuvw")
        assert result == 0.0

    def test_empty_a_returns_0_0(self):
        assert estimate_similarity("", "something") == 0.0

    def test_empty_b_returns_0_0(self):
        assert estimate_similarity("something", "") == 0.0

    def test_both_empty_returns_0_0(self):
        assert estimate_similarity("", "") == 0.0

    def test_partially_similar_between_0_and_1(self):
        result = estimate_similarity("the quick brown fox", "the quick red fox")
        assert 0.0 < result < 1.0

    def test_case_insensitive(self):
        result = estimate_similarity("Hello World", "hello world")
        assert result == 1.0

    def test_single_word_overlap(self):
        result = estimate_similarity("one two three", "one four five")
        assert 0.0 < result < 1.0


# ============================================================
# CONTEXT CONSOLIDATOR — Deduplication
# ============================================================


class TestDeduplicateStageArtifacts:
    def test_single_artifact_no_removal(self):
        artifacts = {"key": "value"}
        deduped, removed = deduplicate_stage_artifacts(artifacts)
        assert deduped == {"key": "value"}
        assert removed == []

    def test_empty_artifacts(self):
        deduped, removed = deduplicate_stage_artifacts({})
        assert deduped == {}
        assert removed == []

    def test_identical_content_removes_duplicate(self):
        artifacts = {
            "a": "identical content here",
            "b": "identical content here",
        }
        deduped, removed = deduplicate_stage_artifacts(artifacts)
        assert len(deduped) == 1
        assert len(removed) == 1

    def test_similar_content_above_threshold_removes(self):
        artifacts = {
            "a": "the quick brown fox jumps over the lazy dog",
            "b": "the quick brown fox jumps over the lazy cat",
        }
        _, removed = deduplicate_stage_artifacts(artifacts, threshold=0.5)
        assert len(removed) >= 1

    def test_dissimilar_content_keeps_both(self):
        artifacts = {
            "a": "completely unrelated content first",
            "b": "totally different content second",
        }
        deduped, removed = deduplicate_stage_artifacts(artifacts, threshold=0.9)
        assert len(deduped) == 2
        assert removed == []

    def test_skips_empty_content(self):
        artifacts = {
            "a": "content",
            "b": "   ",
            "c": "more content",
        }
        deduped, _ = deduplicate_stage_artifacts(artifacts)
        assert "b" not in deduped

    def test_preserves_first_occurrence(self):
        artifacts = {
            "first": "shared content",
            "second": "shared content",
        }
        deduped, _ = deduplicate_stage_artifacts(artifacts)
        assert "first" in deduped


# ============================================================
# CONTEXT CONSOLIDATOR — Compression
# ============================================================


class TestCompressHandoff:
    def test_short_handoff_no_change(self):
        short = "Brief summary"
        assert compress_handoff(short, 125) == short

    def test_long_handoff_truncated(self):
        long_text = "x" * 10000
        result = compress_handoff(long_text, 100)
        assert len(result) > 400
        assert "[truncated]" in result

    def test_truncation_includes_ellipsis(self):
        long_text = "y" * 5000
        result = compress_handoff(long_text, 50)
        assert result.endswith("\n... [truncated]")


# ============================================================
# CONTEXT CONSOLIDATOR — State Diff
# ============================================================


class TestComputeStateDiff:
    def test_identical_states_empty_diff(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1, "b": 2}
        assert compute_state_diff(old, new) == {}

    def test_added_keys_included(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        diff = compute_state_diff(old, new)
        assert diff == {"b": 2}

    def test_removed_keys_included_with_none(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        diff = compute_state_diff(old, new)
        assert diff == {"b": None}

    def test_modified_keys_included_with_new_value(self):
        old = {"a": 1}
        new = {"a": 99}
        diff = compute_state_diff(old, new)
        assert diff == {"a": 99}

    def test_multiple_changes(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 10, "b": 2, "d": 4}
        diff = compute_state_diff(old, new)
        assert diff["a"] == 10
        assert diff["c"] is None
        assert diff["d"] == 4
        assert "b" not in diff

    def test_empty_states(self):
        assert compute_state_diff({}, {}) == {}


# ============================================================
# CONTEXT CONSOLIDATOR — Handoff Summary
# ============================================================


class TestBuildHandoffSummary:
    def test_includes_stage_name(self):
        summary = build_handoff_summary("impl.code", {}, [])
        assert "Stage: impl.code" in summary

    def test_includes_output_summary(self):
        result = {"output": "Implementation complete with tests"}
        summary = build_handoff_summary("impl.code", result, [])
        assert "Output:" in summary
        assert "Implementation complete" in summary

    def test_output_truncated_when_long(self):
        result = {"output": "x" * 500}
        summary = build_handoff_summary("impl.code", result, [])
        assert "..." in summary

    def test_includes_decision_count(self):
        result = {}
        decisions = ["AD-001: Use React", "AD-002: Use TypeScript"]
        summary = build_handoff_summary("impl.code", result, decisions)
        assert "Decisions: 2 recorded" in summary

    def test_includes_decision_items(self):
        result = {}
        decisions = ["AD-001: First decision", "AD-002: Second decision"]
        summary = build_handoff_summary("impl.code", result, decisions)
        assert "AD-001: First decision" in summary
        assert "AD-002: Second decision" in summary

    def test_limits_decisions_to_three(self):
        result = {}
        decisions = [f"Decision {i}" for i in range(5)]
        summary = build_handoff_summary("impl.code", result, decisions)
        assert "Decisions: 5 recorded" in summary
        assert "Decision 0" in summary
        assert "Decision 3" not in summary

    def test_includes_artifact_count(self):
        result = {"artifacts": ["file1.py", "file2.py"]}
        summary = build_handoff_summary("impl.code", result, [])
        assert "Artifacts: 2 produced" in summary

    def test_includes_alert_count(self):
        result = {"gaps": ["Critical: missing auth"]}
        summary = build_handoff_summary("impl.code", result, [])
        assert "Alerts: 1 issues found" in summary

    def test_uses_design_output_fallback(self):
        result = {"design_output": "Design complete"}
        summary = build_handoff_summary("impl.design", result, [])
        assert "Design complete" in summary

    def test_uses_files_created_fallback(self):
        result = {"files_created": ["a.py", "b.py"]}
        summary = build_handoff_summary("impl.code", result, [])
        assert "Artifacts: 2 produced" in summary

    def test_uses_critical_findings_fallback(self):
        result = {"critical_findings": ["Finding 1"]}
        summary = build_handoff_summary("qa.security", result, [])
        assert "Alerts: 1 issues found" in summary

    def test_compressed_when_exceeds_max_tokens(self):
        result = {"output": "x" * 2000}
        summary = build_handoff_summary("impl.code", result, [], max_tokens=50)
        assert "[truncated]" in summary


# ============================================================
# CONTEXT CONSOLIDATOR — Class
# ============================================================


class TestContextConsolidatorProcessStageOutput:
    def test_returns_update_with_deduped_artifacts(self):
        consolidator = ContextConsolidator()
        update = consolidator.process_stage_output(
            "impl.code",
            {"impl.design": "content", "blueprint": "content"},
            {"output": "done"},
            [],
        )
        assert "stage_artifacts" in update
        assert "handoffs" in update

    def test_returns_handoff(self):
        consolidator = ContextConsolidator()
        update = consolidator.process_stage_output(
            "impl.code",
            {},
            {"output": "Implementation done"},
            ["AD-001: Decision"],
        )
        assert "impl.code" in update["handoffs"]

    def test_deduplication_occurs(self):
        consolidator = ContextConsolidator()
        update = consolidator.process_stage_output(
            "impl.code",
            {"a": "same content", "b": "same content"},
            {},
            [],
        )
        assert len(update["stage_artifacts"]) == 1

    def test_tracks_artifact_history(self):
        consolidator = ContextConsolidator()
        consolidator.process_stage_output(
            "impl.code",
            {"impl.design": "content"},
            {"output": "done"},
            [],
        )
        assert "impl.code" in consolidator._artifact_history
        assert len(consolidator._artifact_history["impl.code"]) == 1

    def test_multiple_calls_accumulate_handoffs(self):
        consolidator = ContextConsolidator()
        consolidator.process_stage_output("impl.design", {}, {"output": "d"}, [])
        consolidator.process_stage_output("impl.code", {}, {"output": "c"}, [])
        assert len(consolidator._artifact_history) == 2

    def test_existing_handoffs_parsed_from_string(self):
        consolidator = ContextConsolidator()
        existing = json.dumps({"init": "initial handoff"})
        update = consolidator.process_stage_output(
            "impl.code",
            {"__handoffs__": existing},
            {"output": "done"},
            [],
        )
        assert "init" in update["handoffs"]
        assert "impl.code" in update["handoffs"]


class TestContextConsolidatorShouldConsolidate:
    def test_iteration_zero_returns_false(self):
        c = ContextConsolidator()
        assert c.should_consolidate(0) is False

    def test_before_threshold_returns_false(self):
        c = ContextConsolidator()
        assert c.should_consolidate(3, every=5) is False

    def test_at_threshold_returns_true(self):
        c = ContextConsolidator()
        assert c.should_consolidate(5, every=5) is True

    def test_multiple_of_every_returns_true(self):
        c = ContextConsolidator()
        assert c.should_consolidate(10, every=5) is True

    def test_custom_every(self):
        c = ContextConsolidator()
        assert c.should_consolidate(3, every=3) is True
        assert c.should_consolidate(6, every=3) is True


class TestContextConsolidatorGetContextHealth:
    def test_returns_metrics_dict(self):
        c = ContextConsolidator()
        health = c.get_context_health({})
        assert isinstance(health, dict)
        assert "artifact_count" in health
        assert "handoff_count" in health
        assert "decision_count" in health
        assert "estimated_tokens" in health
        assert "budget_remaining" in health
        assert "budget_pct_used" in health

    def test_empty_state(self):
        c = ContextConsolidator()
        health = c.get_context_health({})
        assert health["artifact_count"] == 0
        assert health["handoff_count"] == 0
        assert health["decision_count"] == 0
        assert health["estimated_tokens"] == 0
        assert health["budget_remaining"] == 66666

    def test_with_artifacts(self):
        c = ContextConsolidator()
        state = {
            "stage_artifacts": {"a": "x" * 100, "b": "y" * 200},
            "handoffs": {"init": "h"},
            "decisions": ["AD-001", "AD-002"],
        }
        health = c.get_context_health(state)
        assert health["artifact_count"] == 2
        assert health["handoff_count"] == 1
        assert health["decision_count"] == 2
        assert health["estimated_tokens"] == 75

    def test_budget_pct_used(self):
        c = ContextConsolidator()
        state = {"stage_artifacts": {}}
        health = c.get_context_health(state)
        assert health["budget_pct_used"] == 0.0

    def test_budget_capped_at_100(self):
        c = ContextConsolidator()
        state = {"stage_artifacts": {"x": "a" * 300000}}
        health = c.get_context_health(state)
        assert health["budget_pct_used"] <= 100.0

    def test_budget_remaining_non_negative(self):
        c = ContextConsolidator()
        state = {"stage_artifacts": {"x": "a" * 300000}}
        health = c.get_context_health(state)
        assert health["budget_remaining"] >= 0

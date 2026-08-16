from __future__ import annotations

import os
import tempfile

from eng_loop.config import deep_merge, ensure_directories, load_config, resolve_paths
from eng_loop.templates import get_skill_name, get_stage_file, is_self_constructed
from eng_loop.tools.autosizing import classify_complexity, deactivate_inactive_stages
from eng_loop.tools.decisions import extract_decisions, next_ad_number, record_decision


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99, "e": 5}, "f": 6}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3, "e": 5}, "f": 6}


def test_load_config_template():
    import pathlib

    repo_root = pathlib.Path(__file__).parent.parent.parent
    framework_root = repo_root
    config = load_config(framework_root, framework_root)
    assert config.get("name") == "engineering-loop"
    assert "constraints" in config
    assert "auto_sizing" in config


def test_resolve_paths():
    import pathlib

    repo_root = pathlib.Path(__file__).parent.parent.parent
    config = {
        "framework_skill_root": "skills",
        "framework_reference_root": "references",
        "framework_stage_root": "stages",
        "framework_template_path": "references/skill-templates.md",
        "artifact_root": "artifacts",
        "log_root": "../_bmad-output/process-logs",
        "state_file": "state.json",
        "context_file": "context.md",
        "planning_artifacts_root": "../_bmad-output/implementation-artifacts",
    }
    paths = resolve_paths(config, repo_root, repo_root, repo_root.parent)
    assert "framework_root" in paths
    assert "artifact_root" in paths
    assert paths["framework_skill_root"].endswith("skills")


def test_ensure_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {
            "artifact_root": os.path.join(tmpdir, "artifacts"),
            "log_root": os.path.join(tmpdir, "logs"),
        }
        ensure_directories(paths)
        assert os.path.isdir(os.path.join(tmpdir, "artifacts", "architectures"))
        assert os.path.isdir(os.path.join(tmpdir, "artifacts", "blueprints"))
        assert os.path.isdir(os.path.join(tmpdir, "logs"))


def test_classify_complexity_small():
    config = {"auto_sizing": {"heuristics": {}}}
    result = classify_complexity("Add a button to the page", config)
    assert result == "small"


def test_classify_complexity_with_integrations():
    config = {"auto_sizing": {"heuristics": {}}}
    result = classify_complexity("Build API integration with external payment service and OAuth", config)
    assert result in ("medium", "large")


def test_stage_file_map():
    assert get_stage_file("impl.code") == "impl-code"
    assert get_stage_file("design.user-research") == "design-user-research"
    assert get_stage_file("arch.requirements") == "architecture"


def test_skill_map():
    assert get_skill_name("init") == "bmad-integration"
    assert get_skill_name("verify") == "verifier"
    assert is_self_constructed(get_skill_name("impl.code"))


def test_extract_decisions():
    text = "Some text with AD-001 and AD-002 decisions, also AD-001 again"
    result = extract_decisions(text)
    assert result == ["AD-001", "AD-002"]


def test_next_ad_number():
    assert next_ad_number([]) == "AD-001"
    assert next_ad_number(["AD-001", "AD-005"]) == "AD-006"


def test_record_decision():
    state = {"decisions": ["AD-001: First decision"]}
    result = record_decision(state, "Second decision")
    assert result == "AD-002: Second decision"
    assert len(state["decisions"]) == 2


def test_deactivate_inactive_stages():
    from eng_loop.state import init_stages

    stages = init_stages()
    result = deactivate_inactive_stages(stages, "small", False)
    assert result["design.user-research"]["done"] is True
    assert result["arch.requirements"]["done"] is True
    assert result["impl.code"]["done"] is False
    assert result["init"]["done"] is False


if __name__ == "__main__":
    test_deep_merge()
    test_load_config_template()
    test_resolve_paths()
    test_ensure_directories()
    test_classify_complexity_small()
    test_classify_complexity_with_integrations()
    test_stage_file_map()
    test_skill_map()
    test_extract_decisions()
    test_next_ad_number()
    test_record_decision()
    test_deactivate_inactive_stages()
    print("All tests passed.")

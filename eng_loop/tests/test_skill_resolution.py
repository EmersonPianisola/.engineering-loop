from __future__ import annotations

from pathlib import Path

import pytest

from eng_loop.config import resolve_paths
from eng_loop.templates import list_skills, load_skill_resolved


def _make_skill(root: Path, name: str, content: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content, encoding="utf-8")


@pytest.fixture
def skill_env(tmp_path) -> tuple[Path, Path]:
    framework = tmp_path / "framework"
    _make_skill(framework / "skills", "essence", "# framework essence")
    _make_skill(framework / "skills", "verifier", "# framework verifier")

    global_root = tmp_path / "global"
    _make_skill(global_root, "essence", "# global essence")
    _make_skill(global_root, "web-search", "# global web-search")

    return framework, global_root


def test_resolve_paths_skill_roots_order(skill_env):
    framework, global_root = skill_env
    config = {"global_skills": {"enabled": True, "roots": [str(global_root)]}}
    paths = resolve_paths(config, framework, framework, framework)

    assert paths["skill_roots"][0] == str(framework / "skills")
    assert paths["skill_roots"][1] == str(global_root)
    assert len(paths["skill_roots"]) == 2


def test_resolve_paths_keeps_framework_skill_root_key(skill_env):
    framework, global_root = skill_env
    config = {"global_skills": {"enabled": True, "roots": [str(global_root)]}}
    paths = resolve_paths(config, framework, framework, framework)

    assert paths["framework_skill_root"] == str(framework / "skills")
    assert paths["skill_roots"][0] == paths["framework_skill_root"]


def test_resolve_paths_global_disabled(skill_env):
    framework, global_root = skill_env
    config = {"global_skills": {"enabled": False, "roots": [str(global_root)]}}
    paths = resolve_paths(config, framework, framework, framework)

    assert paths["skill_roots"] == [str(framework / "skills")]


def test_resolve_paths_skips_missing_roots(tmp_path):
    config = {
        "global_skills": {
            "enabled": True,
            "roots": [str(tmp_path / "nope"), str(tmp_path / "also-missing")],
        }
    }
    paths = resolve_paths(config, tmp_path, tmp_path, tmp_path)

    assert paths["skill_roots"] == [str(tmp_path / "skills")]


def test_resolve_paths_dedupes_framework_root(tmp_path):
    (tmp_path / "skills").mkdir()
    config = {
        "framework_skill_root": "skills",
        "global_skills": {"enabled": True, "roots": [str(tmp_path / "skills")]},
    }
    paths = resolve_paths(config, tmp_path, tmp_path, tmp_path)

    assert paths["skill_roots"] == [str(tmp_path / "skills")]


def test_resolve_paths_expands_tilde(monkeypatch, tmp_path):
    home = tmp_path / "home"
    global_root = home / ".agents" / "skills"
    _make_skill(global_root, "caveman", "# caveman")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    framework = tmp_path / "framework"
    framework.mkdir()
    config = {"global_skills": {"enabled": True, "roots": ["~/.agents/skills"]}}
    paths = resolve_paths(config, framework, framework, framework)

    assert paths["skill_roots"] == [str(framework / "skills"), str(global_root)]
    assert load_skill_resolved("caveman", paths["skill_roots"]) == "# caveman"


def test_resolve_paths_relative_root_resolves_against_loop_root(tmp_path):
    loop_root = tmp_path / "loop"
    global_root = loop_root / "shared-skills"
    _make_skill(global_root, "pdf", "# pdf")

    framework = tmp_path / "framework"
    framework.mkdir()
    config = {"global_skills": {"enabled": True, "roots": ["shared-skills"]}}
    paths = resolve_paths(config, framework, loop_root, loop_root)

    assert paths["skill_roots"] == [str(framework / "skills"), str(global_root)]


def test_load_skill_resolved_framework_wins_on_collision(skill_env):
    framework, global_root = skill_env
    roots = [str(framework / "skills"), str(global_root)]

    assert load_skill_resolved("essence", roots) == "# framework essence"


def test_load_skill_resolved_falls_back_to_global(skill_env):
    framework, global_root = skill_env
    roots = [str(framework / "skills"), str(global_root)]

    assert load_skill_resolved("web-search", roots) == "# global web-search"
    assert load_skill_resolved("verifier", roots) == "# framework verifier"


def test_load_skill_resolved_missing_returns_empty(caplog):
    import logging

    with caplog.at_level(logging.WARNING):
        result = load_skill_resolved("does-not-exist", ["/nonexistent/root"])

    assert result == ""
    assert "Missing markdown file" not in caplog.text


def test_load_skill_resolved_no_warning_for_global_only_skill(caplog, skill_env):
    import logging

    framework, global_root = skill_env
    roots = [str(framework / "skills"), str(global_root)]

    with caplog.at_level(logging.WARNING):
        result = load_skill_resolved("web-search", roots)

    assert result == "# global web-search"
    assert "Missing markdown file" not in caplog.text


def test_load_skill_resolved_none_and_empty_roots():
    assert load_skill_resolved("essence", None) == ""
    assert load_skill_resolved("essence", []) == ""


def test_load_skill_resolved_single_root_backward_compat(skill_env):
    framework, _ = skill_env
    roots = [str(framework / "skills")]

    assert load_skill_resolved("essence", roots) == "# framework essence"
    assert load_skill_resolved("web-search", roots) == ""


def test_list_skills_precedence(skill_env):
    framework, global_root = skill_env
    mapping = list_skills([str(framework / "skills"), str(global_root)])

    assert mapping == {
        "essence": str(framework / "skills"),
        "verifier": str(framework / "skills"),
        "web-search": str(global_root),
    }


def test_list_skills_skips_dirs_without_skill_md(tmp_path):
    root = tmp_path / "roots"
    (root / "not-a-skill").mkdir(parents=True)
    _make_skill(root, "real-skill", "# real")

    mapping = list_skills([str(root)])
    assert mapping == {"real-skill": str(root)}


def test_list_skills_empty_roots():
    assert list_skills(None) == {}
    assert list_skills([]) == {}

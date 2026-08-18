from __future__ import annotations

from pathlib import Path


def _skill_root() -> Path:
    """Resolve the skills/ directory relative to the repo root."""
    return Path(__file__).resolve().parents[2] / "skills"


def test_all_skill_map_entries_have_files():
    """Every SKILL_MAP entry must resolve to an existing SKILL.md file on disk.

    Self-constructed skills (names like __domain__) are excluded — they are
    generated at runtime from internet best practices, not loaded from disk.
    """
    from eng_loop.templates import SKILL_MAP, is_self_constructed

    missing = []
    for stage_id, skill_name in SKILL_MAP.items():
        if is_self_constructed(skill_name):
            continue
        skill_file = _skill_root() / skill_name / "SKILL.md"
        if not skill_file.exists():
            missing.append(f"{stage_id} -> {skill_name} ({skill_file})")

    assert not missing, "Missing SKILL.md files:\n" + "\n".join(f"  - {m}" for m in missing)


def test_load_skill_returns_content_for_existing():
    """Skills that exist on disk must return non-empty content."""
    from eng_loop.templates import SKILL_MAP, is_self_constructed, load_skill

    empty = []
    for stage_id, skill_name in SKILL_MAP.items():
        if is_self_constructed(skill_name):
            continue
        content = load_skill(str(_skill_root()), skill_name)
        if not content:
            empty.append(f"{stage_id} -> {skill_name}")

    assert not empty, "SKILL.md files exist but return empty content:\n" + "\n".join(
        f"  - {e}" for e in empty
    )


def test_load_skill_returns_empty_for_missing(caplog):
    """Loading a non-existent skill should log a warning and return empty string."""
    import logging

    from eng_loop.templates import load_skill

    with caplog.at_level(logging.WARNING):
        result = load_skill(str(_skill_root()), "nonexistent-skill")

    assert result == ""
    assert "Missing markdown file" in caplog.text


def test_skill_map_contains_qa_stages():
    """QA stages must have skill mappings so skills are loaded at runtime."""
    from eng_loop.templates import SKILL_MAP

    qa_stages = {
        "qa.static",
        "qa.unit",
        "qa.integration",
        "qa.human.flow",
        "qa.human.ux",
    }
    missing = qa_stages - set(SKILL_MAP.keys())
    assert not missing, f"QA stages missing from SKILL_MAP: {missing}"


def test_qa_skills_exist_on_disk():
    """Every QA skill referenced in SKILL_MAP must have a SKILL.md file."""
    from eng_loop.templates import SKILL_MAP, is_self_constructed

    qa_stages = {
        "qa.static",
        "qa.unit",
        "qa.integration",
        "qa.human.flow",
        "qa.human.ux",
    }
    missing = []
    for stage_id in qa_stages:
        skill_name = SKILL_MAP.get(stage_id)
        if not skill_name:
            missing.append(f"{stage_id} (no mapping)")
            continue
        if is_self_constructed(skill_name):
            continue
        skill_file = _skill_root() / skill_name / "SKILL.md"
        if not skill_file.exists():
            missing.append(f"{stage_id} -> {skill_name}")

    assert not missing, "QA skills missing on disk:\n" + "\n".join(
        f"  - {m}" for m in missing
    )


def test_design_skills_exist_on_disk():
    """Design phase skills referenced in SKILL_MAP must have SKILL.md files."""
    from eng_loop.templates import SKILL_MAP, is_self_constructed

    design_stages = {
        "design.user-research",
        "design.personas",
        "design.info-arch",
        "design.interaction",
        "design.design-system",
        "design.visual-design",
    }
    missing = []
    for stage_id in design_stages:
        skill_name = SKILL_MAP.get(stage_id)
        if not skill_name:
            missing.append(f"{stage_id} (no mapping)")
            continue
        if is_self_constructed(skill_name):
            continue
        skill_file = _skill_root() / skill_name / "SKILL.md"
        if not skill_file.exists():
            missing.append(f"{stage_id} -> {skill_name}")

    assert not missing, "Design skills missing on disk:\n" + "\n".join(
        f"  - {m}" for m in missing
    )


def test_essence_skill_exists():
    """The essence skill must have a SKILL.md file for the essence gate."""
    skill_file = _skill_root() / "essence" / "SKILL.md"
    assert skill_file.exists(), f"Essence skill missing: {skill_file}"
    assert skill_file.stat().st_size > 100, "Essence SKILL.md is too small"

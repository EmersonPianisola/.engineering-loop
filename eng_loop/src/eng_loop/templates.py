from __future__ import annotations

from pathlib import Path

from eng_loop.tools.prompt_builder import load_cached_markdown


def load_markdown(path: str | Path) -> str:
    return load_cached_markdown(path)


def load_stage_procedure(stage_root: str, stage_file: str) -> str:
    return load_cached_markdown(Path(stage_root) / f"{stage_file}.md")


def load_skill(skill_root: str, skill_name: str) -> str:
    return load_cached_markdown(Path(skill_root) / skill_name / "SKILL.md")


def load_skill_resolved(skill_name: str, skill_roots: list[str] | None) -> str:
    """Load a skill by name across ordered roots (first root with the file wins).

    Roots are checked in priority order (framework skills first, then global
    roots). Existence is checked directly to avoid spurious missing-file
    warnings for roots that simply do not carry the skill.
    """
    for root in skill_roots or []:
        skill_file = Path(root) / skill_name / "SKILL.md"
        if skill_file.is_file():
            return load_skill(root, skill_name)
    return ""


def list_skills(skill_roots: list[str] | None) -> dict[str, str]:
    """Map skill name -> root that provides it (first root in order wins)."""
    found: dict[str, str] = {}
    for root in skill_roots or []:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for entry in sorted(root_path.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").is_file() and entry.name not in found:
                found[entry.name] = root
    return found


def load_reference(reference_root: str, ref_file: str) -> str:
    return load_cached_markdown(Path(reference_root) / f"{ref_file}.md")


STAGE_FILE_MAP: dict[str, str] = {
    "init": "init",
    "init.ideate": "init-ideate",
    "init.bdd": "init-bdd",
    "init.refine": "init-refine",
    "design.user-research": "design-user-research",
    "design.personas": "design-personas",
    "design.info-arch": "design-info-arch",
    "design.interaction": "design-interaction",
    "design.design-system": "design-design-system",
    "design.visual-design": "design-visual-design",
    "arch.requirements": "architecture",
    "arch.solution": "architecture",
    "arch.review": "architecture",
    "impl.design": "impl-design",
    "impl.code": "impl-code",
    "doc.update": "doc-update",
    "verify": "verify",
    "e2e.execute": "e2e-execute",
    "qa.security": "qa-security",
    "qa.api-contract": "qa-api-contract",
    "qa.performance": "qa-performance",
    "deploy.prepare": "deploy-prepare",
    "smoke.test": "smoke-test",
    "doc.decisions": "doc-decisions",
    "doc.project": "doc-project",
    "post": "post",
}


def get_stage_file(stage_id: str) -> str:
    return STAGE_FILE_MAP.get(stage_id, stage_id.replace(".", "-").replace("_", "-"))


SKILL_MAP: dict[str, str] = {
    "init": "bmad-integration",
    "init.ideate": "bmad-ideation",
    "init.bdd": "bmad-bdd-mapper",
    "design.user-research": "bmad-user-research",
    "design.personas": "bmad-personas",
    "design.info-arch": "bmad-info-arch",
    "design.interaction": "bmad-interaction",
    "design.design-system": "bmad-design-system",
    "design.visual-design": "bmad-visual-design",
    "arch.requirements": "requirements-refiner",
    "arch.solution": "solution-designer",
    "arch.review": "architecture-reviewer",
    "impl.design": "implementation-architect",
    "impl.code": "__domain__",
    "doc.update": "__doc-updater__",
    "verify": "verifier",
    "e2e.execute": "e2e-playwright",
    "qa.security": "__security-reviewer__",
    "qa.api-contract": "__api-contract-validator__",
    "qa.performance": "__performance-checker__",
    "qa.static": "linter-agent",
    "qa.unit": "tester-unit",
    "qa.integration": "integration-tester",
    "qa.human.flow": "persona-simulator",
    "qa.human.ux": "ux-auditor",
    "deploy.prepare": "__orchestrator__",
    "smoke.test": "e2e-playwright",
    "doc.decisions": "__decision-consolidator__",
    "doc.project": "__project-documentation__",
    "post": "__orchestrator__",
}


def get_skill_name(stage_id: str) -> str:
    return SKILL_MAP.get(stage_id, "__unknown__")


def is_self_constructed(skill_name: str) -> bool:
    return skill_name.startswith("__") and skill_name.endswith("__")


def build_stage_prompt(
    stage_id: str, stage_procedure: str, skill_content: str, work_item: str, context_slice: str
) -> str:
    parts = []
    parts.append(f"# STAGE: {stage_id}")
    parts.append("")
    if skill_content:
        parts.append("## SKILL")
        parts.append(skill_content)
        parts.append("")
    if stage_procedure:
        parts.append("## PROCEDURE")
        parts.append(stage_procedure)
        parts.append("")
    if work_item:
        parts.append("## WORK ITEM")
        parts.append(work_item)
        parts.append("")
    if context_slice:
        parts.append("## CONTEXT")
        parts.append(context_slice)
        parts.append("")
    return "\n".join(parts)

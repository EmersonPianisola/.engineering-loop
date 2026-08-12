from __future__ import annotations

from typing import Any


def classify_complexity(work_item: str, config: dict[str, Any]) -> str:
    heuristics = config.get("auto_sizing", {}).get("heuristics", {})
    small_h = heuristics.get("small", {})
    medium_h = heuristics.get("medium", {})

    estimated_files = _estimate_files(work_item)
    estimated_tasks = _estimate_tasks(work_item)
    has_new_domains = _has_new_domains(work_item)
    has_integrations = _has_integrations(work_item)
    has_ambiguity = _has_ambiguity(work_item)

    max_files_small = small_h.get("max_files", 3)
    max_tasks_small = small_h.get("max_tasks", 3)

    max_files_medium = medium_h.get("max_files", 10)
    max_tasks_medium = medium_h.get("max_tasks", 8)

    if has_ambiguity and has_new_domains and has_integrations:
        return "complex"

    if estimated_files > max_files_medium or estimated_tasks > max_tasks_medium or has_new_domains or has_integrations:
        return "large"

    if estimated_files > max_files_small or estimated_tasks > max_tasks_small or has_integrations:
        return "medium"

    return "small"


def _estimate_files(text: str) -> int:
    import re
    file_keywords = re.findall(r"\b(file|module|component|class|function|endpoint|route|page|screen)\b", text.lower())
    return max(len(file_keywords), 1)


def _estimate_tasks(text: str) -> int:
    import re
    task_indicators = re.findall(r"\b(should|must|need to|implement|create|build|add|update|fix)\b", text.lower())
    return max(len(task_indicators), 1)


def _has_new_domains(text: str) -> bool:
    domain_keywords = ["machine learning", "ai", "blockchain", "iot", "real-time", "streaming", "ml model", "neural"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in domain_keywords)


def _has_integrations(text: str) -> bool:
    integration_keywords = ["api", "integration", "webhook", "third-party", "external service", "sdk", "oauth", "payment"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in integration_keywords)


def _has_ambiguity(text: str) -> bool:
    ambiguity_keywords = ["maybe", "perhaps", "ideally", "somewhat", "roughly", "approximately", "might want"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in ambiguity_keywords)


def deactivate_inactive_stages(stages: dict[str, Any], complexity: str, ui_project: bool) -> dict[str, Any]:
    from eng_loop.state import STAGE_MIN_COMPLEXITY, COMPLEXITY_ORDER, STAGE_ORDER

    result = dict(stages)
    for sid in STAGE_ORDER:
        min_c = STAGE_MIN_COMPLEXITY.get(sid)
        if min_c and COMPLEXITY_ORDER.get(complexity, 0) < COMPLEXITY_ORDER.get(min_c, 0):
            result[sid]["done"] = True
            result[sid]["attempts"] = 0
            result[sid]["essence_checked"] = False

        if sid in ("e2e.execute", "smoke.test") and not ui_project:
            result[sid]["done"] = True

    return result


def detect_ui_project(paths: dict[str, Any]) -> bool:
    import os
    project_root = paths.get("project_root", "")
    ui_indicators = ["package.json", "vite.config", "next.config", "nuxt.config", "angular.json", "tailwind.config"]
    for indicator in ui_indicators:
        for ext in [".js", ".ts", ".json", ".mjs"]:
            if os.path.exists(os.path.join(project_root, indicator + ext)):
                return True
            if os.path.exists(os.path.join(project_root, indicator)):
                return True
    return False


# ──────────────────────────────────────────────
# Work Type Classification
# ──────────────────────────────────────────────

WORK_TYPE_KEYWORDS: dict[str, list[str]] = {
    "operational": [
        "run tests", "execute tests", "run test", "execute test",
        "rodar testes", "executar testes", "rodar test", "executar test",
        "run e2e", "execute e2e", "rodar e2e", "executar e2e",
        "run build", "execute build",
        "deploy", "deployar", "migrate", "seed", "rollback",
        "backup", "monitor", "check health", "verify deployment",
        "run lint", "run typecheck", "npm test", "pytest",
        "playwright test", "vitest", "jest",
        "garantir que esteja funcionando", "garantir funcionamento",
        "production readiness", "entregue ao cliente",
        "test suite", "full test", "all tests", "run the test",
    ],
    "operational_single": [
        "testes", "test", "e2e", "build", "deploy", "lint",
        "typecheck", "rodar", "executar",
        "firebase", "production", "staging", "suite",
    ],
    "bugfix": [
        "fix", "repair", "corrigir", "broken", "bug",
        "fix bug", "fix error", "fix test", "fix tests",
        "corrigir erro", "corrigir bug", "corrigir teste",
        "resolve issue", "patch", "hotfix",
    ],
    "bugfix_single": [
        "erro", "error", "falha", "fail", "failing",
    ],
    "feature": [
        "implement", "create", "add feature", "build", "develop",
        "implementar", "criar", "adicionar", "desenvolver",
        "new feature", "nova funcionalidade", "novo recurso",
        "add support", "implement support",
    ],
}


def classify_work_type(work_item: str) -> str:
    """Classify work item as operational, bugfix, or feature.

    Operational: run existing code (tests, builds, deploys).
    Bugfix: fix broken behavior.
    Feature: create new functionality (default).

    Uses two-tier matching:
    1. Multi-word phrases (high confidence, weight=2)
    2. Single words (lower confidence, weight=1)
    """
    text_lower = work_item.lower()

    # Tier 1: Multi-word phrase matches (weight=2)
    operational_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["operational"] if kw in text_lower)
    bugfix_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["bugfix"] if kw in text_lower)
    feature_phrase = sum(2 for kw in WORK_TYPE_KEYWORDS["feature"] if kw in text_lower)

    # Tier 2: Single-word matches (weight=1) — only if no phrase matched
    operational_single = sum(1 for kw in WORK_TYPE_KEYWORDS["operational_single"] if kw in text_lower)
    bugfix_single = sum(1 for kw in WORK_TYPE_KEYWORDS["bugfix_single"] if kw in text_lower)

    operational_score = operational_phrase + operational_single
    bugfix_score = bugfix_phrase + bugfix_single
    feature_score = feature_phrase

    # Operational: needs phrase match (>=2) OR strong single-word signal (>=4)
    if operational_phrase >= 2 or (operational_single >= 4 and operational_score > bugfix_score and operational_score > feature_score):
        return "operational"

    # Bugfix: needs phrase match or single-word signal
    if bugfix_phrase >= 2 or (bugfix_score >= 3 and bugfix_score > feature_score):
        return "bugfix"

    return "feature"


def is_operational_work(work_item: str) -> bool:
    return classify_work_type(work_item) == "operational"


# Stages to deactivate for operational work (no new code creation needed)
OPERATIONAL_EXCLUDED_STAGES: list[str] = [
    "impl.design",
    "impl.code",
    "doc.update",
    "verify",
    "arch.requirements",
    "arch.solution",
    "arch.review",
    "design.user-research",
    "design.personas",
    "design.info-arch",
    "design.interaction",
    "design.design-system",
    "design.visual-design",
    "doc.decisions",
    "doc.project",
]


def deactivate_for_work_type(stages: dict[str, Any], work_type: str) -> dict[str, Any]:
    """Deactivate stages that don't apply for the given work type."""
    if work_type == "feature":
        return stages

    result = dict(stages)
    excluded = []

    if work_type == "operational":
        excluded = OPERATIONAL_EXCLUDED_STAGES
    elif work_type == "bugfix":
        # Bugfix: skip design stages, keep impl but skip heavy architecture
        excluded = [
            "design.user-research", "design.personas", "design.info-arch",
            "design.interaction", "design.design-system", "design.visual-design",
        ]

    for sid in excluded:
        if sid in result:
            result[sid]["done"] = True
            result[sid]["attempts"] = 0
            result[sid]["essence_checked"] = False

    return result

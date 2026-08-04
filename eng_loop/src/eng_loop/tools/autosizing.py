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

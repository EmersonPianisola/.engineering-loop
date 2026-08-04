from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(framework_root: str | Path, loop_root: str | Path) -> dict[str, Any]:
    framework_root = Path(framework_root)
    loop_root = Path(loop_root)

    template_path = framework_root / "config-template.yaml"
    project_path = loop_root / "config.yaml"

    defaults = load_yaml(template_path)

    if project_path.exists():
        project = load_yaml(project_path)
        return deep_merge(defaults, project)

    return defaults


def resolve_paths(config: dict[str, Any], framework_root: str | Path, loop_root: str | Path, project_root: str | Path) -> dict[str, str]:
    framework_root = Path(framework_root)
    loop_root = Path(loop_root)
    project_root = Path(project_root)

    return {
        "framework_root": str(framework_root),
        "loop_root": str(loop_root),
        "project_root": str(project_root),
        "framework_skill_root": str(framework_root / config.get("framework_skill_root", "skills")),
        "framework_reference_root": str(framework_root / config.get("framework_reference_root", "references")),
        "framework_stage_root": str(framework_root / config.get("framework_stage_root", "stages")),
        "framework_template_path": str(framework_root / config.get("framework_template_path", "references/skill-templates.md")),
        "artifact_root": str(loop_root / config.get("artifact_root", "artifacts")),
        "log_root": str(project_root / config.get("log_root", "../_bmad-output/process-logs")),
        "state_file": str(loop_root / config.get("state_file", "state.json")),
        "context_file": str(loop_root / config.get("context_file", "context.md")),
        "planning_artifacts_root": str(loop_root / config.get("planning_artifacts_root", "../_bmad-output/implementation-artifacts")),
    }


def ensure_directories(paths: dict[str, str]) -> None:
    dirs = [
        paths["artifact_root"],
        paths["log_root"],
        f"{paths['artifact_root']}/architectures",
        f"{paths['artifact_root']}/blueprints",
        f"{paths['artifact_root']}/bdd-journeys",
        f"{paths['artifact_root']}/design",
        f"{paths['artifact_root']}/test-plans",
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

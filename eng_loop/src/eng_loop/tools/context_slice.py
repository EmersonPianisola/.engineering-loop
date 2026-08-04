from __future__ import annotations

from pathlib import Path
from typing import Any


CONTEXT_SLICE_RULES: dict[str, dict[str, list[str]]] = {
    "verify": {"include": ["blueprint", "source_diff", "test_files"], "exclude": ["full_context", "other_specs"]},
    "qa.security": {"include": ["diff", "blueprint", "architecture"], "exclude": ["test_files"]},
    "qa.api-contract": {"include": ["blueprint", "api_source", "integration_tests"], "exclude": ["e2e_tests", "full_diff"]},
    "qa.performance": {"include": ["blueprint", "architecture", "build_output"], "exclude": ["test_files"]},
    "impl.code": {"include": ["blueprint", "work_item", "lessons"], "exclude": []},
    "impl.design": {"include": ["architecture", "work_item"], "exclude": []},
}


def build_context_slice(
    stage_id: str,
    paths: dict[str, str],
    stage_artifacts: dict[str, str],
    config: dict[str, Any],
) -> str:
    agent_limit = config.get("hardware", {}).get("agent_context_limit", 66666)
    rules = CONTEXT_SLICE_RULES.get(stage_id, {"include": ["work_item", "blueprint"], "exclude": []})

    parts = []
    parts.append(f"# Context for stage: {stage_id}")
    parts.append(f"# Context limit: {agent_limit} tokens")
    parts.append("")

    artifact_root = paths.get("artifact_root", "")

    for key in rules["include"]:
        content = _resolve_context_key(key, stage_id, stage_artifacts, artifact_root)
        if content:
            parts.append(f"## {key}")
            parts.append(content)
            parts.append("")

    result = "\n".join(parts)
    return _enforce_token_limit(result, agent_limit)


def _resolve_context_key(key: str, stage_id: str, stage_artifacts: dict[str, str], artifact_root: str) -> str:
    import json

    if key == "work_item":
        return stage_artifacts.get("work_item", "")
    if key == "blueprint":
        bp = stage_artifacts.get("impl.design", "")
        if not bp:
            bp_path = Path(artifact_root) / "blueprints"
            if bp_path.exists():
                for f in sorted(bp_path.glob("*.md")):
                    bp = f.read_text(encoding="utf-8")
                    break
        return bp
    if key == "architecture":
        arch = stage_artifacts.get("arch.solution", "")
        if not arch:
            arch_path = Path(artifact_root) / "architectures"
            if arch_path.exists():
                for f in sorted(arch_path.glob("*.md")):
                    arch += f.read_text(encoding="utf-8") + "\n"
        return arch
    if key == "source_diff" or key == "diff":
        return stage_artifacts.get("diff", "")
    if key == "test_files":
        return stage_artifacts.get("test_files", "")
    if key == "api_source":
        return stage_artifacts.get("api_source", "")
    if key == "integration_tests":
        return stage_artifacts.get("integration_tests", "")
    if key == "e2e_tests":
        return stage_artifacts.get("e2e_tests", "")
    if key == "build_output":
        return stage_artifacts.get("build_output", "")
    if key == "full_diff":
        return stage_artifacts.get("full_diff", "")
    if key == "lessons":
        lessons = stage_artifacts.get("lessons", "[]")
        try:
            parsed = json.loads(lessons) if isinstance(lessons, str) else lessons
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return str(lessons)
    if key == "full_context":
        return "\n".join(f"## {k}\n{v}\n" for k, v in stage_artifacts.items())
    if key == "other_specs":
        return ""
    return ""


def _enforce_token_limit(text: str, token_limit: int) -> str:
    estimated_chars = token_limit * 4
    if len(text) > estimated_chars:
        return text[:estimated_chars] + "\n\n... [truncated — context limit reached] ..."
    return text

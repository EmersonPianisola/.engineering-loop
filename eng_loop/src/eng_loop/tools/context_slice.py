from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# CONTEXT SLICE — Selective context assembler per stage
# ============================================================
# Replaces inline artifact embedding in node handlers.
# Supports reference mode (paths only) and inline mode (full content).
# ============================================================

CONTEXT_SLICE_RULES: dict[str, dict[str, list[str]]] = {
    "init": {"include": [], "exclude": []},
    "init.ideate": {"include": [], "exclude": []},
    "init.bdd": {"include": [], "exclude": []},
    "init.refine": {"include": [], "exclude": []},
    "design.user-research": {"include": ["journey_map"], "exclude": []},
    "design.personas": {"include": ["journey_map"], "exclude": []},
    "design.info-arch": {"include": ["journey_map"], "exclude": []},
    "design.interaction": {"include": ["journey_map"], "exclude": []},
    "design.design-system": {"include": ["journey_map"], "exclude": []},
    "design.visual-design": {"include": ["journey_map"], "exclude": []},
    "arch.requirements": {"include": [], "exclude": []},
    "arch.solution": {"include": ["arch_requirements"], "exclude": []},
    "arch.review": {"include": ["arch_requirements", "architecture"], "exclude": []},
    "impl.design": {"include": ["architecture"], "exclude": []},
    "impl.code": {"include": ["blueprint", "lessons"], "exclude": []},
    "doc.update": {"include": ["blueprint", "diff"], "exclude": []},
    "verify": {"include": ["blueprint", "diff"], "exclude": []},
    "e2e.execute": {"include": ["blueprint"], "exclude": []},
    "qa.static": {"include": ["blueprint", "diff"], "exclude": []},
    "qa.unit": {"include": ["blueprint", "diff"], "exclude": []},
    "qa.integration": {"include": ["blueprint", "diff"], "exclude": []},
    "qa.security": {"include": ["blueprint", "diff", "architecture"], "exclude": []},
    "qa.api-contract": {"include": ["blueprint", "diff"], "exclude": []},
    "qa.performance": {"include": ["blueprint", "diff", "architecture"], "exclude": []},
    "qa.human.flow": {"include": ["blueprint"], "exclude": []},
    "qa.human.ux": {"include": ["blueprint"], "exclude": []},
    "deploy.prepare": {"include": ["blueprint", "diff"], "exclude": []},
    "smoke.test": {"include": ["blueprint"], "exclude": []},
    "doc.decisions": {"include": [], "exclude": []},
    "doc.project": {"include": ["blueprint"], "exclude": []},
    "post": {"include": [], "exclude": []},
}

ARTIFACT_RESOLVERS: dict[str, dict[str, Any]] = {
    "work_item": {"source": "state", "key": "work_item"},
    "blueprint": {
        "source": "artifact",
        "state_key": "impl.design",
        "disk_path": "blueprints/blueprint.md",
    },
    "architecture": {
        "source": "artifact",
        "state_key": "arch.solution",
        "disk_path": "architectures/arch-solution.md",
    },
    "arch_requirements": {
        "source": "artifact",
        "state_key": "arch.requirements",
        "disk_path": "architectures/arch-requirements.md",
    },
    "diff": {
        "source": "artifact",
        "state_key": "diff",
        "disk_path": None,
    },
    "source_diff": {
        "source": "artifact",
        "state_key": "diff",
        "disk_path": None,
    },
    "lessons": {
        "source": "artifact",
        "state_key": "lessons",
        "disk_path": "lessons.json",
    },
    "journey_map": {
        "source": "artifact",
        "state_key": "init.bdd",
        "disk_path": "bdd-journeys/journey.md",
    },
    "test_files": {
        "source": "artifact",
        "state_key": "test_files",
        "disk_path": None,
    },
    "api_source": {
        "source": "artifact",
        "state_key": "api_source",
        "disk_path": None,
    },
    "integration_tests": {
        "source": "artifact",
        "state_key": "integration_tests",
        "disk_path": None,
    },
    "e2e_tests": {
        "source": "artifact",
        "state_key": "e2e_tests",
        "disk_path": None,
    },
    "build_output": {
        "source": "artifact",
        "state_key": "build_output",
        "disk_path": None,
    },
    "full_diff": {
        "source": "artifact",
        "state_key": "diff",
        "disk_path": None,
    },
    "full_context": {
        "source": "all_artifacts",
    },
}


def build_context_slice(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, str],
    config: dict[str, Any],
    *,
    use_references: bool = True,
    inline_threshold: int = 3000,
) -> str:
    """Build context slice for a stage.

    Args:
        stage_id: The stage identifier (e.g., "impl.code")
        state: The full PipelineState
        paths: Resolved filesystem paths
        config: Merged configuration
        use_references: If True, emit file paths instead of content for large artifacts
        inline_threshold: Characters below which content is inlined regardless

    Returns:
        Markdown-formatted context section, or empty string if nothing to include.
    """
    agent_limit = config.get("hardware", {}).get("agent_context_limit", 66666)
    rules = CONTEXT_SLICE_RULES.get(stage_id, {"include": ["work_item", "blueprint"], "exclude": []})

    parts = []
    parts.append(f"# Context for stage: {stage_id}")
    parts.append(f"# Context limit: {agent_limit} tokens")
    parts.append("")

    stage_artifacts = state.get("stage_artifacts", {})
    artifact_root = paths.get("artifact_root", "")

    for key in rules["include"]:
        if key in rules.get("exclude", []):
            continue

        content = _resolve_context_key(key, stage_id, state, stage_artifacts, artifact_root)
        if not content:
            continue

        if use_references and len(content) > inline_threshold:
            ref_path = _get_reference_path(key, artifact_root)
            if ref_path:
                parts.append(f"## {key}")
                parts.append(f"Path: {ref_path}")
                parts.append("Use `read` tool to access this artifact.")
                parts.append("")
                continue

        parts.append(f"## {key}")
        parts.append(content)
        parts.append("")

    result = "\n".join(parts)
    return _enforce_token_limit(result, agent_limit)


def build_context_slice_references(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, str],
    config: dict[str, Any],
) -> str:
    """Build context slice using references only (no inline content).

    Maximum token efficiency — artifacts are accessed via read tool.
    """
    return build_context_slice(
        stage_id,
        state,
        paths,
        config,
        use_references=True,
        inline_threshold=0,
    )


def _resolve_context_key(
    key: str,
    stage_id: str,
    state: dict[str, Any],
    stage_artifacts: dict[str, str],
    artifact_root: str,
) -> str:
    resolver = ARTIFACT_RESOLVERS.get(key)
    if not resolver:
        return ""

    source = resolver.get("source")

    if source == "state":
        return state.get(resolver["key"], "")

    if source == "all_artifacts":
        return "\n".join(f"## {k}\n{v}\n" for k, v in stage_artifacts.items())

    if source == "artifact":
        state_key = resolver.get("state_key", "")
        content = stage_artifacts.get(state_key, "")

        if not content and resolver.get("disk_path") and artifact_root:
            disk_path = Path(artifact_root) / resolver["disk_path"]
            if disk_path.exists():
                content = disk_path.read_text(encoding="utf-8")

        if key == "lessons" and content:
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
                return json.dumps(parsed, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass

        return content

    return ""


def _get_reference_path(key: str, artifact_root: str) -> str | None:
    resolver = ARTIFACT_RESOLVERS.get(key)
    if not resolver:
        return None

    disk_path = resolver.get("disk_path")
    if disk_path and artifact_root:
        return f"{artifact_root}/{disk_path}"

    return None


def _enforce_token_limit(text: str, token_limit: int) -> str:
    """Enforce token limit on context slice.

    DEPRECATED: Hard truncation replaced by agent lifecycle management.
    When an agent's budget is exhausted, a new agent is spawned with distilled context.
    This function now returns text unchanged.
    """
    # Agent lifecycle handles budget enforcement via spawn transitions.
    # Returning full text preserves all context.
    return text


def get_available_artifacts(state: dict[str, Any], paths: dict[str, str]) -> list[str]:
    """List available artifact keys for debugging/observability."""
    stage_artifacts = state.get("stage_artifacts", {})
    artifact_root = paths.get("artifact_root", "")

    available = list(stage_artifacts.keys())

    for key, resolver in ARTIFACT_RESOLVERS.items():
        if key in available:
            continue
        disk_path = resolver.get("disk_path")
        if disk_path and artifact_root:
            full_path = Path(artifact_root) / disk_path
            if full_path.exists():
                available.append(key)

    return available

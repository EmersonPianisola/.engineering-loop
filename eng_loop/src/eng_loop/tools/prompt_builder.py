from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileCache:
    """In-memory cache for stage procedures, skills, and reference files.

    Eliminates redundant disk reads on retries. Cache is keyed by file path
    and invalidated on explicit clear() or when max_entries is exceeded.
    """

    def __init__(self, max_entries: int = 200, ttl_seconds: int = 600):
        self._cache: dict[str, tuple[str, float]] = {}
        self._max_entries = max_entries
        self._ttl = ttl_seconds

    def get(self, file_path: str) -> str | None:
        entry = self._cache.get(file_path)
        if entry is None:
            return None
        content, loaded_at = entry
        if time.time() - loaded_at > self._ttl:
            del self._cache[file_path]
            return None
        return content

    def put(self, file_path: str, content: str) -> None:
        if len(self._cache) >= self._max_entries:
            oldest_path = next(iter(self._cache))
            del self._cache[oldest_path]
        self._cache[file_path] = (content, time.time())

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


GLOBAL_FILE_CACHE = FileCache()


def load_cached_markdown(file_path: str | Path) -> str:
    """Load a markdown file, using the global cache."""
    path_str = str(file_path)
    cached = GLOBAL_FILE_CACHE.get(path_str)
    if cached is not None:
        return cached

    p = Path(file_path)
    if not p.exists():
        return ""

    content = p.read_text(encoding="utf-8")
    GLOBAL_FILE_CACHE.put(path_str, content)
    return content


def clear_file_cache() -> None:
    GLOBAL_FILE_CACHE.clear()


# ============================================================
# STAGE CONTEXT CONFIGURATION
# ============================================================

ARTIFECT_KEY_MAP: dict[str, dict[str, str]] = {
    "blueprint": {"artifact_key": "impl.design", "disk_path": "blueprints/blueprint.md"},
    "architecture": {"artifact_key": "arch.solution", "disk_path": "architectures/arch-solution.md"},
    "arch_requirements": {"artifact_key": "arch.requirements", "disk_path": "architectures/arch-requirements.md"},
    "diff": {"artifact_key": "diff", "disk_path": None},
    "lessons": {"artifact_key": "lessons", "disk_path": "lessons.json"},
    "journey_map": {"artifact_key": "init.bdd", "disk_path": "bdd-journeys/journey.md"},
    "validation": {"artifact_key": "verify", "disk_path": "validation.md"},
    "e2e_report": {"artifact_key": "e2e.execute", "disk_path": "e2e-report.md"},
}


STAGE_ARTIFACT_INCLUDES: dict[str, list[str]] = {
    "init": [],
    "init.ideate": [],
    "init.bdd": [],
    "init.refine": [],
    "design.user-research": ["journey_map"],
    "design.personas": ["journey_map"],
    "design.info-arch": ["journey_map"],
    "design.interaction": ["journey_map"],
    "design.design-system": ["journey_map"],
    "design.visual-design": ["journey_map"],
    "arch.requirements": [],
    "arch.solution": ["arch_requirements"],
    "arch.review": ["arch_requirements", "architecture"],
    "impl.design": ["architecture"],
    "impl.code": ["blueprint", "lessons"],
    "doc.update": ["blueprint", "diff"],
    "verify": ["blueprint", "diff"],
    "e2e.execute": ["blueprint"],
    "qa.security": ["blueprint", "diff"],
    "qa.api-contract": ["blueprint", "diff"],
    "qa.performance": ["blueprint", "diff"],
    "deploy.prepare": ["blueprint", "diff"],
    "smoke.test": ["blueprint"],
    "doc.decisions": [],
    "doc.project": ["blueprint"],
    "post": [],
}


# ============================================================
# PROMPT BUILDER
# ============================================================


class SystemPrefix:
    """Shared system prefix that is constructed once and reused across stages.

    Eliminates ~25,000-35,000 tokens of redundant boilerplate per loop run.
    """

    def __init__(self, state: dict[str, Any], paths: dict[str, str], config: dict[str, Any]):
        self._state = state
        self._paths = paths
        self._config = config
        self._prefix: str | None = None
        self._hash: str | None = None

    def build(self) -> str:
        state_hash = self._compute_hash()
        if self._hash == state_hash and self._prefix:
            return self._prefix

        parts = []

        work_item = self._state.get("work_item", "")
        if work_item:
            parts.append(f"## WORK ITEM\n{work_item}")

        project_root = self._paths.get("project_root", ".")
        if project_root:
            parts.append(f"## PROJECT ROOT\n{project_root}")

        complexity = self._state.get("complexity", "unset")
        if complexity:
            parts.append(f"## COMPLEXITY\n{complexity}")

        work_type = self._state.get("work_type", "feature")
        if work_type:
            parts.append(f"## WORK TYPE\n{work_type}")

        ui_project = self._state.get("ui_project", False)
        if ui_project:
            parts.append("## UI PROJECT\ntrue")

        ideation = self._state.get("ideation", "")
        if ideation:
            parts.append(f"## IDEATION\n{ideation}")

        # Project Map — pre-computed structural overview (eliminates exploratory glob/read)
        project_map_section = self._get_project_map_section()
        if project_map_section:
            parts.append(project_map_section)

        decisions = self._state.get("decisions", [])
        if decisions:
            parts.append("## DECISIONS (accumulated)")
            for d in decisions:
                parts.append(f"- {d}")

        self._prefix = "\n\n".join(parts)
        self._hash = state_hash
        return self._prefix

    def _get_project_map_section(self) -> str:
        """Get project map section from state. Returns empty string if not built."""
        pm_data = self._state.get("project_map")
        if not pm_data or not pm_data.get("tree"):
            return ""
        from eng_loop.tools.project_map import ProjectMap

        pm = ProjectMap.from_dict(pm_data)
        return pm.to_prompt_section()

    def _compute_hash(self) -> str:
        hashable = (
            self._state.get("work_item", ""),
            self._state.get("complexity", ""),
            self._state.get("work_type", ""),
            self._state.get("ui_project", False),
            self._state.get("ideation", ""),
            str(self._state.get("decisions", [])),
            str(self._state.get("project_map", {}).get("tree", "")[:500]),
            str(self._paths),
        )
        return hashlib.md5(str(hashable).encode()).hexdigest()


class StageContext:
    """Per-stage context: procedure, skill, upstream artifacts, handoffs.

    Replaces inline f-string prompt construction in each node handler.
    Uses artifact references (paths) instead of full content to reduce tokens.
    Falls back to inline content only when the artifact is small enough.
    """

    INLINE_MAX_CHARS = 3000

    def __init__(
        self,
        stage_id: str,
        state: dict[str, Any],
        paths: dict[str, str],
        config: dict[str, Any],
        role_description: str = "",
        stage_proc: str = "",
        skill_content: str = "",
        graphify_injection: str = "",
        use_references: bool = True,
    ):
        self.stage_id = stage_id
        self.state = state
        self.paths = paths
        self.config = config
        self.role_description = role_description
        self.stage_proc = stage_proc
        self.skill_content = skill_content
        self.graphify_injection = graphify_injection
        self.use_references = use_references

    def build(self) -> str:
        parts = []

        if self.role_description:
            parts.append(f"You are the {self.role_description} for stage: {self.stage_id}.")
            parts.append("")

        if self.skill_content:
            parts.append("## SKILL")
            parts.append(self.skill_content)
            parts.append("")

        if self.stage_proc:
            parts.append("## PROCEDURE")
            parts.append(self.stage_proc)
            parts.append("")

        if self.graphify_injection:
            parts.append(self.graphify_injection)
            parts.append("")

        artifact_sections = self._build_artifact_sections()
        if artifact_sections:
            parts.append(artifact_sections)

        handoff_sections = self._build_handoff_sections()
        if handoff_sections:
            parts.append(handoff_sections)

        return "\n".join(parts)

    def _build_artifact_sections(self) -> str:
        includes = STAGE_ARTIFACT_INCLUDES.get(self.stage_id, [])
        if not includes:
            return ""

        parts = []
        stage_artifacts = self.state.get("stage_artifacts", {})
        artifact_root = self.paths.get("artifact_root", "")

        for key in includes:
            mapping = ARTIFECT_KEY_MAP.get(key)
            if not mapping:
                continue

            content = stage_artifacts.get(mapping["artifact_key"], "")

            if not content and mapping["disk_path"] and artifact_root:
                disk_path = Path(artifact_root) / mapping["disk_path"]
                if disk_path.exists():
                    content = disk_path.read_text(encoding="utf-8")

            if not content:
                continue

            if self.use_references and len(content) > self.INLINE_MAX_CHARS:
                ref_path = mapping["disk_path"] or f"(in-memory artifact: {key})"
                parts.append(f"## {key.upper().replace('_', ' ')}")
                parts.append(f"Path: {ref_path}")
                parts.append("Use `read` tool to access this artifact. Do NOT embed content in your reasoning.")
                parts.append("")
            else:
                parts.append(f"## {key.upper().replace('_', ' ')}")
                parts.append(content)
                parts.append("")

        return "\n".join(parts) if parts else ""

    def _build_handoff_sections(self) -> str:
        handoffs = self.state.get("handoffs", {})
        if not handoffs:
            return ""

        relevant = self._get_relevant_handoffs()
        if not relevant:
            return ""

        parts = ["## PRIOR STAGE HANDOFFS"]
        for stage_id, summary in relevant:
            parts.append(f"### {stage_id}")
            parts.append(summary)
            parts.append("")

        return "\n".join(parts)

    def _get_relevant_handoffs(self) -> list[tuple[str, str]]:
        handoffs = self.state.get("handoffs", {})
        stage_deps = self._get_upstream_stages()
        result = []
        for dep in stage_deps:
            if dep in handoffs:
                result.append((dep, handoffs[dep]))
        return result

    def _get_upstream_stages(self) -> list[str]:
        from eng_loop.state import STAGE_ORDER

        current_idx = None
        for i, s in enumerate(STAGE_ORDER):
            if s == self.stage_id:
                current_idx = i
                break
        if current_idx is None or current_idx <= 0:
            return []
        recent = STAGE_ORDER[max(0, current_idx - 5) : current_idx]
        return list(reversed(recent))


class PromptBuilder:
    """Centralized prompt builder for all stages.

    Usage in node handlers:
        builder = PromptBuilder(state, paths, config)
        prompt = builder.build(
            stage_id="impl.code",
            role_description="Implementation agent",
            stage_proc=stage_proc,
            instructions="Execute the work item using TDD...",
        )
    """

    def __init__(self, state: dict[str, Any], paths: dict[str, str], config: dict[str, Any]):
        self.state = state
        self.paths = paths
        self.config = config
        self._system_prefix = SystemPrefix(state, paths, config)

    def build(
        self,
        stage_id: str,
        *,
        role_description: str = "",
        stage_proc: str = "",
        skill_content: str = "",
        graphify_injection: str = "",
        instructions: str = "",
        use_artifact_references: bool = True,
        extra_sections: str = "",
    ) -> str:
        prefix = self._system_prefix.build()

        ctx = StageContext(
            stage_id=stage_id,
            state=self.state,
            paths=self.paths,
            config=self.config,
            role_description=role_description,
            stage_proc=stage_proc,
            skill_content=skill_content,
            graphify_injection=graphify_injection,
            use_references=use_artifact_references,
        )
        stage_context = ctx.build()

        parts = []
        if prefix:
            parts.append(prefix)
        if stage_context:
            parts.append(stage_context)
        if extra_sections:
            parts.append(extra_sections)
        if instructions:
            parts.append("")
            parts.append(instructions)

        return "\n".join(parts)

    def get_system_prefix(self) -> str:
        return self._system_prefix.build()

    def get_stage_context(
        self,
        stage_id: str,
        *,
        role_description: str = "",
        stage_proc: str = "",
        skill_content: str = "",
        graphify_injection: str = "",
        use_artifact_references: bool = True,
    ) -> str:
        ctx = StageContext(
            stage_id=stage_id,
            state=self.state,
            paths=self.paths,
            config=self.config,
            role_description=role_description,
            stage_proc=stage_proc,
            skill_content=skill_content,
            graphify_injection=graphify_injection,
            use_references=use_artifact_references,
        )
        return ctx.build()

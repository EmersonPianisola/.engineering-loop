from __future__ import annotations

import os
from typing import Any

from eng_loop.templates import get_skill_name, get_stage_file, load_skill, load_stage_procedure
from eng_loop.tools.graphify import get_graphify_injection, precompute_graph_context
from eng_loop.tools.prompt_builder import PromptBuilder


def build_node_prompt(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, Any],
    config: dict[str, Any],
    *,
    role_description: str = "",
    instructions: str = "",
    extra_sections: str = "",
    include_skill: bool = True,
    include_procedure: bool = True,
    use_artifact_references: bool = True,
    include_graph_context: bool = True,
) -> str:
    """Build a stage prompt using the centralized PromptBuilder.

    Replaces inline f-string prompt construction. Eliminates redundant
    work_item, project_root, graphify_injection, and boilerplate sections.

    Args:
        stage_id: Stage identifier (e.g., "impl.code")
        state: PipelineState
        paths: Resolved filesystem paths
        config: Merged configuration
        role_description: Role for the agent (e.g., "Implementation agent")
        instructions: Stage-specific instructions appended at the end
        extra_sections: Additional markdown sections to inject
        include_skill: Whether to load and include the skill file
        include_procedure: Whether to load and include the stage procedure
        use_artifact_references: Use file paths instead of inline content
        include_graph_context: Whether to pre-compute graph context and inject it

    Returns:
        Complete prompt string ready for agent invocation.
    """
    stage_file = get_stage_file(stage_id)
    skill_name = get_skill_name(stage_id)

    stage_proc = ""
    if include_procedure:
        stage_proc = load_stage_procedure(paths.get("framework_stage_root", ""), stage_file)

    skill_content = ""
    if include_skill and not (skill_name.startswith("__") and skill_name.endswith("__")):
        skill_content = load_skill(paths.get("framework_skill_root", ""), skill_name)

    # Graphify tools are NOT available in opencode backend (subprocess mode).
    # In that mode, rely entirely on pre-computed graph context in the prompt.
    _is_opencode = os.environ.get("ENG_AGENT_BACKEND", "") == "opencode"
    graphify_injection = get_graphify_injection(state, paths, tools_available=not _is_opencode)

    # Pre-compute graph context from work item and blueprint entities
    # In opencode mode, this is the PRIMARY mechanism — use more entities
    graph_context = ""
    if include_graph_context:
        max_entities = 8 if _is_opencode else 5
        graph_context = precompute_graph_context(state, paths, config, max_entities=max_entities)

    # Combine pre-computed graph context with any extra sections
    combined_extra = ""
    parts = []
    if graph_context:
        parts.append(graph_context)
    if extra_sections:
        parts.append(extra_sections)
    combined_extra = "\n\n".join(parts)

    builder = PromptBuilder(state, paths, config)
    return builder.build(
        stage_id,
        role_description=role_description,
        stage_proc=stage_proc,
        skill_content=skill_content,
        graphify_injection=graphify_injection,
        instructions=instructions,
        use_artifact_references=use_artifact_references,
        extra_sections=combined_extra,
    )


def build_handoff_update(
    stage_id: str,
    stage_result: dict[str, Any],
    decisions: list[str],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Build the handoff state update after a stage completes.

    Creates a compact summary of what the stage accomplished for downstream stages.
    """
    from eng_loop.tools.context_consolidator import (
        build_handoff_summary,
        deduplicate_stage_artifacts,
    )

    handoff = build_handoff_summary(stage_id, stage_result, decisions)
    existing_handoffs = dict(state.get("handoffs", {}))
    existing_handoffs[stage_id] = handoff

    current_artifacts = dict(state.get("stage_artifacts", {}))
    deduped, _ = deduplicate_stage_artifacts(current_artifacts)

    return {
        "handoffs": existing_handoffs,
        "stage_artifacts": deduped,
    }

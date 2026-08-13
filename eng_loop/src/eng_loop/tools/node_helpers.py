from __future__ import annotations

from typing import Any

from eng_loop.tools.graphify import get_graphify_injection
from eng_loop.tools.prompt_builder import PromptBuilder
from eng_loop.templates import load_skill, load_stage_procedure, get_stage_file, get_skill_name


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

    Returns:
        Complete prompt string ready for agent invocation.
    """
    stage_file = get_stage_file(stage_id)
    skill_name = get_skill_name(stage_id)

    stage_proc = ""
    if include_procedure:
        stage_proc = load_stage_procedure(
            paths.get("framework_stage_root", ""), stage_file
        )

    skill_content = ""
    if include_skill and not (skill_name.startswith("__") and skill_name.endswith("__")):
        skill_content = load_skill(
            paths.get("framework_skill_root", ""), skill_name
        )

    graphify_injection = get_graphify_injection(state, paths)

    builder = PromptBuilder(state, paths, config)
    return builder.build(
        stage_id,
        role_description=role_description,
        stage_proc=stage_proc,
        skill_content=skill_content,
        graphify_injection=graphify_injection,
        instructions=instructions,
        use_artifact_references=use_artifact_references,
        extra_sections=extra_sections,
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

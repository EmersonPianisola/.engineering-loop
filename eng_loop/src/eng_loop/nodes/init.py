from __future__ import annotations

from typing import Any

from eng_loop.model import create_model_from_config
from eng_loop.schemas import InitBddOutput, InitIdeateOutput, InitOutput, InitRefineOutput
from eng_loop.tools.essence_gate import build_essence_state, run_essence_gate
from eng_loop.tools.evidence_gate import validate_stage_output
from eng_loop.tools.file_ops import read_file
from eng_loop.tools.node_helpers import build_handoff_update, build_node_prompt
from eng_loop.tools.progress import (
    log_artifact,
    log_blocked,
    log_stage_done,
    log_stage_fail,
    log_stage_skip,
)


def _handle_essence_result(
    stage_id: str,
    essence,
    state: dict[str, Any],
    config: dict[str, Any],
    stages: dict[str, Any],
) -> dict[str, Any] | None:
    """Handle essence gate result. Returns dict if blocked/waiting, None to continue."""
    if essence.blocked:
        return {
            "status": "blocked",
            "blocking_condition": f"Essence Lens 4 tension in {stage_id}: {essence.tension}",
            "stages": stages,
            "essence_tension": essence.tension,
        }
    if essence.waiting_for_input:
        essence_state = build_essence_state(stage_id, essence, state, config)
        return {
            "status": "waiting_for_input",
            "blocking_condition": "essence_clarification_needed",
            "stages": stages,
            "essence": essence_state,
            "essence_clarifying_questions": essence.clarifying_questions,
        }
    return None


def _resolve_work_item(work_item: Any) -> str:
    from pathlib import Path

    from eng_loop.state import get_work_item_text

    cleaned = get_work_item_text({"work_item": work_item}).strip().strip("'\"")
    p = Path(cleaned)
    if p.exists() and p.is_file():
        return read_file(cleaned)
    return cleaned


def init_node(state: dict[str, Any]) -> dict[str, Any]:
    """Cognitive node — validates work item via LLM.

    Reads classification results from state['codebase_facts'] (computed
    by init_setup_node). Does NOT perform classification, graphify,
    or stage deactivation here — that is the setup node's job.
    """
    import logging as _logging

    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    _dbg = _logging.getLogger(__name__)

    stage_id = "init"
    config = state.get("config", {})
    paths = state.get("paths", {})
    stages = dict(state.get("stages", {}))

    # Essence gate — validate inputs before stage execution
    essence = run_essence_gate(stage_id, state, paths, config)
    essence_result = _handle_essence_result(stage_id, essence, state, config, stages)
    if essence_result:
        return essence_result
    if essence.updated_state and essence.updated_state.get("stages"):
        stages = essence.updated_state["stages"]

    work_item = _resolve_work_item(state.get("work_item", ""))

    # Read cached classification from codebase_facts
    codebase_facts = state.get("codebase_facts", {})
    complexity = state.get("complexity", codebase_facts.get("complexity", "unset"))
    ui_project = state.get("ui_project", codebase_facts.get("ui_project", False))

    _dbg.debug(
        "[DEBUG] init_node: work_item=%r, complexity=%s, ui=%s, max_agent_iterations=%d",
        work_item[:120],
        complexity,
        ui_project,
        config.get("agent", {}).get("max_agent_iterations", 25),
    )

    prompt = build_node_prompt(
        "init",
        state,
        paths,
        config,
        role_description="Engineering Loop INIT agent",
        extra_sections=(f"## COMPLEXITY CLASSIFICATION\n{complexity}\n\n## CODEBASE FACTS\n{codebase_facts}"),
        instructions=(
            f"Validate the work item and prepare for the loop.\n"
            f"Work item: {work_item}\n\n"
            "Explore the project briefly (glob + read key files). Validate the work item.\n"
            "Return a JSON object with these fields: valid, work_item_refined, estimated_files, estimated_tasks, notes."
        ),
    )

    model = create_model_from_config(state.get("config", {}), stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=InitOutput,
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    if agent_result.error:
        log_blocked("input not ready for engineering")
        return {
            "status": "blocked",
            "blocking_condition": f"init agent error: {agent_result.error}",
            "stages": stages,
            "complexity": complexity,
            "ui_project": ui_project,
        }

    valid = result.get("valid", False)
    if not valid and result.get("work_item_refined"):
        valid = True

    if not valid:
        log_blocked("input not ready for engineering")
        return {
            "status": "blocked",
            "blocking_condition": "input not ready for engineering",
            "stages": stages,
            "complexity": complexity,
            "ui_project": ui_project,
        }

    stages["init"]["done"] = True
    stages["init"]["attempts"] = 1
    log_stage_done(stage_id, result.get("notes", "validated"))

    refined = result.get("work_item_refined", work_item)
    handoff_update = build_handoff_update(stage_id, result, [], state)

    return {
        "stages": stages,
        "complexity": complexity,
        "ui_project": ui_project,
        "work_item": refined,
        "graphify": codebase_facts.get("graphify", {}),
        **handoff_update,
    }


def init_ideate_node(state: dict[str, Any]) -> dict[str, Any]:
    import logging as _logging

    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    _dbg = _logging.getLogger(__name__)

    stages = dict(state.get("stages", {}))
    stage_id = "init.ideate"
    config = state.get("config", {})
    paths = state.get("paths", {})

    # Essence gate
    essence = run_essence_gate(stage_id, state, paths, config)
    essence_result = _handle_essence_result(stage_id, essence, state, config, stages)
    if essence_result:
        return essence_result
    if essence.updated_state and essence.updated_state.get("stages"):
        stages = essence.updated_state["stages"]

    if stages.get(stage_id, {}).get("done", False):
        log_stage_skip(stage_id)
        return {}
    max_attempts = config.get("constraints", {}).get("max_init_ideate_attempts", 3)
    current_attempts = stages[stage_id].get("attempts", 0)
    _dbg.debug(
        "[DEBUG] init_ideate_node: attempts=%d/%d, max_agent_iterations=%d",
        current_attempts,
        max_attempts,
        config.get("agent", {}).get("max_agent_iterations", 25),
    )

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        log_stage_fail(stage_id, "non-convergence")
        return {
            "stages": stages,
            "status": "blocked",
            "blocking_condition": f"{stage_id} non-convergence",
        }

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="BMAD Ideation agent",
        instructions=(
            "Ideate on the work item and decompose into tasks.\n"
            "Explore the project briefly with read/glob if needed.\n"
            "Return a JSON object with these fields: ideation_results, decomposed_tasks, ready_for_next."
        ),
    )
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=InitIdeateOutput,
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    if agent_result.error:
        _dbg.error(
            "[DEBUG] init_ideate_node: agent_result.error=%s, iterations=%d, elapsed=%.1fs, tool_calls=%d, data=%s",
            agent_result.error,
            agent_result.iterations,
            agent_result.elapsed,
            agent_result.tool_calls_made,
            str(agent_result.data)[:300],
        )
        log_stage_fail(stage_id, agent_result.error)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            _dbg.warning("[DEBUG] init_ideate_node: RETRYING attempt %d/%d", stages[stage_id]["attempts"], max_attempts)
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
            }
        _dbg.error("[DEBUG] init_ideate_node: BLOCKED — max attempts %d reached", max_attempts)
        stages[stage_id]["done"] = True
        return {
            "stages": stages,
            "status": "blocked",
            "blocking_condition": f"{stage_id} agent error",
        }

    # Evidence gate
    is_valid, error_msg = validate_stage_output(stage_id, result, str(result))
    if not is_valid:
        log_stage_fail(stage_id, f"evidence gate: {error_msg}")
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} evidence: {error_msg}"],
            }

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)
    log_stage_done(stage_id, str(result.get("decomposed_tasks", ""))[:120])

    handoff_update = build_handoff_update(stage_id, result, [], state)

    return {
        "stages": stages,
        "ideation": result.get("ideation_results", ""),
        **handoff_update,
    }


def init_bdd_node(state: dict[str, Any]) -> dict[str, Any]:
    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    stages = dict(state.get("stages", {}))
    stage_id = "init.bdd"
    config = state.get("config", {})
    paths = state.get("paths", {})

    # Essence gate
    essence = run_essence_gate(stage_id, state, paths, config)
    essence_result = _handle_essence_result(stage_id, essence, state, config, stages)
    if essence_result:
        return essence_result
    if essence.updated_state and essence.updated_state.get("stages"):
        stages = essence.updated_state["stages"]

    if stages.get(stage_id, {}).get("done", False):
        log_stage_skip(stage_id)
        return {}
    max_attempts = config.get("constraints", {}).get("max_init_bdd_attempts", 2)

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        log_stage_done(stage_id, "max attempts reached, proceeding")
        return {}

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="BDD Journey Mapper",
        instructions=(
            "Map user journeys with Gherkin scenarios. Keep it concise.\n"
            "Return a JSON object with these fields: journey_map, gherkin_scenarios, complete."
        ),
    )
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=InitBddOutput,
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    if agent_result.error:
        log_stage_fail(stage_id, agent_result.error)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
            }
        stages[stage_id]["done"] = True
        return {}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    artifact_root = paths.get("artifact_root", "")
    journey_content = result.get("journey_map", "")
    if isinstance(journey_content, dict):
        import json

        journey_content = json.dumps(journey_content, indent=2, ensure_ascii=False)
    if journey_content:
        from eng_loop.tools.file_ops import write_file

        artifact_path = f"{artifact_root}/bdd-journeys/journey.md"
        write_file(artifact_path, journey_content)
        log_artifact(stage_id, artifact_path)

    log_stage_done(stage_id, str(result.get("gherkin_scenarios", ""))[:120])
    handoff_update = build_handoff_update(stage_id, result, [], state)
    return {"stages": stages, **handoff_update}


def init_refine_node(state: dict[str, Any]) -> dict[str, Any]:
    import logging as _logging

    from eng_loop.tools.agent_runner import AgentResult, run_agent
    from eng_loop.tools.agent_tools import get_tools_for_stage

    _dbg = _logging.getLogger(__name__)

    stages = dict(state.get("stages", {}))
    stage_id = "init.refine"
    config = state.get("config", {})
    paths = state.get("paths", {})

    # Essence gate
    essence = run_essence_gate(stage_id, state, paths, config)
    essence_result = _handle_essence_result(stage_id, essence, state, config, stages)
    if essence_result:
        return essence_result
    if essence.updated_state and essence.updated_state.get("stages"):
        stages = essence.updated_state["stages"]

    if stages.get(stage_id, {}).get("done", False):
        log_stage_skip(stage_id)
        return {}
    max_attempts = config.get("constraints", {}).get("max_init_refine_attempts", 5)
    current_attempts = stages[stage_id].get("attempts", 0)
    _dbg.debug(
        "[DEBUG] init_refine_node: attempts=%d/%d, max_agent_iterations=%d",
        current_attempts,
        max_attempts,
        config.get("agent", {}).get("max_agent_iterations", 25),
    )

    if stages[stage_id].get("attempts", 0) >= max_attempts:
        stages[stage_id]["done"] = True
        log_stage_done(stage_id, "max attempts reached, proceeding")
        return {}

    prompt = build_node_prompt(
        stage_id,
        state,
        paths,
        config,
        role_description="Idea Refinement agent",
        instructions=(
            "Refine the work item into an engineering-ready specification. Keep it concise.\n"
            "Return a JSON object with these fields: refined_work_item, ready_for_architecture."
        ),
    )
    model = create_model_from_config(config, stage_id)

    tools = get_tools_for_stage(stage_id, paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id=stage_id,
        output_schema=InitRefineOutput,
        max_iterations=max_agent_iterations,
        config=config,
    )

    result = agent_result.data

    if agent_result.error:
        _dbg.error(
            "[DEBUG] init_refine_node: agent_result.error=%s, iterations=%d, elapsed=%.1fs, tool_calls=%d, data=%s",
            agent_result.error,
            agent_result.iterations,
            agent_result.elapsed,
            agent_result.tool_calls_made,
            str(agent_result.data)[:300],
        )
        log_stage_fail(stage_id, agent_result.error)
        stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
        if stages[stage_id]["attempts"] < max_attempts:
            _dbg.warning("[DEBUG] init_refine_node: RETRYING attempt %d/%d", stages[stage_id]["attempts"], max_attempts)
            return {
                "stages": stages,
                "errors": list(state.get("errors", [])) + [f"{stage_id} agent error: {agent_result.error}"],
            }
        _dbg.error("[DEBUG] init_refine_node: max attempts %d reached, proceeding", max_attempts)
        stages[stage_id]["done"] = True
        return {}

    stages[stage_id]["attempts"] = stages[stage_id].get("attempts", 0) + 1
    stages[stage_id]["done"] = True
    stages[stage_id]["output"] = str(result)

    refined = result.get("refined_work_item", state.get("work_item", ""))
    refined_str = str(refined) if refined else ""
    log_stage_done(stage_id, refined_str[:120] if refined_str else "refined")

    handoff_update = build_handoff_update(stage_id, result, [], state)

    return {
        "stages": stages,
        "work_item": refined,
        **handoff_update,
    }

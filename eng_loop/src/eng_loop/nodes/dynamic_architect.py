from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import DynamicBlueprint, DynamicBlueprintProposal, DynamicRuntime
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.agent_tools import get_tools_for_stage
from eng_loop.tools.node_helpers import build_node_prompt
from eng_loop.tools.policy_resolver import authorize_blueprint
from eng_loop.tools.progress import log_stage_done, log_stage_fail

logger = logging.getLogger(__name__)


def dynamic_architect_node(state: dict[str, Any]) -> Command[str]:
    """Intercept node: evaluates work item and emits a dynamic blueprint proposal.

    The LLM proposes a DynamicBlueprintProposal. The framework authorizes it
    via policy rules to produce the official DynamicBlueprint. If the blueprint
    requires augmentation, routes to meta-executor; otherwise passes through.
    """
    config = state.get("config", {})
    paths = state.get("paths", {})
    work_item = state.get("work_item", "")
    codebase_facts = state.get("codebase_facts", {})

    if state.get("dynamic_plan"):
        logger.info("dynamic_architect: plan already exists, skipping")
        plan = state["dynamic_plan"]
        if plan.get("trigger") == "augment" and plan.get("steps"):
            return Command(goto="meta-executor")
        return Command(goto="init")

    instructions = (
        f"Evaluate this work item and determine if dynamic step augmentation is needed.\n\n"
        f"Work item: {work_item}\n\n"
        f"Codebase facts: {json.dumps(codebase_facts, default=str)}\n\n"
        "If the work item requires sub-tasks beyond the standard pipeline stages,\n"
        "propose dynamic steps with specific roles, tool capabilities, and validation rules.\n"
        "Each step must have a unique step_id matching ^[a-z0-9][a-z0-9-]{{2,63}}$.\n"
        "Max 5 steps allowed. Use trigger='augment' only if dynamic steps are truly needed.\n\n"
        "Return a JSON object with fields: plan_id, trigger, proposed_complexity, steps, rationale."
    )

    prompt = build_node_prompt(
        "dynamic.architect",
        state,
        paths,
        config,
        role_description="Dynamic Planning Architect",
        instructions=instructions,
    )

    model = create_model_from_config(config, "dynamic.architect")
    tools = get_tools_for_stage("dynamic.architect", paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 15)

    agent_result: AgentResult = run_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        stage_id="dynamic.architect",
        output_schema=DynamicBlueprintProposal,
        max_iterations=max_agent_iterations,
        config=config,
    )

    if agent_result.error:
        logger.warning("dynamic_architect: LLM error, defaulting to no augmentation: %s", agent_result.error)
        return _build_passthrough_command()

    proposal_data = agent_result.data
    try:
        proposal = DynamicBlueprintProposal(**proposal_data)
    except Exception as e:
        log_stage_fail("dynamic.architect", f"Invalid proposal schema: {e}")
        return _build_passthrough_command()

    if proposal.trigger != "augment" or not proposal.steps:
        logger.info("dynamic_architect: no augmentation proposed")
        blueprint = DynamicBlueprint(
            plan_id="none",
            trigger="none",
            authorized_complexity="standard",
            steps=(),
            rationale="No augmentation needed.",
        )
        return Command(
            update={
                "dynamic_plan": blueprint.model_dump(),
                "dynamic_runtime": DynamicRuntime(status="completed").model_dump(),
            },
            goto="init",
        )

    blueprint = authorize_blueprint(proposal, state)

    if blueprint.authorized_complexity == "restricted":
        log_stage_fail("dynamic.architect", "Restricted complexity — human approval required")
        return Command(
            update={
                "status": "blocked",
                "blocking_condition": "Restricted complexity class enforced by framework policy. Human approval required.",
            },
            goto="__end__",
        )

    logger.info(
        "dynamic_architect: authorized blueprint %s with %d steps (%s)",
        blueprint.plan_id,
        len(blueprint.steps),
        blueprint.authorized_complexity,
    )
    log_stage_done("dynamic.architect", f"blueprint {blueprint.plan_id}: {len(blueprint.steps)} steps")

    return Command(
        update={
            "dynamic_plan": blueprint.model_dump(),
            "dynamic_runtime": DynamicRuntime(status="running").model_dump(),
        },
        goto="meta-executor",
    )


def _build_passthrough_command() -> Command[str]:
    blueprint = DynamicBlueprint(
        plan_id="none",
        trigger="none",
        authorized_complexity="standard",
        steps=(),
        rationale="Architect node error — defaulting to standard pipeline.",
    )
    return Command(
        update={
            "dynamic_plan": blueprint.model_dump(),
            "dynamic_runtime": DynamicRuntime(status="completed").model_dump(),
        },
        goto="init",
    )

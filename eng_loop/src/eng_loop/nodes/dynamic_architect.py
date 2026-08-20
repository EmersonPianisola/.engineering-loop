from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.schemas import (
    DynamicBlueprint,
    DynamicBlueprintProposal,
    DynamicRuntime,
    GraphTopologyProposal,
)
from eng_loop.state import get_work_item_text
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.agent_tools import get_tools_for_stage
from eng_loop.tools.node_helpers import build_node_prompt
from eng_loop.tools.policy_resolver import (
    TopologyValidationError,
    authorize_blueprint,
    authorize_topology,
)
from eng_loop.tools.progress import log_stage_done, log_stage_fail

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────────────────
# PRE-BUILD: Topology Architect
# Produces a GraphTopologyProposal for the graph builder.
# This runs BEFORE graph compilation, invoked by cli.py.
# ───────────────────────────────────────────────────────────────────


def propose_topology(
    work_item: str,
    codebase_facts: dict[str, Any],
    config: dict[str, Any],
    state: dict[str, Any],
    paths: dict[str, Any] | None = None,
) -> GraphTopologyProposal | None:
    """Ask the LLM to propose an optimal graph topology for the work item.

    Returns a GraphTopologyProposal on success, None on any failure.
    The caller (cli.py) is responsible for catching None and falling back
    to the deterministic graph builder.
    """
    paths = paths or {}
    node_catalog = _build_node_catalog_context()
    allowed_conditions_text = _build_allowed_conditions_context()
    context_budget_text = _build_context_budget_context(config)

    instructions = (
        f"You are a Graph Topology Architect. Your job is to design the optimal\n"
        f"execution graph for the given work item.\n\n"
        f"## WORK ITEM\n"
        f"{work_item}\n\n"
        f"## CODEBASE FACTS\n"
        f"{json.dumps(codebase_facts, default=str)}\n\n"
        f"## AVAILABLE NODE CATALOG\n"
        f"{node_catalog}\n\n"
        f"## ALLOWED EDGE CONDITIONS\n"
        f"{allowed_conditions_text}\n\n"
        f"{context_budget_text}\n"
        if context_budget_text
        else ""
        "## CRITICAL: HAPPY-PATH ONLY\n"
        "You propose ONLY the happy-path (forward-progress) edges.\n"
        "Failure routing (loopback on retry, terminal on blocked) is AUTOMATICALLY\n"
        "injected by the framework. NEVER propose loopback or terminal edges.\n"
        "Proposing a loopback edge (e.g., verify -> impl.code) creates a cycle\n"
        "and will be REJECTED by the policy firewall.\n\n"
        "## CRITICAL RULES\n"
        "1. Include 'init' (entry) and 'post' (exit) — they are MANDATORY.\n"
        "2. All stages in required_stages must exist in the catalog above.\n"
        "3. All edges must connect stages in required_stages (or __start__/__end__).\n"
        "4. The graph must be a DAG (Directed Acyclic Graph). NO CYCLES.\n"
        "5. 'post' must be reachable from 'init' via forward edges.\n"
        "6. No duplicate edges.\n"
        "7. Use edge_type='fixed' for unconditional transitions (default).\n"
        "8. Use edge_type='conditional' with an allowed condition for branching.\n"
        "9. DO NOT use edge_type='loopback' — failure routing is automatic.\n"
        "10. DO NOT use edge_type='terminal' — blocked routing is automatic.\n"
        "11. Minimize stages — only include what the task genuinely needs.\n"
        "12. DO NOT include design/arch/verify/QA/deploy stages for documentation tasks.\n"
        "13. DO NOT include impl.design/impl.code/verify/deploy for operational tasks.\n"
        "14. For bugfix tasks, skip design stages but keep impl + verify.\n"
        "15. Each stage should have exactly ONE outgoing edge (or two for branching).\n"
        "16. Edges should flow forward: init -> ... -> impl -> ... -> post.\n\n"
        "## DOCUMENTATION TASK RULES (CRITICAL)\n"
        "For documentation tasks that produce NEW files (summary, report, new doc):\n"
        "  - MUST include 'impl.code' stage (this is where files are actually written)\n"
        "  - DO NOT use 'doc.update' — it requires impl.code.done=true as prerequisite\n"
        "  - Pattern: init -> init.ideate -> init.refine -> impl.code -> post\n\n"
        "For documentation tasks that only UPDATE existing files (README, CHANGELOG):\n"
        "  - Use 'doc.update' stage\n"
        "  - Pattern: init -> init.ideate -> init.refine -> impl.code -> doc.update -> post\n\n"
        "NEVER propose a topology with 'doc.update' but without 'impl.code'.\n\n"
        "## EXAMPLE (documentation task — new file)\n"
        "required_stages: [init, init.ideate, init.refine, impl.code, post]\n"
        "edges:\n"
        "  - init -> init.ideate (fixed)\n"
        "  - init.ideate -> init.refine (fixed)\n"
        "  - init.refine -> impl.code (fixed)\n"
        "  - impl.code -> post (fixed)\n"
        "  - post -> __end__ (fixed)\n\n"
        "## OUTPUT FORMAT\n"
        "Return a JSON object matching this schema:\n"
        "{\n"
        '  "plan_id": "unique-id",\n'
        '  "work_type": "feature|bugfix|documentation|operational",\n'
        '  "complexity": "small|medium|large|complex",\n'
        '  "required_stages": ["stage.id", ...],\n'
        '  "edges": [\n'
        '    {"from_stage": "A", "to_stage": "B", "edge_type": "fixed", "condition": "always", "description": "..."},\n'
        "    ...\n"
        "  ],\n"
        '  "phase_groups": [\n'
        '    {"name": "INIT", "stages": ["init", "init.ideate", ...]},\n'
        "    ...\n"
        "  ],\n"
        '  "execution_policies": [],\n'
        '  "rationale": "Why this topology is optimal for the task"\n'
        "}\n"
    )

    prompt = build_node_prompt(
        "dynamic.architect",
        state,
        paths,
        config,
        role_description="Graph Topology Architect",
        instructions=instructions,
    )

    model = create_model_from_config(config, "dynamic.architect")
    tools = get_tools_for_stage("dynamic.architect", paths, config, state)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 15)

    try:
        agent_result: AgentResult = run_agent(
            model=model,
            tools=tools,
            prompt=prompt,
            stage_id="dynamic.architect.topology",
            output_schema=GraphTopologyProposal,
            max_iterations=max_agent_iterations,
            config=config,
        )
    except Exception as e:
        logger.warning("architect propose_topology: LLM error: %s", e)
        return None

    if agent_result.error:
        logger.warning("architect propose_topology: agent error: %s", agent_result.error)
        return None

    proposal_data = agent_result.data
    try:
        proposal = GraphTopologyProposal(**proposal_data)
    except Exception as e:
        logger.warning("architect propose_topology: schema validation failed: %s", e)
        return None

    # Authorize through policy firewall
    try:
        authorized = authorize_topology(proposal, state)
        logger.info(
            "architect: authorized topology %s with %d stages (%s)",
            authorized.plan_id,
            len(authorized.authorized_stages),
            authorized.policy_notes or "clean",
        )
        log_stage_done(
            "dynamic.architect.topology",
            f"topology {authorized.plan_id}: {len(authorized.authorized_stages)} stages",
        )
        return proposal
    except TopologyValidationError as e:
        logger.warning("architect propose_topology: policy rejected: [%s] %s", e.layer, e.message)
        return None


def _build_node_catalog_context() -> str:
    """Build the node catalog text for the architect's prompt."""
    from eng_loop.state import build_node_catalog_text

    return build_node_catalog_text()


def _build_allowed_conditions_context() -> str:
    """Build the allowed conditions text for the architect's prompt."""
    condition_descriptions = {
        "always": "Unconditional transition",
        "stage_done": "Stage completed successfully",
        "stage_failed": "Stage failed verification",
        "stage_blocked": "Pipeline blocked",
        "complexity_at_least_medium": "Complexity is medium, large, or complex",
        "complexity_at_least_large": "Complexity is large or complex",
        "complexity_is_complex": "Complexity is exactly complex",
        "complexity_is_small": "Complexity is small",
        "is_ui_project": "Project has UI components",
        "not_ui_project": "Project has no UI components",
    }
    lines = ["| Condition | Description |"]
    lines.append("|---|---|")
    for cond, desc in condition_descriptions.items():
        lines.append(f"| `{cond}` | {desc} |")
    return "\n".join(lines)


def _build_context_budget_context(config: dict[str, Any]) -> str:
    """Build context budget information for the architect's prompt.

    Provides the architect with context window constraints so it can
    propose a topology that respects the available budget.
    """
    hardware = config.get("hardware", {})
    context_window = hardware.get("context_window", 0)
    if context_window <= 0:
        return ""

    budget_cfg = hardware.get("context_budget", {})
    reserved = budget_cfg.get("reserved_output", {}).get("default", 4096)
    margin = budget_cfg.get("safety_margin_tokens", 2048)
    effective = context_window - reserved - margin

    return (
        f"## CONTEXT BUDGET CONSTRAINTS\n"
        f"The model has a context window of {context_window:,} tokens.\n"
        f"After reserving {reserved:,} tokens for output and {margin:,} for safety margin,\n"
        f"the effective input budget is {effective:,} tokens per call.\n"
        f"Design a topology that can execute within these constraints.\n"
        f"Stages that accumulate large context (many tool calls, large artifacts)\n"
        f"may need compaction. Prefer fewer, more focused stages over many small ones.\n\n"
    )


# ───────────────────────────────────────────────────────────────────
# RUNTIME: Dynamic Architect Node (in-graph)
# Handles micro-augmentation decisions during execution.
# Cannot alter the structural topology — only proposes runtime steps.
# ───────────────────────────────────────────────────────────────────


def dynamic_architect_node(state: dict[str, Any]) -> Command[str]:
    """Runtime intercept node: evaluates if micro-augmentation is needed.

    This runs INSIDE the compiled graph, after init-setup.
    It can only propose DynamicBlueprint steps (pre-pipeline augmentation),
    NOT alter the structural topology (that's done by propose_topology pre-build).
    """
    config = state.get("config", {})
    paths = state.get("paths", {})
    work_item = get_work_item_text(state)
    codebase_facts = state.get("codebase_facts", {})

    # If we have a pre-build topology proposal, check if it was authorized
    topology_proposal = state.get("topology_proposal")
    if topology_proposal:
        logger.info("dynamic_architect: topology already proposed pre-build, checking augmentation")

    if state.get("dynamic_plan"):
        logger.info("dynamic_architect: dynamic plan already exists, skipping")
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
        "Each step must have a unique step_id matching ^[a-z0-9][a-z0-9-]{{2,63}}$\n"
        "Max 5 steps allowed. Use trigger='augment' only if dynamic steps are truly needed.\n\n"
        "Return a JSON object matching this schema:\n"
        "{{\n"
        '  "plan_id": "unique-id",\n'
        '  "trigger": "none" or "augment",\n'
        '  "proposed_complexity": "standard" or "adaptive" or "restricted",\n'
        '  "rationale": "explanation",\n'
        '  "steps": [\n'
        "    {\n"
        '      "step_id": "lowercase-hyphenated-id",\n'
        '      "role_description": "cognitive agent role for this step (REQUIRED)",\n'
        '      "requested_capabilities": ["read_files", "write_files"],\n'
        '      "max_attempts": 3,\n'
        '      "validation_rules": [\n'
        '        {"type": "files_exist", "payload": {"paths": ["src/foo.py"]}},\n'
        '        {"type": "tests_pass", "payload": {"suite": "unit", "command": "pytest tests/"}},\n'
        '        {"type": "contains_symbol", "payload": {"symbol": "def main", "target_file": "src/foo.py"}}\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "CRITICAL VALIDATION RULES (read these carefully):\n"
        "- validation_rules must be objects with 'type' and 'payload' fields\n"
        "- type must be one of: 'tests_pass', 'files_exist', 'contains_symbol'\n"
        "- For 'tests_pass', payload must have 'suite' (unit|integration|e2e) and 'command'\n"
        "- For 'files_exist', payload must have 'paths' (array of relative paths)\n"
        "- For 'contains_symbol', payload must have 'symbol' and 'target_file'\n"
        "- ONLY propose validation rules for things the agent will ACTUALLY CREATE or MODIFY in this step.\n"
        "  DO NOT propose 'files_exist' for files that already exist in the codebase.\n"
        "  DO NOT propose 'contains_symbol' for symbols in existing files — the agent cannot change pre-existing code arbitrarily.\n"
        "  DO NOT propose 'tests_pass' for test suites that are currently failing for unrelated reasons.\n"
        "  If you are unsure whether a file/symbol exists, DO NOT propose a validation rule for it.\n"
        "  Prefer NO validation rules over incorrect ones — a bad rule blocks the pipeline after 3 retries.\n"
        "- role_description is REQUIRED on every step\n"
        "- If trigger='none', steps must be empty array\n"
        "- If trigger='augment', steps must contain at least one step\n"
        "- proposed_complexity must be 'standard', 'adaptive', or 'restricted' (NOT 'small', 'medium', 'large', 'complex')"
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

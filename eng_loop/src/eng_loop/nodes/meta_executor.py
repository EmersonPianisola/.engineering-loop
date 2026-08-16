from __future__ import annotations

import copy
import logging
import time
from typing import Any

from langgraph.types import Command

from eng_loop.model import create_model_from_config
from eng_loop.tools.agent_runner import AgentResult, run_agent
from eng_loop.tools.dynamic_validation import evaluate_validation_rules
from eng_loop.tools.node_helpers import build_node_prompt
from eng_loop.tools.policy_resolver import SAFE_TOOL_POOL, get_tools_by_names
from eng_loop.tools.progress import log_stage_done, log_stage_fail

logger = logging.getLogger(__name__)


def meta_node_executor_node(state: dict[str, Any]) -> Command[str]:
    """Sequential executor for dynamic blueprint steps.

    Consumes the immutable dynamic_plan and advances through steps
    using a cursor in dynamic_runtime. Maintains strict attempt
    counting and typed validation per step.
    """
    plan = state.get("dynamic_plan")
    if not plan or plan.get("trigger") == "none":
        return Command(goto="init")

    runtime = _load_runtime(state)
    steps = plan.get("steps", [])

    try:
        runtime.validate_invariants(len(steps))
    except ValueError as e:
        log_stage_fail("meta.executor", f"Runtime invariant violation: {e}")
        return Command(
            update={
                "status": "blocked",
                "blocking_condition": f"Dynamic runtime error: {e}",
            },
            goto="__end__",
        )

    if runtime["cursor"] >= len(steps):
        runtime["status"] = "completed"
        return Command(
            update={"dynamic_runtime": runtime},
            goto="init",
        )

    current_step = steps[runtime["cursor"]]
    step_id = current_step["step_id"]
    max_attempts = current_step.get("max_attempts", 3)

    current_attempts = runtime["attempts"].get(step_id, 0) + 1

    if current_attempts > max_attempts:
        runtime["failed"].append(step_id)
        runtime["status"] = "blocked"
        log_stage_fail("meta.executor", f"Step '{step_id}' exceeded max_attempts ({max_attempts})")
        return Command(
            update={
                "dynamic_runtime": runtime,
                "status": "blocked",
                "blocking_condition": f"Dynamic step '{step_id}' exceeded max_attempts ({max_attempts})",
            },
            goto="__end__",
        )

    runtime["attempts"][step_id] = current_attempts

    allowed_tools = _resolve_step_tools(current_step, state)
    prompt = _build_step_prompt(current_step, state)

    config = state.get("config", {})
    model = create_model_from_config(config, step_id)
    max_agent_iterations = config.get("agent", {}).get("max_agent_iterations", 25)

    start_time = time.monotonic()
    agent_result: AgentResult = run_agent(
        model=model,
        tools=allowed_tools,
        prompt=prompt,
        stage_id=step_id,
        max_iterations=max_agent_iterations,
        config=config,
    )
    finish_time = time.monotonic()

    is_valid, err = evaluate_validation_rules(
        agent_result.data,
        tuple(current_step.get("validation_rules", [])),
        state.get("paths", {}).get("project_root", "."),
        state,
    )

    audit_entry = {
        "plan_id": plan.get("plan_id", ""),
        "step_id": step_id,
        "attempt": current_attempts,
        "status": "success" if is_valid else "failed",
        "started_at": start_time,
        "finished_at": finish_time,
        "error": err if not is_valid else None,
    }
    runtime["step_audit"].append(audit_entry)

    if not is_valid:
        if current_attempts < max_attempts:
            log_stage_fail("meta.executor", f"Step '{step_id}' attempt {current_attempts}/{max_attempts} failed: {err}")
            return Command(
                update={"dynamic_runtime": runtime, "errors": [err]},
                goto="meta-executor",
            )
        else:
            runtime["failed"].append(step_id)
            runtime["status"] = "blocked"
            log_stage_fail("meta.executor", f"Step '{step_id}' exhausted {current_attempts} attempts: {err}")
            return Command(
                update={
                    "dynamic_runtime": runtime,
                    "status": "blocked",
                    "blocking_condition": f"Dynamic step '{step_id}' failed after {current_attempts} attempts: {err}",
                },
                goto="__end__",
            )

    runtime["completed"].append(step_id)
    runtime["cursor"] += 1
    log_stage_done("meta.executor", f"Step '{step_id}' completed (attempt {current_attempts})")

    return Command(
        update={"dynamic_runtime": runtime},
        goto="meta-executor",
    )


def _load_runtime(state: dict[str, Any]) -> dict[str, Any]:
    """Load and deep-copy the dynamic runtime from state."""
    raw = state.get("dynamic_runtime", {})
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    return {
        "cursor": 0,
        "attempts": {},
        "completed": [],
        "failed": [],
        "status": "pending",
        "step_audit": [],
    }


def _resolve_step_tools(
    step: dict[str, Any],
    state: dict[str, Any],
) -> list:
    """Resolve and sandbox tool capabilities for a dynamic step."""
    requested = step.get("required_tools", step.get("requested_capabilities", []))
    if isinstance(requested, tuple):
        requested = list(requested)

    approved = [t for t in requested if t in SAFE_TOOL_POOL]
    if not approved:
        approved = ["read", "glob"]

    return get_tools_by_names(approved, state)


def _build_step_prompt(
    step: dict[str, Any],
    state: dict[str, Any],
) -> str:
    """Build execution prompt for a dynamic step."""
    config = state.get("config", {})
    paths = state.get("paths", {})

    return build_node_prompt(
        step["step_id"],
        state,
        paths,
        config,
        role_description=step.get("role_description", "Dynamic task executor"),
        instructions=(
            f"Execute this dynamic step. Project root: {paths.get('project_root', '.')}\n\n"
            "Use your available tools to complete the task. "
            "When finished, provide your final answer as a JSON object."
        ),
    )
